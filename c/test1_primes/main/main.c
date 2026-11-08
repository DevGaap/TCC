/* Teste 1 (CPU com inteiros), em C (ESP-IDF) */
#include "measurement.h"
#include "workloads.h"

static const test_t TEST = {1, "primes", NULL, primes_run};

void app_main(void)
{
    measurement_run(&TEST);
}
