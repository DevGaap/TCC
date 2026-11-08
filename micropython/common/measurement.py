"""
Medição de um teste, usada pelos três programas em MicroPython.
Faz exatamente o mesmo que c/common/measurement.c e gera as mesmas linhas.

Sequência: parada IDLE_BEFORE_S -> teste por TEST_DURATION_S (LED aceso)
-> parada IDLE_AFTER_S -> DONE -> envio pelo Wi-Fi (LED piscando rápido).

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


def run(number, name, prepare, workload):
    """Roda a sequência inteira de um teste e depois manda os resultados pelo Wi-Fi.

    prepare: função opcional chamada antes do teste, fora da medição
    workload: função que faz a carga uma vez e devolve o checksum
    """
    try:
        machine.freq(config.CPU_FREQ_MHZ * 1_000_000)
        _record_header(number, name)
        _idle(config.IDLE_BEFORE_S)
        _run_test(number, name, prepare, workload)
        _idle(config.IDLE_AFTER_S)
        _record("DONE,%d" % time.ticks_ms())
    finally:
        _marker(0)

    # Daqui para frente a medição já acabou, então o consumo do Wi-Fi não atrapalha
    import wifi_sender
    wifi_sender.send("\n".join(_log) + "\n", _led)
