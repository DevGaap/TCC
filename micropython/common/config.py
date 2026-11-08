"""
Configuração dos testes (vale para os três programas em MicroPython).
Os valores precisam ser os mesmos de c/common/test_config.h.
No C, a frequência da CPU fica em c/common/sdkconfig.defaults.
"""

CPU_FREQ_MHZ = 240

# Quanto tempo o teste fica repetindo a carga. Tem que ser longo para o medidor ter bastante
# tempo de leitura: 300 s dão uns 300 quadros se o vídeo for lido a 1 por segundo.
TEST_DURATION_S = 300

IDLE_BEFORE_S = 10  # placa parada antes do teste, para medir o consumo de base
IDLE_AFTER_S = 10   # e depois do teste também

USE_LED_MARKER = True  # LED do GPIO2 aceso só enquanto o teste roda
LED_GPIO = 2

# Tamanho das cargas de trabalho
PRIMES_LIMIT = 10000
MATRIX_N = 32
SORT_N = 1000
