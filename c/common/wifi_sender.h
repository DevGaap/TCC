#pragma once

/*
 * Liga o Wi-Fi, manda `log` (as linhas CSV da rodada) para o servidor do notebook por
 * HTTP POST e desliga o Wi-Fi de novo. Em cada tentativa acrescenta uma linha
 * SEND,<ms_desde_o_boot>, que o servidor usa para converter os tempos da placa em horário
 * do notebook. Não desiste: fica tentando até o servidor confirmar.
 */
void wifi_sender_send(const char *log);
