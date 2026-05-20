# Telemetry Module

Sistema de telemetria que envia dados do bot Python para a API Node.js em tempo real.

## Projeto Relacionado (Node.js)

O backend que recebe os dados de telemetria vive em um repositório separado:

- **Caminho local**: `../tibia-services/` (relativo a este repo)
- **Docs**: Ver `CLAUDE.md` na raiz daquele repo

### Arquivos relevantes na API (Node.js)

```
apps/api/src/
├── modules/
│   ├── events/
│   │   ├── controller.ts           # POST /api/v1/events/batch (recebe eventos do bot)
│   │   ├── schemas.ts              # BatchEventsSchema, Event types
│   │   └── use-cases/
│   │       └── process-batch.use-case.ts  # Processa kills, loot, XP, deaths
│   ├── sessions/
│   │   └── controller.ts           # CRUD de sessions
│   ├── realtime/
│   │   └── controller.ts           # WebSocket handler (position, status, bot disconnect)
│   └── analytics/
│       ├── controller.ts           # GET endpoints (XP/h, kills, loot, heatmap, hunts)
│       ├── schemas.ts              # Zod schemas de response
│       └── use-cases/              # Use cases por endpoint
├── shared/realtime/
│   └── room-manager.ts             # Gerencia rooms WebSocket por sessionId
└── entities/
    ├── session.entity.ts           # SessionEntity (status, kills, loot totals)
    ├── kill.entity.ts              # KillEntity (positionX/Y/Z, experienceGained)
    ├── loot.entity.ts              # LootEntity
    ├── experience-snapshot.entity.ts
    └── game-event.entity.ts        # GameEventEntity (death, level_up, refill)
```

### Arquivos relevantes no Frontend (Node.js)

```
apps/app/src/
├── hooks/
│   ├── use-realtime.ts             # WebSocket client (position, status, events)
│   ├── use-analytics.ts            # React Query hooks para analytics
│   └── use-notifications.ts        # Browser notifications (death, low HP, stuck)
├── components/map/
│   └── live-map.tsx                # Mapa Leaflet com posicao ao vivo + heatmap
├── types/
│   └── index.ts                    # Interfaces TypeScript
└── routes/dashboard/
    ├── index.tsx                   # Dashboard principal (mini-map, bot status)
    ├── sessions/$sessionId.tsx     # Detalhe da sessao (heatmap, notifications)
    └── analytics/index.tsx         # Analytics (hunts tab, XP, kills, loot)
```

## Arquitetura do Módulo

```
src/telemetry/
├── __init__.py      # Exporta TelemetryClient
├── client.py        # TelemetryClient — facade principal
├── config.py        # Configuracoes (URLs, intervals)
├── buffer.py        # EventBuffer — ring buffer thread-safe
├── worker.py        # TelemetryWorker — thread que faz flush de eventos via HTTP
└── realtime.py      # RealtimeClient — WebSocket para position/status updates
```

## Fluxo de Dados

```
Bot (Python)                          API (Node.js)                    Frontend (React)
─────────────                         ────────────                     ────────────────
TelemetryClient
  ├── start_session() ──HTTP POST──→  POST /api/v1/sessions
  │                                     → cria SessionEntity
  │
  ├── track_kill/loot/xp()
  │   └── EventBuffer ──────────────→  POST /api/v1/events/batch
  │       (flush via TelemetryWorker)     → salva Kill/Loot/XP entities
  │                                       → broadcast stats via WS ───→  useRealtimeSession()
  │                                       → broadcast death/level_up ─→  useNotifications()
  │
  ├── update_position() ──WebSocket─→  WS /ws (position message)
  │   └── RealtimeClient                  → updateRoomPosition()
  │                                       → broadcast to subscribers ─→  LiveMap component
  │
  ├── update_status() ──WebSocket──→  WS /ws (status message)
  │   └── RealtimeClient                  → updateRoomStatus()
  │                                       → broadcast to subscribers ─→  BotStatusCard
  │
  └── end_session() ──HTTP PATCH──→   PATCH /api/v1/sessions/:id
      (also via atexit/SIGTERM)           → status = "completed"
      OR: WS disconnect ─────────→       → close handler patches session
```

## Protocolo de Comunicacao

### HTTP — Eventos em Batch

```python
# Bot envia (via TelemetryWorker, a cada flush_interval=5s)
POST /api/v1/events/batch
Authorization: Bearer tm_xxxx...
{
  "sessionId": "uuid",
  "events": [
    {"type": "kill", "creatureName": "Demon", "experienceGained": 6000, "positionX": 1000, ...},
    {"type": "loot", "itemName": "Demon Horn", "quantity": 1, "estimatedValue": 5000},
    {"type": "experience", "experience": "100000000", "level": 500},
    {"type": "death", "killer": "Demon", "positionX": 1000, ...},
    {"type": "level_up", "newLevel": 501},
    {"type": "refill", "potionsBought": 100, "goldSpent": 5000}
  ]
}
```

### WebSocket — Posicao e Status

```python
# Bot envia (via RealtimeClient, a cada update_interval=0.5s)
WS /ws?token=tm_xxxx&session=uuid

# Position update
{"type": "position", "sessionId": "uuid", "x": 1000, "y": 1000, "z": 7, "timestamp": "..."}

# Status update
{"type": "status", "sessionId": "uuid", "hpPercent": 85, "manaPercent": 60,
 "botState": "running", "targetCreature": "Demon", "currentTask": "attacking"}
```

## Graceful Shutdown

O client registra handlers para fechar a sessao corretamente:

1. **atexit** — chamado em exit normal do Python (Ctrl+C com KeyboardInterrupt handled)
2. **SIGTERM** — chamado quando processo recebe kill (sem -9)
3. **API-side fallback** — se o WebSocket desconecta (kill -9), a API detecta e fecha a sessao

Guard `_ending` previne double-call quando atexit + SIGTERM disparam juntos.

## Uso no GameLoop

```python
# Em gameloop.py
telemetry = TelemetryClient()  # Lê TELEMETRY_API_URL, TELEMETRY_API_KEY do .env
telemetry.start_session(character_id="uuid", hunt_location="Oramond")

# A cada tick
telemetry.update_position(x, y, z)
telemetry.update_status(hp_percent=85, mana_percent=60, bot_state="running", ...)

# Quando mata criatura
telemetry.track_kill("Demon", experience=6000, position=(x, y, z))

# No finally do gameloop
telemetry.end_session(final_level=500, final_experience=100000000)
```

## Variaveis de Ambiente

```env
TELEMETRY_API_URL=http://localhost:3333    # URL da API Node.js
TELEMETRY_API_KEY=tm_xxxx...               # License key para autenticacao
TELEMETRY_WS_URL=ws://localhost:3333/ws    # WebSocket URL
```
