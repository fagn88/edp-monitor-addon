# EDP Voucher Monitor - Home Assistant Add-on

Monitoriza automaticamente a disponibilidade de vouchers no portal EDP Packs e envia notificações via ntfy.

## Funcionalidades

- Verifica disponibilidade de vouchers Pingo Doce 10€
- Intervalo de verificação aleatório (4-6 min por defeito)
- Notificações push via ntfy
- Interface noVNC para login inicial

## Instalação

1. Adiciona este repositório ao Home Assistant:
   - Settings > Add-ons > Add-on Store > ⋮ > Repositories
   - Adiciona: `https://github.com/fagn88/edp-monitor-addon`

2. Instala o add-on "EDP Voucher Monitor"

3. Configura as opções:
   - `ntfy_topic`: Tópico ntfy para notificações
   - `check_interval_min`: Intervalo mínimo em segundos (default: 240)
   - `check_interval_max`: Intervalo máximo em segundos (default: 360)

4. Inicia o add-on

5. Acede ao noVNC em `http://<ip-do-ha>:6080` e faz login no portal EDP

## Configuração ntfy

1. Instala a app ntfy no telemóvel (iOS/Android)
2. Subscreve o tópico configurado (ex: `edp-voucher-fn2026`)
3. Recebes notificação quando o voucher estiver disponível

## Como funciona

1. O add-on usa Chromium com Selenium para navegar no portal EDP
2. Na primeira execução, precisas fazer login via noVNC
3. A sessão fica guardada para verificações futuras
4. Quando o voucher fica disponível, envia múltiplas notificações

## Notas

- O login no portal EDP expira periodicamente - receberás notificação para fazer login novamente
- O intervalo aleatório ajuda a evitar detecção como bot
