"""Teste 2 (matrizes, CPU com ponto flutuante), em MicroPython."""
import config
import measurement
import workloads

measurement.run(2, "matrices",
                lambda: workloads.matrices_prepare(config.MATRIX_N),
                lambda: workloads.matrices_run(config.MATRIX_N))
