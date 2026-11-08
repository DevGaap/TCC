/*
 * Configuração dos testes (vale para os três programas em C).
 * Os valores precisam ser os mesmos de micropython/common/config.py.
 * A frequência da CPU não fica aqui, e sim no sdkconfig.defaults.
 */
#pragma once

/*
 * Quanto tempo o teste fica repetindo a carga. Tem que ser longo para o medidor ter
 * bastante tempo de leitura: 300 s dão uns 300 quadros se o vídeo for lido a 1 por segundo.
 */
#define TEST_DURATION_S     300

#define IDLE_BEFORE_S       10   /* placa parada antes do teste, para medir o consumo de base */
#define IDLE_AFTER_S        10   /* e depois do teste também */

#define USE_LED_MARKER      1    /* LED do GPIO2 aceso só enquanto o teste roda */
#define LED_GPIO            2

/* Tamanho das cargas de trabalho */
#define PRIMES_LIMIT        10000
#define MATRIX_N            32
#define SORT_N              1000
