# EDP Voucher Monitor - Home Assistant Add-on

Monitoriza automaticamente a disponibilidade de vouchers no portal EDP Packs e envia notificações push via ntfy.

## Funcionalidades

- Verifica disponibilidade de vouchers Pingo Doce 10€
- Intervalo de verificação aleatório (4-6 min por defeito) para evitar detecção
- Notificações push via ntfy para telemóvel
- Interface noVNC para login inicial no portal EDP
- Sessão persistente - login guardado entre reinícios

## Instalação

### 1. Adicionar repositório ao Home Assistant

1. Vai a **Settings** > **Add-ons** > **Add-on Store**
2. Clica nos **⋮** (3 pontos) no canto superior direito
3. Selecciona **Repositories**
4. Adiciona: `https://github.com/fagn88/edp-monitor-addon`
5. Clica **Add** e depois **Close**

### 2. Instalar o add-on

1. Procura **"EDP Voucher Monitor"** na lista de add-ons
2. Clica e selecciona **Install**
3. Aguarda a instalação (pode demorar alguns minutos)

### 3. Configurar

Na página do add-on, configura:

| Opção | Descrição | Default |
|-------|-----------|---------|
| `ntfy_topic` | Tópico ntfy para notificações | `edp-voucher-fn2026` |
| `check_interval_min` | Intervalo mínimo em segundos | `240` (4 min) |
| `check_interval_max` | Intervalo máximo em segundos | `360` (6 min) |

### 4. Configurar notificações ntfy

1. Instala a app **ntfy** no telemóvel ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
2. Abre a app e adiciona subscrição ao tópico configurado (ex: `edp-voucher-fn2026`)

### 5. Iniciar e fazer login

1. Clica **Start** para iniciar o add-on
2. Abre o browser em `http://<ip-do-ha>:6080`
3. No noVNC, faz login no portal EDP (https://particulares.cliente.edp.pt)
4. Após login, o monitor começa automaticamente

## Como funciona

```
┌─────────────────────────────────────────────────────────┐
│                    Home Assistant                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │           EDP Voucher Monitor Add-on             │    │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────────┐    │    │
│  │  │  Xvfb   │→│ Chromium │→│ edp_monitor  │    │    │
│  │  │ Display │  │ Browser  │  │   Python     │    │    │
│  │  └─────────┘  └─────────┘  └──────┬───────┘    │    │
│  │       ↓                           │            │    │
│  │  ┌─────────┐                      ↓            │    │
│  │  │ noVNC   │←─ Login      ┌──────────────┐    │    │
│  │  │ :6080   │   Manual     │   ntfy.sh    │    │    │
│  │  └─────────┘              └──────┬───────┘    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                                       │
                                       ↓
                              ┌──────────────┐
                              │  Telemóvel   │
                              │  (ntfy app)  │
                              └──────────────┘
```

1. O add-on corre Chromium num display virtual (Xvfb)
2. noVNC permite acesso visual para fazer login inicial
3. O script Python navega para a página de vouchers
4. Verifica se está disponível a cada 4-6 minutos
5. Quando disponível, envia notificação push via ntfy

## Logs

Verifica os logs em: **Add-on** > **EDP Voucher Monitor** > **Log**

Exemplo de output:
```
[main] Creating Chrome driver...
[main] Driver created successfully
[check] Navigating to packs page...
[check] Waiting for Pingo Doce...
[check] Clicking Pingo Doce...
[11:55:50] Sold out
[main] #1 | Next: 12:01:37 (347s)
```

## Notas

- A sessão de login expira periodicamente - receberás notificação para fazer login novamente
- O intervalo aleatório ajuda a evitar detecção como bot
- O add-on continua a correr mesmo que feches o noVNC
- Quando o voucher fica disponível, o monitor envia 10 notificações espaçadas de 1 minuto

## Estrutura do Add-on

```
edp-monitor-addon/
├── README.md
├── repository.json
└── edp-monitor/
    ├── config.yaml
    ├── build.yaml
    ├── Dockerfile
    ├── CHANGELOG.md
    ├── edp_monitor.py
    └── rootfs/
        └── etc/services.d/edp-monitor/run
```

## Licença

MIT
