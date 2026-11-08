"""
Medição de um teste, usada pelos três programas em MicroPython.
Faz exatamente o mesmo que c/common/measurement.c e gera as mesmas linhas.

Sequência: parada IDLE_BEFORE_S -> teste por TEST_DURATION_S (LED aceso)
-> parada IDLE_AFTER_S -> DONE -> registro na flash e soft reset -> envio pelo Wi-Fi
(LED piscando rápido).

Cada linha é impressa (útil para depurar com o cabo USB) e também guardada em memória,
para ser enviada quando a medição acabar. O módulo network só é importado depois do DONE.
"""
import gc
import machine
import math
import os
import time
from machine import Pin

import config

LANGUAGE = "MicroPython"

_led = Pin(config.LED_GPIO, Pin.OUT, value=0) if config.USE_LED_MARKER else None
_log = []


def _record(line):
    print(line)
    _log.append(line)


def _marker(level):
    if _led is not None:
        _led.value(level)


def _idle(seconds):
    if seconds <= 0:
        return
    _record("IDLE,%d,%d" % (time.ticks_ms(), seconds))
    time.sleep(seconds)


def _record_header(number, name):
    gc.collect()
    _record("INFO,language,%s" % LANGUAGE)
    _record("INFO,version,MicroPython %s" % os.uname().release)
    _record("INFO,test,%d;%s" % (number, name))
    _record("INFO,cpu_mhz,%d" % (machine.freq() // 1_000_000))
    _record("INFO,free_heap,%d" % gc.mem_free())
    _record("INFO,test_duration_s,%d" % config.TEST_DURATION_S)
    _record("INFO,params,primes=%d;matrix=%d;sorting=%d"
            % (config.PRIMES_LIMIT, config.MATRIX_N, config.SORT_N))
    # Número aleatório para o servidor reconhecer se a mesma rodada chegar duas vezes
    _record("INFO,run_id,%s" % "".join("%02x" % b for b in os.urandom(4)))


def _run_test(number, name, prepare, workload):
    if prepare is not None:
        prepare()

    gc.collect()
    heap_before = gc.mem_free()
    iterations = 0
    checksum = 0
    min_us = None
    max_us = 0
    mean = 0.0
    m2 = 0.0  # Welford: média e desvio padrão sem guardar todas as amostras

    _record("START,%d,%s,%d" % (number, name, time.ticks_ms()))
    _marker(1)

    target_ms = config.TEST_DURATION_S * 1000
    start = time.ticks_ms()
    while True:
        t0 = time.ticks_us()
        checksum = workload()
        dt = time.ticks_diff(time.ticks_us(), t0)

        iterations += 1
        if min_us is None or dt < min_us:
            min_us = dt
        if dt > max_us:
            max_us = dt
        delta = dt - mean
        mean += delta / iterations
        m2 += delta * (dt - mean)

        if time.ticks_diff(time.ticks_ms(), start) >= target_ms:
            break
    duration_ms = time.ticks_diff(time.ticks_ms(), start)

    _marker(0)
    _record("END,%d,%d" % (number, time.ticks_ms()))

    stdev = math.sqrt(m2 / (iterations - 1)) if iterations > 1 else 0.0
    _record("RESULT,%s,%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d"
            % (LANGUAGE, number, name, iterations, duration_ms,
               round(mean), min_us, max_us, round(stdev),
               checksum, heap_before, gc.mem_free()))


# Registro da rodada guardado na flash entre o fim do teste e o envio (ver run())
PENDING_FILE = "pending_send.txt"
UNSENT_FILE = "unsent_send.txt"


def _send_pending():
    """Se houver uma rodada esperando envio, manda pelo Wi-Fi e devolve True.

    A primeira linha do arquivo é o ticks_ms de quando ele foi gravado. Depois de um soft reset
    o relógio continua contando, então o ticks_ms atual é maior. Se a placa foi desligada no meio
    do envio, o relógio recomeçou do zero: aí o arquivo é de uma rodada antiga, fica guardado em
    UNSENT_FILE e o teste roda normalmente.
    """
    try:
        with open(PENDING_FILE) as f:
            saved_ms = int(f.readline())
            log = f.read()
    except (OSError, ValueError):
        return False

    if time.ticks_ms() < saved_ms:
        print("rodada antiga sem envio encontrada; guardada em %s" % UNSENT_FILE)
        try:
            os.remove(UNSENT_FILE)
        except OSError:
            pass
        os.rename(PENDING_FILE, UNSENT_FILE)
        return False

    import wifi_sender
    wifi_sender.send(log, _led)
    os.remove(PENDING_FILE)
    return True


def run(number, name, prepare, workload):
    """Roda a sequência inteira de um teste e depois manda os resultados pelo Wi-Fi.

    prepare: função opcional chamada antes do teste, fora da medição
    workload: função que faz a carga uma vez e devolve o checksum
    """
    # Depois do soft reset do fim da rodada, o main.py roda de novo e cai aqui só para enviar
    if _send_pending():
        return

    try:
        machine.freq(config.CPU_FREQ_MHZ * 1_000_000)
        _record_header(number, name)
        _idle(config.IDLE_BEFORE_S)
        _run_test(number, name, prepare, workload)
        _idle(config.IDLE_AFTER_S)
        _record("DONE,%d" % time.ticks_ms())
    finally:
        _marker(0)

    # Daqui para frente a medição já acabou, então o consumo do Wi-Fi não atrapalha.
    # Não dá para ligar o Wi-Fi direto: durante o teste o MicroPython aumenta o próprio heap
    # pegando RAM do sistema (nas matrizes, sobram uns 18 KB) e não devolve, e o Wi-Fi falha
    # com "WiFi Out of Memory". Então o registro vai para a flash e o soft reset devolve a RAM.
    # O ticks_ms não zera no soft reset, então os horários do SEND continuam certos.
    with open(PENDING_FILE, "w") as f:
        f.write("%d\n" % time.ticks_ms())
        f.write("\n".join(_log) + "\n")
    machine.soft_reset()
