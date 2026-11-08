#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "test_config.h"
#include "wifi_config_generated.h"  /* gerado pelo CMake a partir do wifi_config.json */
#include "wifi_sender.h"

#define CONNECTED_BIT BIT0
#define BLINK_MS 150

static EventGroupHandle_t s_events;

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(s_events, CONNECTED_BIT);
        esp_wifi_connect();  /* caiu ou não achou a rede: tenta de novo */
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(s_events, CONNECTED_BIT);
    }
}

static void wifi_start(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    s_events = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL));

    wifi_config_t wifi = {0};
    strncpy((char *)wifi.sta.ssid, WIFI_SSID, sizeof(wifi.sta.ssid));
    strncpy((char *)wifi.sta.password, WIFI_PASSWORD, sizeof(wifi.sta.password));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi));
    ESP_ERROR_CHECK(esp_wifi_start());
}

/*
 * Espera até `ms` piscando o LED (o pisca rápido quer dizer "enviando"). Se stop_on_connect
 * for true, sai assim que o Wi-Fi conectar. Devolve se está conectado.
 */
static bool wait_blinking(int ms, bool stop_on_connect)
{
    int level = 0;
    for (int t = 0; t < ms; t += BLINK_MS) {
        level = !level;
        gpio_set_level(LED_GPIO, level);
        vTaskDelay(pdMS_TO_TICKS(BLINK_MS));
        if (stop_on_connect && (xEventGroupGetBits(s_events) & CONNECTED_BIT)) {
            break;
        }
    }
    gpio_set_level(LED_GPIO, 0);
    return (xEventGroupGetBits(s_events) & CONNECTED_BIT) != 0;
}

static bool post(const char *body)
{
    esp_http_client_config_t cfg = {
        .url = SERVER_URL,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 5000,
    };
    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (client == NULL) {
        return false;
    }
    esp_http_client_set_header(client, "Content-Type", "text/plain; charset=utf-8");
    esp_http_client_set_post_field(client, body, strlen(body));
    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    printf("WIFI,post,%s,status=%d\n", esp_err_to_name(err), status);
    return err == ESP_OK && status == 200;
}

void wifi_sender_send(const char *log)
{
    printf("WIFI,starting,%s\n", SERVER_URL);
    wifi_start();

    size_t size = strlen(log) + 64;
    char *body = malloc(size);
    if (body == NULL) {
        printf("WIFI,error,out of memory\n");
        return;
    }

    int attempt = 0;
    while (1) {
        if (wait_blinking(10000, true)) {
            attempt++;
            snprintf(body, size, "%sSEND,%lld\n", log, esp_timer_get_time() / 1000);
            printf("WIFI,attempt,%d\n", attempt);
            if (post(body)) {
                break;
            }
            wait_blinking(3000, false);  /* o servidor não respondeu; tenta de novo daqui a 3 s */
        } else {
            printf("WIFI,no connection to %s\n", WIFI_SSID);
        }
    }

    free(body);
    gpio_set_level(LED_GPIO, 0);
    esp_wifi_stop();
    printf("WIFI,sent\n");
}
