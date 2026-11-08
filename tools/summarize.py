"""
Junta todas as rodadas que já têm o _energy.csv e monta as tabelas do TCC.

Procura em results/<linguagem>/<teste>/<teste>-<n>/*_energy.csv (a pasta results/archive fica
de fora) e grava:

  results/summary.csv      uma linha por teste: número de rodadas, média e desvio padrão
                           entre as rodadas de tempo, potência e energia por execução
  results/comparison.csv   C contra MicroPython em cada teste: quantas vezes o MicroPython
                           é mais lento e quantas vezes gasta mais energia por execução

Uso:
  python tools/summarize.py
"""
import argparse
import csv
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"

METRICS = ["mean_us", "mean_power_w", "idle_power_w", "energy_j",
           "energy_per_iteration_mj", "net_energy_per_iteration_mj"]


def to_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def collect():
    groups = {}
    # results/<linguagem>/<teste>/<teste>-<n>/<arquivo>_energy.csv
    for path in sorted(RESULTS_DIR.glob("*/*/*/*_energy.csv")):
        test_dir = path.parent.parent
        language_dir = test_dir.parent
        if language_dir.name == "archive":
            continue
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                row["run"] = path.parent.name
                # chave no formato c-primes, para casar C com MicroPython depois
                key = f"{language_dir.name}-{test_dir.name}"
                groups.setdefault(key, []).append(row)
    return groups


def summarize(groups):
    summary = []
    for test_name, rows in sorted(groups.items()):
        first = rows[0]
        out = {"test_name": test_name, "language": first["language"], "test": first["test"],
               "name": first["name"], "runs": len(rows),
               "sources": ";".join(sorted({r["source"] for r in rows}))}
        for m in METRICS:
            values = [v for v in (to_float(r.get(m)) for r in rows) if v is not None]
            out[m + "_mean"] = round(statistics.mean(values), 5) if values else ""
            out[m + "_stdev"] = round(statistics.stdev(values), 5) if len(values) > 1 else ""
        summary.append(out)
    return summary


def compare(summary):
    """Casa c-<teste>[-sufixo] com micropython-<teste>[-sufixo]."""
    by_name = {s["test_name"]: s for s in summary}
    rows = []
    for name, c in sorted(by_name.items()):
        if not name.startswith("c-"):
            continue
        mp = by_name.get("micropython-" + name[2:])
        if mp is None:
            continue
        row = {"test": name[2:], "c_runs": c["runs"], "micropython_runs": mp["runs"]}
        for m, label in (("mean_us", "time"), ("mean_power_w", "power"),
                         ("energy_per_iteration_mj", "energy_per_iteration"),
                         ("net_energy_per_iteration_mj", "net_energy_per_iteration")):
            cv, mv = to_float(c[m + "_mean"]), to_float(mp[m + "_mean"])
            row["c_" + label] = c[m + "_mean"]
            row["micropython_" + label] = mp[m + "_mean"]
            row[label + "_ratio"] = round(mv / cv, 2) if cv and mv is not None else ""
        rows.append(row)
    return rows


def write(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("Salvo em", path)


def main():
    global RESULTS_DIR
    parser = argparse.ArgumentParser(description="Monta as tabelas com todas as rodadas.")
    parser.add_argument("--results", type=pathlib.Path, default=RESULTS_DIR,
                        help="pasta dos resultados (padrão: results/)")
    RESULTS_DIR = parser.parse_args().results.resolve()

    groups = collect()
    if not groups:
        print("Nenhuma rodada com _energy.csv em results/. Rode o compute_energy.py antes.")
        return
    summary = summarize(groups)
    comparison = compare(summary)

    print("%-28s %6s %14s %10s %18s" % ("teste", "rodadas", "tempo (us)", "potência", "mJ por execução"))
    for s in summary:
        print("%-28s %6d %14s %10s %18s" % (s["test_name"], s["runs"], s["mean_us_mean"],
                                           s["mean_power_w_mean"], s["energy_per_iteration_mj_mean"]))
    if comparison:
        print("\nMicroPython em relação ao C (quantas vezes):")
        for c in comparison:
            print("  %-20s tempo %sx, potência %sx, energia por execução %sx"
                  % (c["test"], c["time_ratio"], c["power_ratio"], c["energy_per_iteration_ratio"]))
        if any(c["c_runs"] < 5 or c["micropython_runs"] < 5 for c in comparison):
            print("  (alguns testes têm menos de 5 rodadas; o desvio padrão ainda é pouco confiável)")

    write(RESULTS_DIR / "summary.csv", summary)
    write(RESULTS_DIR / "comparison.csv", comparison)


if __name__ == "__main__":
    main()
