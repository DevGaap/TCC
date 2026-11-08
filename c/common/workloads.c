#include <stdlib.h>
#include "test_config.h"
#include "workloads.h"

#define LCG_SEED 12345u

/*
 * Gerador pseudoaleatório bem simples (o LCG do ZX81). Os números ficam abaixo de 65537,
 * e isso é de propósito: assim o MicroPython trabalha com inteiros pequenos e não precisa
 * alocar memória a cada número gerado.
 */
static inline uint32_t lcg_next(uint32_t x)
{
    return (x * 75u + 74u) % 65537u;
}

/* ---------- Teste 1: primos ---------- */

static int is_prime(uint32_t n)
{
    if (n < 2) {
        return 0;
    }
    if (n % 2 == 0) {
        return n == 2;
    }
    for (uint32_t d = 3; d * d <= n; d += 2) {
        if (n % d == 0) {
            return 0;
        }
    }
    return 1;
}

uint32_t primes_run(void)
{
    uint32_t total = 0;
    for (uint32_t n = 2; n <= PRIMES_LIMIT; n++) {
        if (is_prime(n)) {
            total++;
        }
    }
    return total;
}

/* ---------- Teste 2: matrizes ---------- */

static float matrix_a[MATRIX_N][MATRIX_N];
static float matrix_b[MATRIX_N][MATRIX_N];
static float matrix_r[MATRIX_N][MATRIX_N];

void matrices_prepare(void)
{
    uint32_t x = LCG_SEED;
    for (int i = 0; i < MATRIX_N; i++) {
        for (int j = 0; j < MATRIX_N; j++) {
            x = lcg_next(x);
            matrix_a[i][j] = (float)(x % 100) / 10.0f;
        }
    }
    for (int i = 0; i < MATRIX_N; i++) {
        for (int j = 0; j < MATRIX_N; j++) {
            x = lcg_next(x);
            matrix_b[i][j] = (float)(x % 100) / 10.0f;
        }
    }
}

uint32_t matrices_run(void)
{
    float total = 0.0f;
    for (int i = 0; i < MATRIX_N; i++) {
        for (int j = 0; j < MATRIX_N; j++) {
            float s = 0.0f;
            for (int k = 0; k < MATRIX_N; k++) {
                s += matrix_a[i][k] * matrix_b[k][j];
            }
            matrix_r[i][j] = s;
            total += s;
        }
    }
    return (uint32_t)total;
}

/* ---------- Teste 3: ordenação ---------- */

uint32_t sorting_run(void)
{
    /* O vetor é alocado a cada execução de propósito: o teste também mede a alocação */
    int32_t *v = malloc(SORT_N * sizeof(int32_t));
    if (v == NULL) {
        return 0;
    }

    uint32_t x = LCG_SEED;
    for (int i = 0; i < SORT_N; i++) {
        x = lcg_next(x);
        v[i] = (int32_t)x;
    }

    for (int i = 1; i < SORT_N; i++) {
        int32_t key = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > key) {
            v[j + 1] = v[j];
            j--;
        }
        v[j + 1] = key;
    }

    uint32_t checksum = 0;
    for (int i = 0; i < SORT_N; i++) {
        checksum = (checksum + (uint32_t)v[i] * (uint32_t)(i + 1)) & 0xFFFFFFu;
    }

    free(v);
    return checksum;
}
