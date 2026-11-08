"""
Tira quadros do vídeo do medidor para montar o registro de potência ao longo do tempo.

A ideia é filmar o visor do medidor junto com o LED da placa durante a rodada inteira. Este
script pega um quadro a cada --every segundos e gera, dentro da pasta da rodada:

  frames/<tempo>s.jpg      um quadro por instante, com o tempo do vídeo escrito no canto
  sheets/sheet_NN.jpg      folhas com vários quadros lado a lado, para ler mais rápido
  <teste>_power.csv        tabela para preencher: t_s, voltage_v, current_a, charge_mah
                           (só é criada se ainda não existir, para não apagar o que já foi lido)

Se você passar --led com a região do LED no vídeo, o script mede o brilho dela em cada quadro
e sugere em que segundo o LED acendeu. Esse é o valor do --start-at do compute_energy.py.
Para descobrir as coordenadas, rode uma vez sem --led e abra um quadro em qualquer editor de
imagem (o Paint mostra a posição do mouse no rodapé).

Uso:
  python tools/extract_frames.py results/c/primes/primes-1
  python tools/extract_frames.py <pasta> --every 0.5 --crop 400,200,600,400 --led 1200,800,40,40
  python tools/extract_frames.py <pasta> --video outro_nome.mp4

Precisa do OpenCV (já instalado no micropython/.venv): pip install opencv-python
"""
import argparse
import csv
import pathlib
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("Falta o OpenCV. Instale com: micropython\\.venv\\Scripts\\python.exe -m pip install opencv-python")

VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".3gp", ".webm")
SHEET_COLS = 5
SHEET_ROWS = 4


def parse_box(text):
    parts = [int(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("use x,y,largura,altura")
    return parts


def find_video(run_dir):
    videos = sorted(p for p in run_dir.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
    if not videos:
        sys.exit("Nenhum vídeo encontrado em %s (coloque lá o <nome>_video.mp4, ex.: c-primes-1_video.mp4)" % run_dir)
    if len(videos) > 1:
        print("Mais de um vídeo na pasta; usando %s (escolha outro com --video)" % videos[0].name)
    return videos[0]


def test_name(run_dir):
    """O nome do teste vem do _results.csv que o servidor salvou na pasta."""
    found = list(run_dir.glob("*_results.csv"))
    if found:
        return found[0].name[: -len("_results.csv")]
    return run_dir.parent.name


def label(img, text):
    cv2.putText(img, text, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)


def thumbnail(img):
    """Cada quadro fica com no máximo 360 px de largura na folha, senão a imagem fica enorme."""
    h, w = img.shape[:2]
    scale = min(1.0, 360 / w)
    return cv2.resize(img, (int(w * scale), int(h * scale)))


def build_sheets(thumbs, out_dir):
    """Junta as miniaturas em folhas de SHEET_COLS x SHEET_ROWS."""
    out_dir.mkdir(exist_ok=True)
    per_sheet = SHEET_COLS * SHEET_ROWS
    th, tw = thumbs[0][1].shape[:2]
    count = 0
    for start in range(0, len(thumbs), per_sheet):
        chunk = thumbs[start:start + per_sheet]
        sheet = np.zeros((th * SHEET_ROWS, tw * SHEET_COLS, 3), dtype=np.uint8)
        for k, (t, thumb) in enumerate(chunk):
            thumb = thumb.copy()
            label(thumb, "%.1f s" % t)
            r, c = divmod(k, SHEET_COLS)
            sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = thumb
        count += 1
        cv2.imwrite(str(out_dir / ("sheet_%02d.jpg" % count)), sheet)
    return count


def suggest_led_times(levels):
    """Acha quando o brilho do LED sobe e desce: limiar no meio do caminho entre o mínimo e o máximo."""
    values = [v for _, v in levels]
    low, high = min(values), max(values)
    if high - low < 15:  # quase não variou; provavelmente a região está errada
        return None, None
    threshold = (low + high) / 2
    on = [t for t, v in levels if v > threshold]
    return on[0], on[-1]


def main():
    parser = argparse.ArgumentParser(description="Extrai quadros do vídeo do medidor.")
    parser.add_argument("run_dir", type=pathlib.Path, help="pasta da rodada (results/<linguagem>/<teste>/<teste>-<n>)")
    parser.add_argument("--video", help="nome do vídeo dentro da pasta (padrão: o único que tiver)")
    parser.add_argument("--every", type=float, default=1.0, help="segundos entre quadros (padrão 1)")
    parser.add_argument("--crop", type=parse_box, help="recorta só o visor: x,y,largura,altura")
    parser.add_argument("--led", type=parse_box, help="região do LED no vídeo: x,y,largura,altura")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    video = run_dir / args.video if args.video else find_video(run_dir)
    name = test_name(run_dir)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        sys.exit("Não consegui abrir %s" % video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    length_s = total / fps if total > 0 else 0
    print("Vídeo: %s (%.1f s, %.1f quadros/s)" % (video.name, length_s, fps))

    frames_dir = run_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    frames = []
    led_levels = []

    # Lê o vídeo inteiro em sequência e guarda o quadro mais próximo de cada instante pedido.
    # É mais lento que pular direto para o tempo, mas funciona com qualquer vídeo de celular.
    next_t = 0.0
    index = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        t = index / fps
        index += 1
        if t + 0.5 / fps < next_t:
            continue

        if args.led:
            x, y, w, h = args.led
            region = cv2.cvtColor(img[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
            led_levels.append((next_t, float(region.mean())))

        if args.crop:
            x, y, w, h = args.crop
            img = img[y:y + h, x:x + w]
        frames.append((next_t, thumbnail(img)))  # miniatura sem o rótulo, que a folha põe depois
        img = img.copy()
        label(img, "%.1f s" % next_t)
        cv2.imwrite(str(frames_dir / ("%07.1fs.jpg" % next_t)), img)
        next_t = round(next_t + args.every, 3)
    cap.release()

    if not frames:
        sys.exit("Nenhum quadro foi lido do vídeo.")
    print("%d quadros salvos em %s" % (len(frames), frames_dir))
    sheets = build_sheets(frames, run_dir / "sheets")
    print("%d folhas salvas em %s" % (sheets, run_dir / "sheets"))

    power = run_dir / ("%s_power.csv" % name)
    if power.exists():
        print("%s já existe; não mexi nele." % power.name)
    else:
        with open(power, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "voltage_v", "current_a", "charge_mah"])
            for t, _ in frames:
                w.writerow(["%.1f" % t, "", "", ""])
        print("Tabela para preencher: %s (charge_mah é opcional)" % power)

    if led_levels:
        with open(frames_dir / "led_levels.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "brightness"])
            w.writerows(("%.1f" % t, "%.1f" % v) for t, v in led_levels)
        on, off = suggest_led_times(led_levels)
        if on is None:
            print("O brilho da região do LED quase não mudou. Confira as coordenadas do --led.")
        else:
            print("LED aceso de %.1f s a %.1f s do vídeo (%.0f s; o teste dura 300 s)"
                  % (on, off, off - on + args.every))
            print("Use --start-at %.1f no compute_energy.py (confira olhando os quadros)" % on)


if __name__ == "__main__":
    main()
