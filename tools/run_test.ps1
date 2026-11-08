<#
.SYNOPSIS
  Grava um teste no ESP32 pela USB e deixa o servidor esperando os resultados pelo Wi-Fi.

.DESCRIPTION
  1. Grava o programa pela USB. A placa NÃO começa o teste ainda (o C fica parado no
     bootloader e o MicroPython fica no REPL).
  2. Você tira a USB e liga a placa na fonte, com o medidor no meio.
  3. A placa faz o teste com o Wi-Fi desligado e, no fim, manda os resultados para o
     servidor, que este script deixa aberto até a rodada chegar.

.EXAMPLE
  .\tools\run_test.ps1 -Language c -Test 1
  .\tools\run_test.ps1 -Language micropython -Test 3
  .\tools\run_test.ps1 -Language c -Test 2 -Suffix 160mhz
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet("c", "micropython")][string]$Language,
    [Parameter(Mandatory = $true)][ValidateSet(1, 2, 3)][int]$Test,
    [string]$Port = "COM3",
    [string]$Suffix = ""   # vai no nome do teste: c-primes-160mhz
)

$root = Split-Path -Parent $PSScriptRoot
$folders = @{ 1 = "test1_primes"; 2 = "test2_matrices"; 3 = "test3_sorting" }
$folder = $folders[$Test]
$venv = Join-Path $root "micropython\.venv\Scripts"
$python = Join-Path $venv "python.exe"
$wifiConfig = Join-Path $root "wifi_config.json"

$cfg = Get-Content $wifiConfig -Raw | ConvertFrom-Json
if ($cfg.ssid -eq "NETWORK_NAME") {
    throw "Preencha o wifi_config.json (rede, senha e IP do notebook) antes de gravar."
}

if ($Language -eq "c") {
    . C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1 *> $null
    Push-Location (Join-Path $root "c\$folder")
    try {
        idf.py build
        if ($LASTEXITCODE -ne 0) { throw "Falha na compilação de c\$folder" }
        idf.py -p $Port flash
        if ($LASTEXITCODE -ne 0) { throw "Falha ao gravar na $Port" }
    }
    finally { Pop-Location }
}
else {
    $mpremote = Join-Path $venv "mpremote.exe"

    # Se a placa não responder como MicroPython (por exemplo, está com um programa em C),
    # grava o firmware de novo
    $hasMicroPython = $false
    foreach ($attempt in 1..2) {
        & $mpremote connect $Port exec "print('ok')" *> $null
        if ($LASTEXITCODE -eq 0) { $hasMicroPython = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $hasMicroPython) {
        Write-Host "MicroPython não encontrado na placa; gravando o firmware..."
        $esptool = Join-Path $venv "esptool.exe"
        $firmware = Get-ChildItem (Join-Path $root "micropython\firmware\*.bin") | Select-Object -First 1
        & $esptool --port $Port erase-flash
        if ($LASTEXITCODE -ne 0) { throw "Falha ao apagar a flash" }
        & $esptool --port $Port --baud 460800 write-flash 0x1000 $firmware.FullName
        if ($LASTEXITCODE -ne 0) { throw "Falha ao gravar o firmware MicroPython" }
        Start-Sleep -Seconds 5  # no primeiro boot ele cria o sistema de arquivos
    }

    $common = Join-Path $root "micropython\common"
    $files = @(
        "$common\config.py", "$common\workloads.py", "$common\measurement.py",
        "$common\wifi_sender.py", $wifiConfig, (Join-Path $root "micropython\$folder\main.py")
    )
    # Logo depois de gravar o firmware a placa pode ainda estar iniciando; tenta algumas vezes
    foreach ($attempt in 1..3) {
        & $mpremote connect $Port cp @files ":"
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 3
    }
    if ($LASTEXITCODE -ne 0) { throw "Falha ao copiar os arquivos para a placa" }
}

Write-Host ""
Write-Host "Programa gravado. A placa ainda NÃO está rodando o teste."
Write-Host "  1. Tire o cabo USB do notebook."
Write-Host "  2. Comece a filmar o medidor e o LED da placa juntos."
Write-Host "  3. Ligue: fonte -> medidor -> placa. Isso liga a placa e começa a rodada."
Write-Host "  4. LED aceso fixo (uns 10 s depois) = teste rodando."
Write-Host "  5. LED apagou (5 min depois) = fim do teste. Espere mais uns 10 s e pare o vídeo."
Write-Host "  6. LED piscando rápido = enviando pelo Wi-Fi. Apagou de vez = enviado."
Write-Host ""

$serverArgs = @((Join-Path $root "tools\wifi_server.py"), "--once")
if ($Suffix) { $serverArgs += @("--suffix", $Suffix) }
& $python @serverArgs
