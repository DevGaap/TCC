# MicroPython: rodada do teste 2 não era enviada (`WiFi Out of Memory`)

Registro do problema encontrado em 08/11/2026, no teste 2 (matrizes) em MicroPython, e de como
foi resolvido. Serve de material para o TCC (limitações do MicroPython / gerenciamento de memória).

Ambiente: ESP32-D0WD-V3, firmware `ESP32_GENERIC-20260824-v1.29.0`, CPU a 240 MHz, sem PSRAM.

---

## 1. O que aconteceu

- O teste 1 (primos) em MicroPython rodou e enviou as 5 rodadas sem problema.
- No teste 2 (matrizes), a primeira rodada (ligada por volta de 12:15) rodou os 5 minutos
  normalmente: LED aceso durante o teste, apagou no fim. Mas o LED **nunca piscou** (envio pelo
  Wi-Fi) e o servidor não recebeu nada.
- Essa rodada se perdeu: o registro só existia na RAM da placa.

## 2. Diagnóstico

Ligando a placa na USB e rodando o teste encurtado (10 s) pelo `mpremote`, apareceu o erro:

```
DONE,34762
WIFI,starting,http://192.168.0.19:8080/result
Traceback (most recent call last):
  File "main.py", line 8, in <module>
  File "measurement.py", line 121, in run
  File "wifi_sender.py", line 67, in send
OSError: WiFi Out of Memory
```

A linha 67 é o `wlan.active(True)`: o driver do Wi-Fi não conseguiu alocar memória para ligar.
O teste em si funcionou (checksum 795024, igual ao C).

### 2.1 Medições de memória

Foram medidas as duas memórias da placa:

- **heap do MicroPython** (`gc.mem_alloc() + gc.mem_free()`), onde ficam os objetos Python;
- **heap do sistema (ESP-IDF)** (`esp32.idf_heap_info(esp32.HEAP_DATA)`), de onde o driver do
  Wi-Fi tira a memória dele.

| Momento | IDF livre (soma) | IDF maior bloco livre | Heap MicroPython |
|---|---|---|---|
| Placa recém-ligada | 141.996 B | 110.592 B | total 166.592 B, livre 158.864 B |
| Depois de ~5 s de matrizes (11 execuções) | 82.600 B | 53.248 B | total 165.248 B |
| Depois de liberar as matrizes e `gc.collect()` | 82.600 B (não mudou) | 53.248 B | livre 102.880 B (`micropython.mem_info`) |
| Depois de 10 s de teste + falha do Wi-Fi | **18.488 B** | **6.144 B** | livre 160.288 B (após `gc.collect()`) |
| Depois de um **soft reset** | 141.996 B | 110.592 B | volta ao normal |

Em 5 s de teste, o heap do sistema perdeu cerca de 60 KB, e em 10 s ficou com cerca de 18 KB
livres, com o maior bloco de 6 KB. O Wi-Fi precisa de bem mais que isso para ligar.

Liberar os objetos do Python (`gc.collect()`) **não devolve** essa memória ao sistema: o heap do
MicroPython fica com bastante espaço livre, mas o IDF continua sem. Só o soft reset devolveu.

### 2.2 Interpretação

O port ESP32 do MicroPython (v1.29) aumenta o próprio heap sob demanda, pegando blocos da RAM
do sistema (o `micropython.mem_info()` mostra `max new split: 53248`, o tamanho do próximo
bloco que ele pode pegar). Pelos dados, esses blocos não voltam para o sistema durante a
execução do programa, mesmo vazios.

O teste de matrizes cria um `float` novo (um objeto alocado no heap) a cada multiplicação e
soma: são 32 × 32 × 32 = 32.768 por execução. Esse lixo constante faz o heap crescer até
ocupar quase toda a RAM do sistema. No teste de primos isso não aparece: os inteiros pequenos
do MicroPython não são alocados no heap.

### 2.3 Comparação com o C

| Teste | Linguagem | Heap livre antes | Heap livre depois |
|---|---|---|---|
| Primos | C | 270.140 B | 270.140 B |
| Primos | MicroPython | 158.944 B | 139.120 B |
| Matrizes | C | 261.948 B | 261.948 B |
| Matrizes | MicroPython (10 s) | 110.176 B | 85.888 B |
| Matrizes | MicroPython (20 s) | 110.016 B | 73.584 B |

No C, a memória não muda durante o teste: as matrizes são vetores fixos e as contas usam a FPU
direto, sem alocação nenhuma. No MicroPython, as próprias matrizes já ocupam cerca de 48 KB
(158.864 → 110.176 B livres), porque cada elemento é um objeto `float` dentro de uma lista.

## 3. Solução

Em [`micropython/common/measurement.py`](../micropython/common/measurement.py):

1. Depois do DONE (a medição já acabou), a placa grava o registro da rodada na flash, em
   `pending_send.txt`. A primeira linha do arquivo é o `ticks_ms` do momento da gravação.
2. Faz `machine.soft_reset()`, que reinicia a VM do MicroPython e devolve toda a RAM ao sistema.
3. O `main.py` roda de novo, encontra o arquivo pendente, liga o Wi-Fi (agora com memória),
   envia, apaga o arquivo e para (não roda o teste de novo).

Detalhes:

- **A medição não muda**: tudo acontece depois do DONE, fora do intervalo medido.
- O `ticks_ms` **não zera no soft reset** (medido: 54.105 ms antes, 54.685 ms depois), então o
  `SEND` continua no mesmo relógio dos outros eventos e o servidor calcula os horários certos.
- Se a placa for desligada no meio do envio, o relógio recomeça do zero na próxima vez. O código
  percebe isso (o `ticks_ms` atual fica menor que o salvo), guarda o arquivo antigo em
  `unsent_send.txt` e roda o teste normalmente.

### 3.1 Teste da correção

Rodada de 20 s (com paradas de 2 s), sem cabo USB no meio, enviada para um servidor separado
(`--suffix fixtest`, apagado depois):

```
RESULT,MicroPython,2,matrices,46,20054,435801,392964,483034,41361,795024,110016,73584
IDLE,22363,2
DONE,24363
MPY: soft reboot
WIFI,starting,http://192.168.0.19:8080/result
WIFI,attempt,1
WIFI,post,HTTP/1.0 200 OK
WIFI,sent
```

O `SEND` chegou com 28.900 ms, 4,5 s depois do DONE, o que inclui o soft reset e a conexão ao
Wi-Fi.

## 4. Observação extra: variação causada pelo coletor de lixo

Nos testes curtos de matrizes em MicroPython, o tempo de cada execução variou bem mais que no C:

| Rodada | Execuções | Média | Mín | Máx | Desvio |
|---|---|---|---|---|---|
| MicroPython, 10 s | 21 | 477.671 µs | 436.707 µs | 483.244 µs | 9.874 µs |
| MicroPython, 20 s | 46 | 435.801 µs | 392.964 µs | 483.034 µs | 41.361 µs |
| C, 300 s (rodadas oficiais) | 164.285 | 1.820 µs | 1.816 µs | 1.833 µs | 2 µs |

A diferença entre o mínimo e o máximo (~90 ms) é compatível com execuções em que o coletor de
lixo entrou para limpar os `float`. Nos primos em MicroPython, sem alocação, o desvio foi de 4 µs.

### 4.1 Confirmação nas rodadas oficiais (300 s, 08/11/2026)

As 5 rodadas oficiais de matrizes em MicroPython foram enviadas sem erro, já com a correção:

| Rodada | Execuções | Média (µs) | Mín (µs) | Máx (µs) | Desvio interno (µs) | Heap livre antes → depois (B) |
|---|---|---|---|---|---|---|
| 1 | 748 | 401.229 | 392.922 | 483.084 | 18.649 | 110.016 → 20.112 |
| 2 | 754 | 397.998 | 392.971 | 483.022 | 9.764 | 110.016 → 41.056 |
| 3 | 750 | 400.320 | 392.942 | 483.037 | 16.699 | 110.016 → 53.984 |
| 4 | 751 | 399.339 | 392.958 | 483.003 | 14.226 | 110.016 → 52.208 |
| 5 | 755 | 397.555 | 392.949 | 482.962 | 7.714 | 110.016 → 53.696 |
| **Média** | **751,6 ± 2,9** | **399.288 ± 1.541** (CV 0,39%) | | | | |

- O **mínimo é sempre ~392,9 ms** (execução sem coleta de lixo) e o **máximo é sempre ~483 ms**
  (execução com coleta): cada coleta custa uns 90 ms.
- O que varia entre rodadas é **quantas vezes** o coletor entra. Por isso o desvio interno vai
  de 7,7 a 18,6 ms, e a rodada mais lenta (1) foi a que terminou com menos heap livre.
- É a primeira carga em que rodadas iguais deram números diferentes. Primos (C e MicroPython) e
  matrizes em C deram exatamente o mesmo resultado nas 5 rodadas.
- Em C, as matrizes deram 164.285 execuções e 1.820 µs em todas as rodadas: o MicroPython foi
  ~219× mais lento (nos primos, ~112×).
- A corrente no display da fonte foi 0,07 A no teste nas duas linguagens (0,04 A parado).

## 5. Para o TCC

- É um exemplo concreto de **limitação do MicroPython**: o gerenciamento automático de memória
  (objetos alocados no heap + coletor de lixo + heap que cresce e não devolve RAM) pode deixar o
  sistema sem memória para outros recursos, como o Wi-Fi, mesmo com o programa "certo".
- No C o problema não existe, porque o programador controla a memória e as matrizes ficam em
  vetores fixos.
- A solução (salvar e reiniciar antes de usar o Wi-Fi) funciona, mas é um contorno que o
  desenvolvedor só descobre depois do erro e exige conhecer detalhes internos do port.
