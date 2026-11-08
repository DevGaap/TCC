/*
 * Programa simples para conferir o ambiente C (ESP-IDF):
 *  - mostra algumas informações do chip na serial;
 *  - mede quanto tempo leva um laço de 1.000.000 de somas;
 *  - fica piscando o LED da placa (GPIO2) a cada 500 ms.
 */
#include <stdio.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_system.h"
#include "esp_timer.h"

#define LED_GPIO GPIO_NUM_2
#define BLINK_INTERVAL_MS 500

static void print_chip_info(void)
{
    esp_chip_info_t info;
    uint32_t flash_size = 0;

    esp_chip_info(&info);
    esp_flash_get_size(NULL, &flash_size);

    printf("\n=== Teste ESP32 em C (ESP-IDF) ===\n");
    printf("Nucleos: %d | Revisao: %d\n", info.cores, info.revision);
    printf("Flash: %" PRIu32 " MB\n", flash_size / (1024 * 1024));
    printf("Heap livre: %" PRIu32 " bytes\n", esp_get_free_heap_size());
}

static void loop_benchmark(void)
{
    /* volatile para o compilador não sumir com o laço inteiro */
    volatile uint64_t sum = 0;
    int64_t start = esp_timer_get_time();

    for (uint32_t i = 0; i < 1000000; i++) {
        sum += i;
    }

    int64_t end = esp_timer_get_time();
    printf("Laco de 1.000.000 iteracoes: %lld us (soma=%" PRIu64 ")\n", end - start, sum);
}

void app_main(void)
{
    print_chip_info();
    loop_benchmark();

    gpio_reset_pin(LED_GPIO);
    gpio_set_direction(LED_GPIO, GPIO_MODE_OUTPUT);

    uint8_t state = 0;
    uint32_t counter = 0;

    while (1) {
        state = !state;
        gpio_set_level(LED_GPIO, state);
        printf("[%" PRIu32 "] LED %s\n", counter++, state ? "LIGADO" : "DESLIGADO");
        vTaskDelay(pdMS_TO_TICKS(BLINK_INTERVAL_MS));
    }
}
