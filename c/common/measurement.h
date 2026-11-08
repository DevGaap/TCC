/*
 * Medição de um teste, usada pelos três programas em C.
 * Faz exatamente o mesmo que micropython/common/measurement.py e gera as mesmas linhas.
 */
#pragma once
#include <stdint.h>

typedef struct {
    int number;
    const char *name;
    void (*prepare)(void);   /* opcional; roda antes do teste e fica fora da medição */
    uint32_t (*run)(void);   /* faz a carga uma vez e devolve o checksum */
} test_t;

/*
 * Roda a sequência inteira:
 *   parada IDLE_BEFORE_S -> teste por TEST_DURATION_S (LED aceso) -> parada IDLE_AFTER_S -> DONE
 * Durante tudo isso o Wi-Fi fica desligado. Só depois do DONE ele é ligado para mandar os
 * resultados ao notebook (LED piscando rápido). Essa função não retorna.
 */
void measurement_run(const test_t *test);
