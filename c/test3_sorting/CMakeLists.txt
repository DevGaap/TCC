# Teste 3 (memória), em C (ESP-IDF)
cmake_minimum_required(VERSION 3.16)

# Código e configurações que os três testes compartilham ficam em c/common
set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../common")
set(SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_LIST_DIR}/../common/sdkconfig.defaults")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(test3_sorting)
