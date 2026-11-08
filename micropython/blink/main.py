"""
Programa simples para conferir o ambiente MicroPython:
 - mostra algumas informações do chip;
 - mede quanto tempo leva um laço de 1.000.000 de somas;
 - fica piscando o LED da placa (GPIO2) a cada 500 ms.
"""
import esp
import gc
import machine
import os
import time
from machine import Pin

LED_GPIO = 2
BLINK_INTERVAL_MS = 500


def print_chip_info():
    print("\n=== Teste ESP32 em MicroPython ===")
    print("Versao:", os.uname().version)
    print("Frequencia CPU:", machine.freq() // 1_000_000, "MHz")
    print("Flash:", esp.flash_size() // (1024 * 1024), "MB")
    gc.collect()
    print("Heap livre:", gc.mem_free(), "bytes")


def loop_benchmark():
    total = 0
    start = time.ticks_us()
    for i in range(1_000_000):
        total += i
    end = time.ticks_us()
    print("Laco de 1.000.000 iteracoes:", time.ticks_diff(end, start), "us (soma=%d)" % total)


def main():
    print_chip_info()
    loop_benchmark()

    led = Pin(LED_GPIO, Pin.OUT)
    state = 0
    counter = 0

    while True:
        state = not state
        led.value(state)
        print("[%d] LED %s" % (counter, "LIGADO" if state else "DESLIGADO"))
        counter += 1
        time.sleep_ms(BLINK_INTERVAL_MS)


main()
