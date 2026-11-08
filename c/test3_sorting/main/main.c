/* Teste 3 (memória), em C (ESP-IDF) */
#include "measurement.h"
#include "workloads.h"

static const test_t TEST = {3, "sorting", NULL, sorting_run};

void app_main(void)
{
    measurement_run(&TEST);
}
