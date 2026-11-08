"""Teste 3 (ordenação, memória), em MicroPython."""
import config
import measurement
import workloads

measurement.run(3, "sorting", None,
                lambda: workloads.sorting_run(config.SORT_N))
