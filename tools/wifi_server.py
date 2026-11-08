"""
Servidor que recebe pelo Wi-Fi os resultados das rodadas do ESP32 (roda no notebook).

A placa faz a medição com o Wi-Fi desligado, guarda as linhas em memória e, depois do DONE,
manda tudo por HTTP POST para http://<ip_do_notebook>:<porta>/result.

Cada rodada vira uma pasta própria, numerada na ordem em que chegou:

  results/<linguagem>/<teste>/<teste>-<n>/
      <linguagem>-<teste>-<n>_log.txt       todas as linhas recebidas, com o horário do notebook
      <linguagem>-<teste>-<n>_results.csv   a linha RESULT (execuções, tempos, checksum, memória)
      <linguagem>-<teste>-<n>_events.csv    IDLE / START / END / DONE, com o horário e o ms da placa
      <linguagem>-<teste>-<n>_notes.txt     modelo para anotar a montagem e o que foi visto no medidor

Exemplo: results/c/primes/primes-3/c-primes-3_results.csv. Com --suffix, o sufixo entra no
nome do teste: results/micropython/sorting-160mhz/sorting-160mhz-1/.
O <n> é sempre o próximo número livre, então nada é sobrescrito.

Como os dados só chegam no fim, o horário de cada linha é calculado: a placa manda o ms desde
o boot de cada evento e, na linha SEND, o ms no momento do envio. Então:
    horário do evento = horário em que o POST chegou - (ms do SEND - ms do evento)

Uso (com o Python do micropython/.venv, ou qualquer Python 3):
  python tools/wifi_server.py                 fica recebendo até Ctrl+C
  python tools/wifi_server.py --once          para depois de salvar uma rodada
  python tools/wifi_server.py --suffix 160mhz
"""
import argparse
import csv
import datetime
import http.server
import json
import pathlib
import socket
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
WIFI_CONFIG = ROOT / "wifi_config.json"

RESULT_FIELDS = [
    "language", "test", "name", "iterations", "duration_ms", "mean_us",
    "min_us", "max_us", "stdev_us", "checksum", "heap_before", "heap_after",
]
# Em que posição de cada tipo de linha fica o "ms desde o boot"
MS_FIELD = {"IDLE": 1, "START": 3, "END": 2, "DONE": 1, "SEND": 1}
EVENTS = ("IDLE", "START", "END", "DONE")

NOTES_TEMPLATE = """\
Anotações da rodada {name} ({when})

alimentação: fonte de bancada chaveada AFR FA-3005-M em modo C.V (tensão constante) ajustada em 5 V -> placa, sem a USB do notebook
medidor: display da própria fonte (AFR FA-3005-M, 3 dígitos, ~10 mA de resolução)
vídeo: (nome do arquivo, se filmou)

leituras no fim do teste (opcional, só para conferência):
  tensão (V):
  corrente (A):
  corrente na parada antes / depois do teste (A):

observações:
"""


class RunError(Exception):
    pass


def parse(text):
    """Separa as linhas recebidas e confere se a rodada veio completa."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    info = {}
    result = None
    send_ms = None
    for line in lines:
        fields = line.split(",")
        if fields[0] == "INFO" and len(fields) >= 3:
            info[fields[1]] = ",".join(fields[2:])
        elif fields[0] == "RESULT":
            if len(fields) != len(RESULT_FIELDS) + 1:
                raise RunError("linha RESULT com %d campos" % len(fields))
            result = fields[1:]
        elif fields[0] == "SEND":
            send_ms = int(fields[1])

    if "language" not in info or "test" not in info:
        raise RunError("faltam as linhas INFO de linguagem e teste")
    if result is None:
        raise RunError("falta a linha RESULT")
    if send_ms is None:
        raise RunError("falta a linha SEND")
    if not any(l.startswith("DONE,") for l in lines):
        raise RunError("falta a linha DONE")
    return lines, info, result, send_ms


def save(text, received, out_dir, suffix):
    lines, info, result, send_ms = parse(text)

    language = info["language"].lower()
    test_name = info["test"].split(";")[-1] + ("-" + suffix if suffix else "")

    def pc_time(ms):
        return received - datetime.timedelta(milliseconds=send_ms - ms)

    # Horário de cada linha: o dela mesma, se tiver ms; senão, o da linha anterior que tinha
    # (as INFO do começo ficam com o horário do primeiro evento)
    times = []
    for line in lines:
        fields = line.split(",")
        pos = MS_FIELD.get(fields[0])
        times.append(pc_time(int(fields[pos])) if pos is not None and len(fields) > pos else None)
    last = next((t for t in times if t is not None), received)
    for i, t in enumerate(times):
        if t is None:
            times[i] = last
        else:
            last = t
    iso = [t.isoformat(timespec="milliseconds") for t in times]

    start_time = next((t for t, l in zip(times, lines) if l.startswith("START,")), received)

    # A pasta da rodada é <teste>-<n>, com o próximo número que ainda não foi usado
    test_dir = out_dir / language / test_name
    test_dir.mkdir(parents=True, exist_ok=True)
    used = [int(p.name.rsplit("-", 1)[1]) for p in test_dir.iterdir()
            if p.is_dir() and p.name.startswith(test_name + "-")
            and p.name.rsplit("-", 1)[1].isdigit()]
    number = max(used, default=0) + 1
    run_dir = test_dir / f"{test_name}-{number}"
    run_dir.mkdir()
    name = f"{language}-{test_name}-{number}"
    prefix = run_dir / name

    with open(f"{prefix}_log.txt", "w", encoding="utf-8") as f:
        f.write("# recebido por Wi-Fi em %s; horários calculados a partir da linha SEND\n"
                % received.isoformat(timespec="milliseconds"))
        for t, line in zip(iso, lines):
            f.write(f"{t}\t{line}\n")

    with open(f"{prefix}_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pc_time"] + RESULT_FIELDS)
        i_res = next(i for i, l in enumerate(lines) if l.startswith("RESULT,"))
        w.writerow([iso[i_res]] + result)

    with open(f"{prefix}_events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pc_time", "event", "board_ms", "data"])
        for t, line in zip(iso, lines):
            fields = line.split(",")
            if fields[0] in EVENTS:
                ms = fields[MS_FIELD[fields[0]]]
                data = [x for i, x in enumerate(fields[1:], 1) if i != MS_FIELD[fields[0]]]
                w.writerow([t, fields[0], ms, ";".join(data)])

    (run_dir / f"{name}_notes.txt").write_text(
        NOTES_TEMPLATE.format(name=name, when=start_time.strftime("%d/%m/%Y %H:%M")),
        encoding="utf-8")

    return name, run_dir, info, dict(zip(RESULT_FIELDS, result))


def local_ips():
    ips = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(item[4][0])
    except OSError:
        pass
    # Descobre o IP que o notebook usa para sair para a rede (não manda nada de verdade)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    ips.discard("127.0.0.1")
    return sorted(ips)


def main():
    parser = argparse.ArgumentParser(description="Recebe pelo Wi-Fi os resultados do ESP32.")
    parser.add_argument("--port", type=int, help="porta TCP (padrão: a do wifi_config.json)")
    parser.add_argument("--suffix", default="", help="acrescentado ao nome do teste, ex.: 160mhz")
    parser.add_argument("--out", type=pathlib.Path, default=RESULTS_DIR)
    parser.add_argument("--once", action="store_true", help="encerra depois de salvar uma rodada")
    args = parser.parse_args()

    config = json.loads(WIFI_CONFIG.read_text(encoding="utf-8"))
    port = args.port or int(config["server_port"])
    seen_ids = set()
    server = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def _reply(self, code, text):
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            # Dá para testar pelo navegador do celular: http://<ip>:<porta>/
            self._reply(200, "servidor do TCC funcionando\n")

        def do_POST(self):
            if self.path != "/result":
                self._reply(404, "use /result\n")
                return
            received = datetime.datetime.now()
            size = int(self.headers.get("Content-Length", 0))
            text = self.rfile.read(size).decode("utf-8", errors="replace")
            print("\n[%s] POST de %s (%d bytes)" % (received.strftime("%H:%M:%S"),
                                                     self.client_address[0], size))

            run_id = next((l.split(",", 2)[2].strip() for l in text.splitlines()
                           if l.startswith("INFO,run_id,")), None)
            if run_id and run_id in seen_ids:
                # A placa não recebeu a confirmação e mandou de novo; não salva duas vezes
                print("A rodada %s já tinha sido salva; ignorando a repetição." % run_id)
                self._reply(200, "already received\n")
                return

            try:
                name, run_dir, info, res = save(text, received, args.out, args.suffix)
            except (RunError, ValueError) as e:
                print("Rodada recusada: %s" % e)
                print(text)
                self._reply(400, "incomplete run: %s\n" % e)
                return

            if run_id:
                seen_ids.add(run_id)
            self._reply(200, "ok\n")
            rel = run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir
            print("Rodada salva em %s (rodada %s deste teste)" % (rel, name.rsplit("-", 1)[1]))
            print("  %s, teste %s: %s execuções em %s ms, média %s us, checksum %s"
                  % (info["language"], res["name"], res["iterations"], res["duration_ms"],
                     res["mean_us"], res["checksum"]))
            print("\nPróximos passos (README, seção 6):\n"
                  "  1. coloque o vídeo do medidor nessa pasta como %s_video.mp4\n"
                  "  2. micropython\\.venv\\Scripts\\python.exe tools\\extract_frames.py %s\n"
                  "  3. preencha o %s_power.csv com as leituras dos quadros\n"
                  "  4. micropython\\.venv\\Scripts\\python.exe tools\\compute_energy.py %s --start-at <s>"
                  % (name, rel, name, rel))
            if args.once:
                threading.Thread(target=server.shutdown, daemon=True).start()

        def log_message(self, fmt, *values):
            pass  # o próprio Handler já imprime o que interessa

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    ips = local_ips()
    print("Servidor recebendo na porta %d. IPs deste notebook: %s" % (port, ", ".join(ips) or "?"))
    if config["server_ip"] not in ips:
        print("ATENÇÃO: o wifi_config.json usa server_ip=%s, que não é um IP deste notebook.\n"
              "         Corrija o arquivo e grave a placa de novo." % config["server_ip"])
    print("Teste pelo navegador do celular (mesma rede): http://%s:%d/" % (config["server_ip"], port))
    print("Esperando a placa enviar (Ctrl+C para parar)...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Servidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
