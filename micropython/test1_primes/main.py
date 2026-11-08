"""Teste 1 (primos, CPU com inteiros), em MicroPython."""
import config
import measurement
import workloads

measurement.run(1, "primes", None,
                lambda: workloads.primes_run(config.PRIMES_LIMIT))
