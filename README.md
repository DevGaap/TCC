# TCC: análise comparativa de C e MicroPython no ESP32

**Tema:** *Análise comparativa de C e MicroPython no desenvolvimento de aplicações para o ESP32:
características, vantagens e limitações.*

Este documento registra como o projeto está montado: hardware, ambientes, testes, método de
medição, como executar uma rodada, formato dos dados e pendências.

> **Convenção do projeto:** nomes de pastas e arquivos sempre em inglês. Comentários no código
> e documentação em português.

---

## Guia rápido: do clone à primeira rodada

Resumo para quem está começando numa máquina nova (Windows). Os detalhes estão nas seções
indicadas.

**1. Instale as ferramentas**

| O quê | Para quê | Como |
|---|---|---|
| Git | baixar o projeto | `winget install Git.Git` |
| Python 3 | MicroPython (gravação) e scripts de análise | `winget install Python.Python.3.12` |
| ESP-IDF v6.1 | compilar e gravar os testes em C | pelo **EIM (ESP-IDF Installation Manager)** da Espressif, com os caminhos padrão (`C:\esp` e `C:\Espressif`) |
| Driver CH9102 | o Windows reconhecer a placa na USB | o Windows 11 costuma instalar sozinho; se a placa não aparecer como COM, instale o driver da WCH |

O `run_test.ps1` ativa o ESP-IDF por `C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1`.
Se você instalou em outro lugar ou em outra versão, ajuste essa linha do script (seção 3.1).

**2. Baixe o projeto e crie o ambiente Python**

```powershell
git clone https://github.com/DevGaap/TCC.git tcc
cd tcc
python -m venv micropython\.venv
micropython\.venv\Scripts\python.exe -m pip install esptool mpremote mpy-cross opencv-python
```

**3. Configure a rede**

```powershell
copy wifi_config.example.json wifi_config.json
```

Preencha `ssid`, `password` (rede **2,4 GHz**), `server_ip` (IP do notebook) e `server_port`, e
libere a porta no firewall (seção 5). O `wifi_config.json` está no `.gitignore` e nunca vai para
o repositório.

**4. Confira a porta da placa**

Ligue a placa na USB e veja a porta COM no Gerenciador de Dispositivos (aqui é `COM3`). Se for
outra, passe `-Port COMx` nos comandos abaixo.

**5. Rode um teste**

```powershell
.\tools\run_test.ps1 -Language c -Test 1             # C, teste 1 (primos)
.\tools\run_test.ps1 -Language micropython -Test 1   # MicroPython, teste 1
```

O script compila, grava a placa (no MicroPython ele grava o firmware sozinho se precisar) e abre
o servidor esperando o resultado. A partir daí, siga a seção 6.1: tire a USB, comece a filmar e
ligue a placa na fonte. Para transformar o vídeo em energia, veja a seção 6.2.

**Só testar se a placa funciona:** os projetos `c/blink` e `micropython/blink` piscam o LED.

```powershell
. C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1
cd c\blink; idf.py build; idf.py -p COM3 flash
```

---

## 1. Hardware

| Item | Valor |
|---|---|
| Placa | DevKit ESP32 com chip **ESP32-D0WD-V3 (revisão 3.1)** |
| CPU | Xtensa LX6 dual core, até 240 MHz |
| Flash | 4 MB |
| Conversor USB-serial | **CH9102** |
| Porta no notebook | **COM3** |
| LED da placa | GPIO2 (usado como marcador do teste) |
| Alimentação nas medições | fonte de bancada 5 V → medidor USB **Exbom UTS-10** → placa |

---

## 2. Estrutura do projeto

```
tcc/
├── README.md
├── wifi_config.json            ← rede, senha, IP e porta do notebook (C e MicroPython leem daqui)
├── c/
│   ├── common/                 ← componente ESP-IDF compartilhado pelos 3 testes
│   │   ├── test_config.h       ← duração, pausas e tamanho das cargas
│   │   ├── sdkconfig.defaults  ← 240 MHz, -O2, watchdog, sem reset depois de gravar
│   │   ├── workloads.c/.h      ← as 3 cargas de trabalho
│   │   ├── measurement.c/.h    ← sequência da medição e registro das linhas
│   │   └── wifi_sender.c/.h    ← liga o Wi-Fi no fim e manda o registro ao notebook
│   ├── test1_primes/           ← programa do teste 1
│   ├── test2_matrices/         ← programa do teste 2
│   ├── test3_sorting/          ← programa do teste 3
│   └── blink/                  ← só para conferir o ambiente C
├── micropython/
│   ├── .venv/                  ← Python isolado: esptool, mpremote, pyserial, opencv
│   ├── firmware/               ← ESP32_GENERIC-20260824-v1.29.0.bin
│   ├── common/                 ← config.py, workloads.py, measurement.py, wifi_sender.py
│   ├── test1_primes/main.py
│   ├── test2_matrices/main.py
│   ├── test3_sorting/main.py
│   └── blink/main.py           ← só para conferir o ambiente MicroPython
├── tools/                      ← tudo o que roda no notebook
│   ├── run_test.ps1            ← grava a placa pela USB e abre o servidor
│   ├── wifi_server.py          ← recebe a rodada pelo Wi-Fi e salva em results/
│   ├── extract_frames.py       ← vídeo do medidor → quadros + tabela de leituras
│   ├── compute_energy.py       ← leituras ao longo do tempo → energia da rodada
│   └── summarize.py            ← todas as rodadas → tabelas do TCC
└── results/
    ├── c/
    │   ├── primes/
    │   │   ├── primes-1/       ← uma pasta por rodada, numerada (seção 7)
    │   │   ├── primes-2/
    │   │   └── ...
    │   ├── matrices/
    │   └── sorting/
    ├── micropython/            ← mesma estrutura do c/
    ├── summary.csv             ← gerado pelo summarize.py
    └── comparison.csv          ← gerado pelo summarize.py
```

---

## 3. Ambientes

### 3.1 C (ESP-IDF)

| Item | Valor |
|---|---|
| Framework | **ESP-IDF v6.1**, instalado pelo EIM (ESP-IDF Installation Manager) |
| Código do ESP-IDF | `C:\esp\v6.1\esp-idf` |
| Ferramentas | `C:\Espressif\tools` |
| Compilador | xtensa-esp-elf GCC 15.2.0 |
| Ativação (em cada terminal novo) | `. C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1` |

Uso manual, se precisar:

```powershell
. C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1
cd c\test1_primes
idf.py build
idf.py -p COM3 flash
idf.py -p COM3 monitor      # sair: Ctrl+]
```

Ao mudar o `c\common\sdkconfig.defaults`, apague o `sdkconfig` e a pasta `build` de cada teste
para que os valores novos valham na próxima compilação.

### 3.2 MicroPython

| Item | Valor |
|---|---|
| Firmware | **MicroPython v1.29.0** (ESP32_GENERIC, 24/08/2026), em `micropython\firmware\` |
| Ferramentas | `esptool` 5.6.0, `mpremote` 1.29.0, `pyserial` 3.5, `opencv-python` |
| Python | ambiente isolado em `micropython\.venv` |

Para recriar o ambiente:

```powershell
cd micropython
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install esptool mpremote mpy-cross opencv-python
```

> Gravar um programa em C apaga o MicroPython da placa, e vice-versa. O `run_test.ps1` cuida
> disso sozinho.

---

## 4. Os testes

Os algoritmos são **idênticos** nas duas linguagens (mesmo código, mesma ordem das operações,
mesmos dados). Cada execução devolve um *checksum*, que tem que ser igual em C e em MicroPython.

| Nº | Programa | O que exercita | Carga | Checksum |
|---|---|---|---|---|
| 1 | `test1_primes` | CPU com **inteiros** | conta os primos até 10.000 por divisão por tentativa | **1229** |
| 2 | `test2_matrices` | CPU com **ponto flutuante** (float 32 bits) | multiplica duas matrizes 32×32 | **795024** |
| 3 | `test3_sorting` | **memória** (alocação, leitura e escrita) | gera 1.000 inteiros, ordena com *insertion sort* e confere | **4714011** |

O checksum do teste 2 dá 795023 no Python do computador, porque lá o float é de 64 bits. No
ESP32, as duas linguagens usam float de 32 bits e dão 795024.

Os dados vêm de um gerador pseudoaleatório simples (LCG do ZX81:
`x = (x × 75 + 74) mod 65537`, semente 12345), que mantém os números pequenos para o
MicroPython não alocar inteiros grandes.

### 4.1 Sequência de uma rodada

```
liga na fonte → parada 10 s → TESTE 300 s (LED aceso) → parada 10 s → DONE
             → liga o Wi-Fi → envia ao notebook (LED piscando rápido) → desliga o Wi-Fi
```

- A carga é repetida sem parar por **300 s** (duração fixa). No fim, a placa calcula quantas
  execuções couberam, a média, o mínimo, o máximo e o desvio padrão (algoritmo de Welford).
- O **LED fica aceso só durante o teste**. No vídeo, é ele que marca o começo e o fim.
- As paradas de 10 s servem para medir o **consumo de base** (placa ligada sem fazer nada).
- O **Wi-Fi fica desligado durante toda a medição**. Ele só é ligado depois do DONE, então o
  consumo do rádio, que é alto e oscila, não entra no teste.

Por que duração fixa e não um número fixo de repetições: o C é dezenas de vezes mais rápido. Com
o mesmo número de repetições, ele terminaria em milissegundos. Com a mesma duração, as duas
linguagens têm a mesma janela de medição, e a **energia por execução** (energia ÷ execuções)
fica comparável.

### 4.2 Parâmetros

Ficam em `c/common/test_config.h` e `micropython/common/config.py`. **Os dois precisam ter os
mesmos valores.**

| Parâmetro | Padrão | Significado |
|---|---|---|
| `TEST_DURATION_S` | 300 | segundos que o teste fica repetindo a carga |
| `IDLE_BEFORE_S` | 10 | parada antes do teste |
| `IDLE_AFTER_S` | 10 | parada depois do teste |
| `USE_LED_MARKER` | ligado | acende o GPIO2 durante o teste |
| `PRIMES_LIMIT` | 10000 | tamanho do teste 1 |
| `MATRIX_N` | 32 | tamanho do teste 2 |
| `SORT_N` | 1000 | tamanho do teste 3 |
| frequência da CPU | 240 MHz | C: `c/common/sdkconfig.defaults`; MicroPython: `CPU_FREQ_MHZ` |

### 4.3 Decisões para uma comparação justa

| Decisão | Motivo |
|---|---|
| **240 MHz nas duas linguagens** | aumenta o processamento e o consumo, como sugerido pelo orientador |
| C com **`-O2`** | o padrão do ESP-IDF é `-Og` (depuração), que deixaria o C artificialmente lento |
| C com **`-ffp-contract=off`** | impede o FMA, para as contas com float darem o mesmo resultado do MicroPython |
| Watchdog da tarefa ociosa da CPU0 desligado no C | o teste ocupa a CPU0 sem pausa |
| Um núcleo nas duas linguagens | o código roda numa tarefa só; o segundo núcleo fica parado nos dois casos |
| Coleta de lixo do MicroPython incluída | faz parte do comportamento real da linguagem |
| Algoritmos escritos à mão | o `list.sort()` do MicroPython é feito em C; usar ele seria medir C contra C |
| Fonte própria, sem a USB do notebook | a USB do notebook é instável (sugestão do orientador) |
| Wi-Fi só depois da medição | o rádio consome muito e de forma irregular |

---

## 5. Preparação (uma vez)

1. Copie o `wifi_config.example.json` para `wifi_config.json` e preencha: `ssid`, `password`, `server_ip` (IP do notebook nessa
   rede; o servidor mostra os IPs dele ao abrir) e `server_port`. A rede tem que ser de
   **2,4 GHz**, porque o ESP32 não conecta em 5 GHz.
2. Libere a porta no firewall do Windows (PowerShell **como administrador**):

   ```powershell
   New-NetFirewallRule -DisplayName "TCC ESP32 Wi-Fi" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
   ```

   A rede precisa estar como **Privada** no Windows. Para conferir, abra
   `http://<ip_do_notebook>:8080/` no celular, na mesma rede, com o servidor rodando.

Se o IP do notebook mudar (outra rede, por exemplo), corrija o `wifi_config.json` e grave a placa
de novo. O servidor avisa quando o IP do arquivo não é o do notebook.

---

## 6. Executar uma rodada

### 6.1 Gravar e medir

```powershell
cd <pasta-do-projeto>
.\tools\run_test.ps1 -Language c -Test 1
```

| Para executar | Comando |
|---|---|
| teste 1 em C / MicroPython | `.\tools\run_test.ps1 -Language c -Test 1` / `-Language micropython -Test 1` |
| teste 2 em C / MicroPython | `.\tools\run_test.ps1 -Language c -Test 2` / `-Language micropython -Test 2` |
| teste 3 em C / MicroPython | `.\tools\run_test.ps1 -Language c -Test 3` / `-Language micropython -Test 3` |

Opções: `-Port COM4` e `-Suffix 160mhz` (vai no nome do teste: `results/c/primes-160mhz/`). Se o
PowerShell bloquear o script, rode antes `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

1. O script grava a placa pela USB e abre o servidor. A placa **não** começa o teste sozinha.
2. **Tire o cabo USB do notebook.**
3. Posicione o celular para filmar **o visor do medidor e o LED da placa juntos**, com o celular
   parado (num suporte), sem reflexo no visor. **Comece a filmar.**
4. Ligue **fonte → medidor → placa**. Isso liga a placa e começa a rodada.
5. LED aceso fixo (uns 10 s depois): o teste começou. Não precisa anotar nada, o vídeo registra.
6. LED apagou (5 min depois): o teste acabou. Espere mais uns 10 s (parada final) e pare o vídeo.
7. LED piscando rápido: a placa está enviando. Quando apaga de vez, o servidor mostra a rodada
   salva em `results/<linguagem>/<teste>/<teste>-<n>/` (ex.: `results/c/primes/primes-1/`).

### 6.2 Registrar a potência ao longo do tempo

Como pediu o orientador, a potência é registrada durante a rodada inteira, e não lida uma vez só.
O vídeo é transformado numa tabela de leituras:

1. Copie o vídeo para a pasta da rodada com o nome `<rodada>_video.mp4` (ex.: `c-primes-1_video.mp4`).
2. Extraia os quadros:

   ```powershell
   micropython\.venv\Scripts\python.exe tools\extract_frames.py results\c\primes\primes-1
   ```

   Isso gera `frames/` (um quadro por segundo), `sheets/` (20 quadros por folha, para ler mais
   rápido) e `c-primes-1_power.csv` com a coluna de tempo já preenchida.
   Opções úteis: `--crop x,y,largura,altura` (recorta só o visor) e `--led x,y,largura,altura`
   (região do LED; o script detecta sozinho quando ele acendeu e sugere o `--start-at`).
3. Preencha no `c-primes-1_power.csv` a tensão (`voltage_v`) e a corrente (`current_a`) de cada
   quadro. O `charge_mah` é opcional e serve para conferir. Tanto `0.07` quanto `0,07` funcionam.
   Também dá para mandar as folhas para o Claude ler e preencher.
4. Calcule a energia, informando o segundo do vídeo em que o LED acendeu:

   ```powershell
   micropython\.venv\Scripts\python.exe tools\compute_energy.py results\c\primes\primes-1 --start-at 12.0
   ```

5. Depois de várias rodadas, monte as tabelas:

   ```powershell
   micropython\.venv\Scripts\python.exe tools\summarize.py
   ```

**Recomendação:** pelo menos 5 rodadas de cada teste em cada linguagem, para ter média e desvio
padrão entre rodadas.

**Fazer as 5 rodadas sem gravar de novo:** o programa continua na placa, e cada vez que ela é
ligada na fonte faz uma rodada nova. Então grave uma vez com o `run_test.ps1` e, depois da
primeira rodada, deixe o servidor aberto sem `--once`
(`micropython\.venv\Scripts\python.exe tools\wifi_server.py`). Para cada rodada seguinte:
desligue a placa, comece a filmar e ligue de novo. O servidor numera sozinho (`primes-2`,
`primes-3`…). Espere o LED parar de piscar antes de desligar, senão a rodada não chega.

Outras opções do `extract_frames.py`: `--every 0.5` (um quadro a cada meio segundo) e
`--video outro.mp4` (se a pasta tiver mais de um vídeo).

Sem vídeo, dá para calcular com uma leitura só do medidor (menos confiável, só para comparação):

```powershell
micropython\.venv\Scripts\python.exe tools\compute_energy.py <pasta_da_rodada> --voltage 4.80 --current 0.07 --charge-mah 20 --idle-current 0.05
```

### 6.3 Se algo der errado

- **Nada chegou no notebook:** ligue a placa pela USB e abra o monitor serial
  (`idf.py -p COM3 monitor` no C, `mpremote connect COM3` no MicroPython). As linhas `WIFI,...`
  mostram onde o envio parou (sem rede, servidor recusando etc.).
- **O servidor não estava aberto:** pode abrir depois. A placa continua tentando a cada poucos
  segundos até o servidor confirmar.
- **Receber várias rodadas sem gravar de novo:** abra o servidor sozinho, sem `--once`:
  `micropython\.venv\Scripts\python.exe tools\wifi_server.py` (para com Ctrl+C).
- **O servidor avisa que o IP não é do notebook:** corrija o `server_ip` no `wifi_config.json` e
  grave a placa de novo.

---

## 7. Arquivos de cada rodada

Cada rodada fica numa pasta própria, `results/<linguagem>/<teste>/<teste>-<n>/`. O `<n>` é o
número da rodada: o servidor sempre usa o próximo número livre, então nada é sobrescrito.
Os arquivos levam o nome completo da rodada (`<linguagem>-<teste>-<n>`), para não se confundirem
se forem copiados para outro lugar.

| Teste | Pastas das rodadas |
|---|---|
| 1 em C | `results/c/primes/primes-1/` … `primes-5/` |
| 2 em C | `results/c/matrices/matrices-1/` … `matrices-5/` |
| 3 em C | `results/c/sorting/sorting-1/` … `sorting-5/` |
| 1, 2 e 3 em MicroPython | `results/micropython/primes/primes-1/` etc. |
| com `-Suffix 160mhz` | `results/c/primes-160mhz/primes-160mhz-1/` |

O horário de cada rodada fica registrado dentro dela (`_log.txt`, `_events.csv` e `_notes.txt`).

| Arquivo (exemplo: teste 1 em C) | Gerado por | Conteúdo |
|---|---|---|
| `c-primes-1_log.txt` | `wifi_server.py` | todas as linhas recebidas, com o horário do notebook |
| `c-primes-1_results.csv` | `wifi_server.py` | execuções, tempos, checksum e memória |
| `c-primes-1_events.csv` | `wifi_server.py` | IDLE, START, END e DONE, com o horário e o ms da placa |
| `c-primes-1_notes.txt` | `wifi_server.py` | modelo para anotar a montagem e observações |
| `c-primes-1_video.mp4` | você | vídeo do medidor e do LED |
| `frames/`, `sheets/` | `extract_frames.py` | quadros do vídeo |
| `c-primes-1_power.csv` | `extract_frames.py` + você | leituras ao longo do tempo |
| `c-primes-1_energy.csv` | `compute_energy.py` | potência, energia e energia por execução |

### 7.1 Linhas que a placa envia

As duas linguagens geram exatamente o mesmo formato (o primeiro campo é o tipo da linha):

```
INFO,language,C
INFO,version,ESP-IDF v6.1
INFO,test,1;primes
INFO,cpu_mhz,240
INFO,free_heap,270140
INFO,test_duration_s,300
INFO,params,primes=10000;matrix=32;sorting=1000
INFO,run_id,b8ce0741
IDLE,<ms_desde_boot>,<segundos>
START,<teste>,<nome>,<ms_desde_boot>
END,<teste>,<ms_desde_boot>
RESULT,<linguagem>,<teste>,<nome>,<execuções>,<duração_ms>,<média_us>,<mín_us>,<máx_us>,<desvio_us>,<checksum>,<heap_antes>,<heap_depois>
IDLE,<ms_desde_boot>,<segundos>
DONE,<ms_desde_boot>
SEND,<ms_desde_boot>
```

Como os dados só chegam no fim, o servidor calcula o horário de cada evento pela linha SEND:
horário do evento = horário em que o POST chegou − (ms do SEND − ms do evento).

---

## 8. Como a energia é calculada

O `compute_energy.py` junta o registro de potência com os eventos da rodada. O alinhamento é
feito pelo LED: o `--start-at` diz em que segundo do vídeo o teste começou, e o resto vem do
relógio da placa (ms de cada evento).

| Métrica | Como é calculada |
|---|---|
| Potência em cada leitura | `P = V × I` |
| Energia do teste | integral de P entre START e END (regra do trapézio) |
| Potência ociosa | média de P nas duas paradas, sem o primeiro e o último segundo |
| Energia líquida | energia do teste − potência ociosa × duração: só o custo de processar |
| **Energia por execução** | energia ÷ execuções (mJ): **a métrica que compara as linguagens** |
| Conferência do mAh | integral da corrente comparada com o mAh acumulado pelo medidor |

Mesmo que a potência seja parecida nas duas linguagens, a energia por execução tende a ser bem
menor em C, porque cada execução termina muito antes.

O `summarize.py` grava o `results/summary.csv` (média e desvio padrão entre rodadas de cada teste)
e o `results/comparison.csv` (quantas vezes o MicroPython é mais lento e gasta mais energia por
execução que o C, em cada teste).

### 8.1 Limitações do medidor

- O UTS-10 mostra a corrente com 2 casas (0,07 A), ou seja, resolução de 10 mA, cerca de 14% de
  70 mA. Diferenças pequenas entre C e MicroPython podem ficar escondidas nessa resolução.
- Nas rodadas antigas, a corrente no visor (0,07 A) não batia com o mAh acumulado (cerca de 20 mAh
  em 5 min, o que daria 0,24 A). Com um ventilador (carga constante), o medidor bateu certinho.
  A suspeita é a corrente do ESP32 variar rápido demais para o visor. O registro ao longo do
  tempo, com a conferência do mAh, serve justamente para esclarecer isso.
- Se o vídeo não for suficiente, o próximo passo é um **sensor INA219 ou INA226** (corrente e
  tensão por I²C, resolução de cerca de 0,1 mA) ligado a um segundo microcontrolador. O
  `compute_energy.py` já aceita esse tipo de registro: basta um CSV com `pc_time` (horário do
  notebook) no lugar de `t_s`, e o alinhamento passa a ser automático, sem `--start-at`.
- A medição inclui a placa inteira (chip, regulador, conversor USB-serial e LEDs). Para o TCC isso
  serve, porque a comparação é relativa: o mesmo hardware é usado nas duas linguagens.

---

## 9. Problemas encontrados e soluções

| Problema | Solução |
|---|---|
| Erro de compilação: componente `spi_flash` faltando | adicionar os componentes usados em `PRIV_REQUIRES` no `CMakeLists.txt` |
| A soma do laço do blink estourava `uint32_t` | usar `uint64_t` no C (o MicroPython usa inteiros de tamanho arbitrário) |
| `mpremote` falhou com *could not enter raw repl* logo depois de gravar o firmware | a placa ainda estava reiniciando; o `run_test.ps1` espera e tenta de novo |
| Medidor não funcionava pela USB do notebook | alimentar por fonte própria e mandar os dados pelo Wi-Fi |
| Com os três testes no mesmo programa, só dava para ler o consumo total | um programa por teste, 300 s cada |
| Leitura única do medidor inconsistente (visor × mAh) e igual em C e MicroPython | registrar a potência ao longo do tempo pelo vídeo (seção 6.2) |
| Projeto dentro do OneDrive | o OneDrive sincroniza `build/` e `.venv/`, o que deixa a compilação lenta; se incomodar, excluir essas pastas da sincronização |

---

## 10. Histórico

Antes do método atual foram feitas três rodadas do teste 1: em C e em MicroPython pela USB do
notebook (03/11/2026) e em C pela fonte com Wi-Fi (04/11/2026). Os arquivos foram apagados
porque a energia delas não era confiável (seção 8.1). Os tempos continuam valendo como
referência (240 MHz, `-O2`):

| Teste 1 (primos) | Execuções em 300 s | Tempo médio | Desvio |
|---|---|---|---|
| C | 79.018 | 3.791 µs | 2 µs |
| MicroPython | 707 | 424.623 µs (~112× mais lento) | 3 µs |

Teste de ambiente (`blink`), 03/11/2026, a 160 MHz e com o C em `-Og`: laço de 1.000.000 de somas
em 182.689 µs no C e 11.134.965 µs no MicroPython; heap livre de 303.296 e 163.120 bytes.

---

## 11. Próximos passos

- [x] Testes 1, 2 e 3 escritos nas duas linguagens, com checksums conferidos
- [x] Alimentação por fonte e envio dos resultados por Wi-Fi
- [x] Ferramentas para registrar a potência pelo vídeo e calcular a energia
- [ ] Fazer uma rodada de teste com vídeo e conferir se a integral da corrente bate com o mAh
- [ ] Rodar os testes 1, 2 e 3 em C e em MicroPython, pelo menos 5 rodadas de cada
- [ ] Gerar as tabelas (`summarize.py`) e os gráficos do TCC
- [ ] (Se o vídeo não tiver resolução suficiente) montar o registrador com INA219/INA226
- [ ] (Opcional) Testar `@micropython.native` e `@micropython.viper` como meio-termo
- [ ] (Opcional) Comparar tamanho do firmware, uso de RAM, tempo de boot e de desenvolvimento

---

## 12. Referências

- ESP-IDF: https://docs.espressif.com/projects/esp-idf/
- MicroPython para ESP32: https://docs.micropython.org/en/latest/esp32/quickref.html
- Firmware MicroPython: https://micropython.org/download/ESP32_GENERIC/
- `mpremote`: https://docs.micropython.org/en/latest/reference/mpremote.html
- `esptool`: https://docs.espressif.com/projects/esptool/
