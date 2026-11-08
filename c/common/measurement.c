/*
 * Sequência de medição. Cada linha é impressa na serial (útil para depurar com o cabo USB)
 * e também guardada em memória, para ser enviada pelo Wi-Fi quando a medição acabar.
 */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_idf_version.h"
#include "esp_random.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "test_config.h"
#include "wifi_sender.h"
#include "measurement.h"

#define LANGUAGE "C"
#define LOG_SIZE 4096

static char s_log[LOG_SIZE];
static size_t s_used = 0;

/* Imprime a linha e guarda uma cópia no registro que vai ser enviado no fim */
static void record(const char *fmt, ...)
{
    char line[256];
    va_list args;
    va_start(args, fmt);
    int n = vsnprintf(line, sizeof(line), fmt, args);
    va_end(args);
    if (n < 0) {
        return;
    }
    if ((size_t)n >= sizeof(line)) {
        n = sizeof(line) - 1;
    }

    printf("%s\n", line);
    if (s_used + n + 2 <= LOG_SIZE) {
        memcpy(s_log + s_used, line, n);
        s_used += n;
        s_log[s_used++] = '\n';
        s_log[s_used] = '\0';
    }
}

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

static void marker(int level)
{
#if USE_LED_MARKER
    gpio_set_level(LED_GPIO, level);
#endif
}

static void idle(int seconds)
{
    if (seconds <= 0) {
        return;
    }
    record("IDLE,%lld,%d", now_ms(), seconds);
    vTaskDelay(pdMS_TO_TICKS(seconds * 1000));
}

static void record_header(const test_t *t)
{
    record("INFO,language,%s", LANGUAGE);
    record("INFO,version,ESP-IDF %s", esp_get_idf_version());
    record("INFO,test,%d;%s", t->number, t->name);
    record("INFO,cpu_mhz,%d", CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ);
    record("INFO,free_heap,%" PRIu32, esp_get_free_heap_size());
    record("INFO,test_duration_s,%d", TEST_DURATION_S);
    record("INFO,params,primes=%d;matrix=%d;sorting=%d", PRIMES_LIMIT, MATRIX_N, SORT_N);
    /* Número aleatório para o servidor reconhecer se a mesma rodada chegar duas vezes */
    record("INFO,run_id,%08" PRIx32, esp_random());
}

static void run_test(const test_t *t)
{
    if (t->prepare != NULL) {
        t->prepare();
    }

    uint32_t heap_before = esp_get_free_heap_size();
    uint32_t iterations = 0;
    uint32_t checksum = 0;
    int64_t min_us = INT64_MAX;
    int64_t max_us = 0;
    double mean = 0.0;
    double m2 = 0.0;  /* Welford: média e desvio padrão sem guardar todas as amostras */

    record("START,%d,%s,%lld", t->number, t->name, now_ms());
    marker(1);

    int64_t start = esp_timer_get_time();
    int64_t limit = start + (int64_t)TEST_DURATION_S * 1000000;
    do {
        int64_t t0 = esp_timer_get_time();
        checksum = t->run();
        int64_t dt = esp_timer_get_time() - t0;

        iterations++;
        if (dt < min_us) {
            min_us = dt;
        }
        if (dt > max_us) {
            max_us = dt;
        }
        double delta = dt - mean;
        mean += delta / iterations;
        m2 += delta * (dt - mean);
    } while (esp_timer_get_time() < limit);
    int64_t duration_ms = (esp_timer_get_time() - start) / 1000;

    marker(0);
    record("END,%d,%lld", t->number, now_ms());

    double stdev = iterations > 1 ? sqrt(m2 / (iterations - 1)) : 0.0;
    record("RESULT,%s,%d,%s,%" PRIu32 ",%lld,%lld,%lld,%lld,%lld,%" PRIu32 ",%" PRIu32 ",%" PRIu32,
           LANGUAGE, t->number, t->name, iterations, duration_ms,
           llround(mean), min_us, max_us, llround(stdev),
           checksum, heap_before, esp_get_free_heap_size());
}

void measurement_run(const test_t *test)
{
#if USE_LED_MARKER
    gpio_reset_pin(LED_GPIO);
    gpio_set_direction(LED_GPIO, GPIO_MODE_OUTPUT);
    gpio_set_level(LED_GPIO, 0);
#endif

    record_header(test);
    idle(IDLE_BEFORE_S);
    run_test(test);
    idle(IDLE_AFTER_S);
    record("DONE,%lld", now_ms());

    /* Daqui para frente a medição já acabou, então o consumo do Wi-Fi não atrapalha */
    wifi_sender_send(s_log);

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
