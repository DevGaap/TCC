/* Teste 2 (CPU com ponto flutuante), em C (ESP-IDF) */
#include "measurement.h"
#include "workloads.h"

static const test_t TEST = {2, "matrices", matrices_prepare, matrices_run};

void app_main(void)
{
    measurement_run(&TEST);
}
