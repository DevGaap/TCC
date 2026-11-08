/*
 * Cargas de trabalho dos testes. Cada função "run" faz o trabalho completo uma vez e
 * devolve um checksum, que tem que bater com o da versão em MicroPython.
 */
#pragma once
#include <stdint.h>

/* Teste 1: CPU com inteiros. Conta os primos até PRIMES_LIMIT. */
uint32_t primes_run(void);

/* Teste 2: CPU com ponto flutuante. Multiplica duas matrizes MATRIX_N x MATRIX_N. */
void matrices_prepare(void);
uint32_t matrices_run(void);

/* Teste 3: memória. Gera, ordena (insertion sort) e confere um vetor de SORT_N inteiros. */
uint32_t sorting_run(void);
