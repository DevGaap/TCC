# Componente "common": o que os três programas de teste compartilham
# (cargas de trabalho, sequência de medição e envio dos resultados pelo Wi-Fi).
idf_component_register(SRCS "measurement.c" "workloads.c" "wifi_sender.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES esp_driver_gpio esp_timer esp_wifi esp_netif
                                     esp_event nvs_flash esp_http_client)

# Sem isso o compilador pode juntar multiplicação e soma numa instrução só (FMA), e as contas
# com float deixariam de dar exatamente o mesmo resultado do MicroPython.
target_compile_options(${COMPONENT_LIB} PRIVATE -ffp-contract=off)

# A rede e o IP do notebook ficam no wifi_config.json da raiz do projeto, o mesmo arquivo que o
# MicroPython usa. Aqui ele é lido e vira um .h com as constantes.
set(json_file "${CMAKE_CURRENT_LIST_DIR}/../../wifi_config.json")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${json_file}")
file(READ "${json_file}" json_text)
string(JSON wifi_ssid GET "${json_text}" ssid)
string(JSON wifi_password GET "${json_text}" password)
string(JSON server_ip GET "${json_text}" server_ip)
string(JSON server_port GET "${json_text}" server_port)

if(wifi_ssid STREQUAL "NETWORK_NAME")
    message(WARNING "o wifi_config.json ainda está com os valores de exemplo")
endif()

# Escapa aspas e barras para a senha não quebrar o #define
foreach(var wifi_ssid wifi_password)
    string(REPLACE "\\" "\\\\" ${var} "${${var}}")
    string(REPLACE "\"" "\\\"" ${var} "${${var}}")
endforeach()

file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/wifi_config_generated.h"
     "/* Gerado a partir do wifi_config.json. Não edite à mão. */\n"
     "#pragma once\n"
     "#define WIFI_SSID \"${wifi_ssid}\"\n"
     "#define WIFI_PASSWORD \"${wifi_password}\"\n"
     "#define SERVER_URL \"http://${server_ip}:${server_port}/result\"\n")
target_include_directories(${COMPONENT_LIB} PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
