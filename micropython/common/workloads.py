"""
Cargas de trabalho dos testes, com os mesmos algoritmos de c/common/workloads.c.
Cada função "run" faz o trabalho completo uma vez e devolve um checksum, que tem que bater
com o da versão em C.

Nada aqui depende do ESP32, então dá para rodar no Python do computador também
(é assim que os checksums foram conferidos).
"""

LCG_SEED = 12345

# Gerador pseudoaleatório do ZX81: x = (x * 75 + 74) % 65537
# Os números ficam abaixo de 65537, então o MicroPython usa inteiros pequenos e não aloca nada.


# ---------- Teste 1: primos ----------

def _is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def primes_run(limit):
    total = 0
    for n in range(2, limit + 1):
        if _is_prime(n):
            total += 1
    return total


# ---------- Teste 2: matrizes ----------

_matrix_a = None
_matrix_b = None
_matrix_r = None


def matrices_prepare(n):
    global _matrix_a, _matrix_b, _matrix_r
    x = LCG_SEED
    a = []
    for _ in range(n):
        row = []
        for _ in range(n):
            x = (x * 75 + 74) % 65537
            row.append((x % 100) / 10)
        a.append(row)
    b = []
    for _ in range(n):
        row = []
        for _ in range(n):
            x = (x * 75 + 74) % 65537
            row.append((x % 100) / 10)
        b.append(row)
    _matrix_a = a
    _matrix_b = b
    _matrix_r = [[0.0] * n for _ in range(n)]


def matrices_run(n):
    a = _matrix_a
    b = _matrix_b
    r = _matrix_r
    total = 0.0
    for i in range(n):
        ai = a[i]
        ri = r[i]
        for j in range(n):
            s = 0.0
            for k in range(n):
                s += ai[k] * b[k][j]
            ri[j] = s
            total += s
    return int(total)


# ---------- Teste 3: ordenação ----------

def sorting_run(n):
    # A lista é criada a cada execução de propósito: o teste também mede a alocação
    v = [0] * n

    x = LCG_SEED
    for i in range(n):
        x = (x * 75 + 74) % 65537
        v[i] = x

    # insertion sort escrito à mão; o list.sort() é feito em C e estragaria a comparação
    for i in range(1, n):
        key = v[i]
        j = i - 1
        while j >= 0 and v[j] > key:
            v[j + 1] = v[j]
            j -= 1
        v[j + 1] = key

    checksum = 0
    for i in range(n):
        checksum = (checksum + v[i] * (i + 1)) & 0xFFFFFF
    return checksum
