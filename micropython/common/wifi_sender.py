"""
Liga o Wi-Fi, manda as linhas da rodada para o servidor do notebook por HTTP POST e desliga
o Wi-Fi de novo. Faz o mesmo que c/common/wifi_sender.c: acrescenta SEND,<ms_desde_o_boot> em
cada tentativa e não desiste até o servidor confirmar. A rede e o IP vêm do wifi_config.json.
"""
import json
import network
import socket
import time

BLINK_MS = 150


def _read_config():
    with open("wifi_config.json") as f:
        return json.load(f)


def _wait_blinking(led, ms, wlan=None):
    """Espera até `ms` piscando o LED; se receber `wlan`, sai assim que conectar."""
    level = 0
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        level = 1 - level
        if led is not None:
            led.value(level)
        time.sleep_ms(BLINK_MS)
        if wlan is not None and wlan.isconnected():
            break
    if led is not None:
        led.value(0)


def _post(ip, port, body):
    data = body.encode()
    header = ("POST /result HTTP/1.0\r\nHost: %s:%d\r\n"
              "Content-Type: text/plain; charset=utf-8\r\nContent-Length: %d\r\n\r\n"
              % (ip, port, len(data))).encode()
    address = socket.getaddrinfo(ip, port)[0][-1]
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(address)
        for part in (header, data):
            sent = 0
            while sent < len(part):
                sent += s.send(part[sent:])
        # Só a primeira linha da resposta interessa (o status)
        reply = b""
        while b"\r\n" not in reply:
            chunk = s.recv(64)
            if not chunk:
                break
            reply += chunk
    finally:
        s.close()
    status = reply.split(b"\r\n")[0]
    print("WIFI,post,%s" % status.decode())
    return b" 200 " in status + b" "


def send(log, led=None):
    cfg = _read_config()
    ip, port = cfg["server_ip"], int(cfg["server_port"])
    print("WIFI,starting,http://%s:%d/result" % (ip, port))

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    attempt = 0
    while True:
        if not wlan.isconnected():
            try:
                wlan.disconnect()
            except OSError:
                pass
            try:
                wlan.connect(cfg["ssid"], cfg["password"])
            except OSError as e:
                print("WIFI,error,%s" % e)
            _wait_blinking(led, 10000, wlan)

        if wlan.isconnected():
            attempt += 1
            print("WIFI,attempt,%d" % attempt)
            try:
                if _post(ip, port, log + "SEND,%d\n" % time.ticks_ms()):
                    break
            except OSError as e:
                print("WIFI,error,%s" % e)
            _wait_blinking(led, 3000)  # o servidor não respondeu; tenta de novo daqui a 3 s
        else:
            print("WIFI,no connection to %s" % cfg["ssid"])

    if led is not None:
        led.value(0)
    wlan.disconnect()
    wlan.active(False)
    print("WIFI,sent")
