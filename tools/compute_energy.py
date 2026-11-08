"""
Calcula o consumo de uma rodada a partir do registro de potência ao longo do tempo.

Lê, da pasta da rodada:
  <teste>_results.csv   número de execuções e duração (salvo pelo wifi_server.py)
  <teste>_events.csv    quando começaram as paradas e o teste, no relógio da placa
  <teste>_power.csv     as leituras do medidor ao longo do tempo (do vídeo, ou de um sensor)

e grava <teste>_energy.csv na mesma pasta.

Formato do _power.csv (uma linha por leitura; linhas sem tensão ou corrente são ignoradas):
  t_s,voltage_v,current_a,charge_mah
  0.0,4.80,0.07,
  1.0,4.80,0.08,
  ...
  - t_s é o tempo no relógio do registro (no vídeo, o segundo do quadro). Para alinhar com a
    rodada, informe --start-at com o t_s em que o LED acendeu.
  - No lugar de t_s pode vir pc_time (horário do notebook, ISO). Aí o alinhamento é automático
    pelos horários do _events.csv, sem --start-at. É o caso de um registrador com sensor.
  - charge_mah é opcional. Se vier, serve só para conferir: o script compara o mAh que o medidor
    acumulou durante o teste com o mAh calculado pela integral da corrente.

Como a energia é calculada:
  - potência em cada leitura: P = V × I
  - energia do teste: integral de P no tempo, entre o START e o END (regra do trapézio)
  - potência ociosa: média de P nas paradas antes e depois do teste (sem o 1º e o último segundo)
  - energia líquida: energia do teste - potência ociosa × duração (só o custo de processar)
  - energia por execução: energia ÷ número de execuções, em mJ (é a métrica que compara as linguagens)

Sem registro de potência dá para usar uma leitura só (modo antigo, menos confiável):
  python tools/compute_energy.py <pasta> --voltage 4.80 --current 0.07 [--idle-current 0.05]

Uso normal:
  python tools/compute_energy.py results/c/primes/primes-1 --start-at 12.0
"""
import argparse
import csv
import datetime
import pathlib
import sys

FIELDS = [
    "language", "test", "name", "iterations", "duration_s", "mean_us", "checksum",
    "source", "samples", "coverage",
    "mean_voltage_v", "mean_current_a", "min_current_a", "max_current_a", "mean_power_w",
    "energy_j", "charge_mah", "meter_charge_mah",
    "idle_power_w", "net_energy_j",
    "energy_per_iteration_mj", "net_energy_per_iteration_mj",
]
IDLE_MARGIN_S = 1.0  # tira as bordas das paradas, onde o LED e a carga ainda estão mudando


def number(text):
    """Aceita 0.07 e 0,07 (o Excel em português salva com vírgula)."""
    text = (text or "").strip().replace(",", ".")
    return float(text) if text else None


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(f, delimiter=delimiter))


def find_files(target):
    run_dir = target if target.is_dir() else target.parent
    found = list(run_dir.glob("*_results.csv"))
    if len(found) != 1:
        sys.exit("Esperava um _results.csv em %s e achei %d" % (run_dir, len(found)))
    name = found[0].name[: -len("_results.csv")]
    return run_dir, name


def read_events(path):
    """Devolve os intervalos (em ms da placa) do teste e das paradas, e o horário do START."""
    test = None
    idles = []
    start_pc = None
    for row in read_csv(path):
        ms = int(row["board_ms"])
        if row["event"] == "START":
            test = [ms, None]
            start_pc = datetime.datetime.fromisoformat(row["pc_time"])
        elif row["event"] == "END" and test:
            test[1] = ms
        elif row["event"] == "IDLE":
            seconds = int(row["data"])
            idles.append((ms + IDLE_MARGIN_S * 1000, ms + (seconds - IDLE_MARGIN_S) * 1000))
    if not test or test[1] is None:
        sys.exit("O _events.csv não tem START e END")
    return tuple(test), idles, start_pc


def read_power(path, start_ms, start_pc, start_at):
    """Lê o registro e converte o tempo de cada leitura para ms no relógio da placa."""
    rows = read_csv(path)
    if not rows:
        sys.exit("%s está vazio" % path.name)
    samples = []
    if "pc_time" in rows[0]:
        for r in rows:
            v, i = number(r.get("voltage_v")), number(r.get("current_a"))
            if v is None or i is None:
                continue
            dt = datetime.datetime.fromisoformat(r["pc_time"]) - start_pc
            samples.append((start_ms + dt.total_seconds() * 1000, v, i, number(r.get("charge_mah"))))
    else:
        if start_at is None:
            sys.exit("Informe --start-at: o t_s do registro em que o LED acendeu")
        for r in rows:
            v, i = number(r.get("voltage_v")), number(r.get("current_a"))
            if v is None or i is None:
                continue
            t = number(r["t_s"])
            samples.append((start_ms + (t - start_at) * 1000, v, i, number(r.get("charge_mah"))))
    samples.sort()
    if len(samples) < 2:
        sys.exit("%s tem menos de duas leituras preenchidas" % path.name)
    return samples


def value_at(ts, ys, t):
    """Interpolação linear; fora do registro, repete a ponta."""
    if t <= ts[0]:
        return ys[0]
    if t >= ts[-1]:
        return ys[-1]
    lo, hi = 0, len(ts) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ts[mid] <= t:
            lo = mid
        else:
            hi = mid
    f = (t - ts[lo]) / (ts[hi] - ts[lo])
    return ys[lo] + f * (ys[hi] - ys[lo])


def integrate(ts, ys, a, b):
    """Integral (trapézio) de y entre a e b, só na parte coberta pelo registro."""
    a2, b2 = max(a, ts[0]), min(b, ts[-1])
    if b2 <= a2:
        return 0.0, 0.0
    points = [a2] + [t for t in ts if a2 < t < b2] + [b2]
    total = 0.0
    for t0, t1 in zip(points, points[1:]):
        total += (value_at(ts, ys, t0) + value_at(ts, ys, t1)) / 2 * (t1 - t0)
    return total, b2 - a2


def from_log(samples, test, idles):
    ts = [s[0] / 1000 for s in samples]  # segundos
    volts = [s[1] for s in samples]
    amps = [s[2] for s in samples]
    power = [v * i for v, i in zip(volts, amps)]
    a, b = test[0] / 1000, test[1] / 1000

    energy, covered = integrate(ts, power, a, b)
    coulombs, _ = integrate(ts, amps, a, b)
    volt_area, _ = integrate(ts, volts, a, b)
    # leituras bem na borda ainda podem ser da parada, então ficam fora do mínimo e do máximo
    inside = [i for t, i in zip(ts, amps) if a < t < b]
    if covered == 0:
        sys.exit("O registro não cobre o intervalo do teste. Confira o --start-at.")

    out = {
        "samples": len(inside),
        "coverage": round(covered / (b - a), 3),
        "mean_voltage_v": round(volt_area / covered, 4),
        "mean_current_a": round(coulombs / covered, 4),
        "min_current_a": min(inside) if inside else "",
        "max_current_a": max(inside) if inside else "",
        "mean_power_w": round(energy / covered, 4),
        # se o registro não cobre o teste todo, estima o que falta pela potência média
        "energy_j": energy / covered * (b - a),
        "charge_mah": round(coulombs / covered * (b - a) / 3.6, 3),
    }

    charges = [(t, c) for t, (_, _, _, c) in zip(ts, samples) if c is not None]
    if len(charges) >= 2:
        cts, cys = [c[0] for c in charges], [c[1] for c in charges]
        out["meter_charge_mah"] = round(value_at(cts, cys, b) - value_at(cts, cys, a), 3)

    idle_energy = idle_time = 0.0
    for lo, hi in idles:
        e, d = integrate(ts, power, lo / 1000, hi / 1000)
        idle_energy += e
        idle_time += d
    if idle_time > 0:
        out["idle_power_w"] = idle_energy / idle_time
    return out


def main():
    parser = argparse.ArgumentParser(description="Calcula a energia de uma rodada.")
    parser.add_argument("run_dir", type=pathlib.Path, help="pasta da rodada (results/<linguagem>/<teste>/<teste>-<n>)")
    parser.add_argument("--power", type=pathlib.Path, help="registro de potência (padrão: <teste>_power.csv)")
    parser.add_argument("--start-at", type=float, help="t_s do registro em que o LED acendeu")
    parser.add_argument("--voltage", type=float, help="modo de leitura única: tensão (V)")
    parser.add_argument("--current", type=float, help="modo de leitura única: corrente (A)")
    parser.add_argument("--charge-mah", type=float, help="modo de leitura única: mAh do medidor (só conferência)")
    parser.add_argument("--idle-current", type=float, help="modo de leitura única: corrente parada (A)")
    args = parser.parse_args()

    run_dir, name = find_files(args.run_dir.resolve())
    result = read_csv(run_dir / f"{name}_results.csv")[0]
    test, idles, start_pc = read_events(run_dir / f"{name}_events.csv")
    iterations = int(result["iterations"])
    duration_s = (test[1] - test[0]) / 1000

    row = {k: "" for k in FIELDS}
    row.update({
        "language": result["language"], "test": result["test"], "name": result["name"],
        "iterations": iterations, "duration_s": duration_s, "mean_us": result["mean_us"],
        "checksum": result["checksum"],
    })

    power_file = args.power or run_dir / f"{name}_power.csv"
    if args.voltage is not None and args.current is not None:
        row["source"] = "single_reading"
        p = args.voltage * args.current
        row.update({
            "samples": 1, "mean_voltage_v": args.voltage, "mean_current_a": args.current,
            "mean_power_w": round(p, 4), "energy_j": p * duration_s,
            "charge_mah": round(args.current * duration_s / 3.6, 3),
            "meter_charge_mah": "" if args.charge_mah is None else args.charge_mah,
        })
        if args.idle_current is not None:
            row["idle_power_w"] = args.voltage * args.idle_current
    elif power_file.exists():
        row["source"] = power_file.name
        samples = read_power(power_file, test[0], start_pc, args.start_at)
        row.update(from_log(samples, test, idles))
    else:
        sys.exit("Não achei %s. Gere com o extract_frames.py e preencha, ou use --voltage e --current."
                 % power_file.name)

    energy = row["energy_j"]
    row["energy_per_iteration_mj"] = round(energy / iterations * 1000, 5)
    if row["idle_power_w"] != "":
        net = energy - row["idle_power_w"] * duration_s
        row["net_energy_j"] = round(net, 3)
        row["net_energy_per_iteration_mj"] = round(net / iterations * 1000, 5)
        row["idle_power_w"] = round(row["idle_power_w"], 4)
    row["energy_j"] = round(energy, 3)

    out = run_dir / f"{name}_energy.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerow(row)

    print("%s, teste %s (%s), %d execuções em %.1f s" % (row["language"], row["test"], row["name"],
                                                           iterations, duration_s))
    print("  potência média: %.3f W  (%.3f V, %.4f A)" % (row["mean_power_w"], row["mean_voltage_v"],
                                                          row["mean_current_a"]))
    print("  energia do teste: %.2f J  ->  %.5f mJ por execução" % (row["energy_j"],
                                                                   row["energy_per_iteration_mj"]))
    if row["net_energy_j"] != "":
        print("  parada: %.3f W  ->  energia líquida %.2f J, %.5f mJ por execução"
              % (row["idle_power_w"], row["net_energy_j"], row["net_energy_per_iteration_mj"]))
    if row["coverage"] != "" and row["coverage"] < 0.98:
        print("  ATENÇÃO: o registro cobre só %.0f%% do teste; o resto foi estimado pela média."
              % (row["coverage"] * 100))
    if row["meter_charge_mah"] != "":
        calc, meter = row["charge_mah"], row["meter_charge_mah"]
        print("  conferência: integral da corrente = %.2f mAh, medidor acumulou %.2f mAh" % (calc, meter))
        if calc and abs(meter - calc) / calc > 0.15:
            print("  ATENÇÃO: diferença de %.0f%%. Uma das duas leituras do medidor não é confiável."
                  % (abs(meter - calc) / calc * 100))
    print("Salvo em", out)


if __name__ == "__main__":
    main()
