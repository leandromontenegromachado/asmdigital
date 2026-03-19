# Modulo Fala Ai

## Analise do sistema atual

- Estrutura backend: `backend/app` com separacao por `api/routers`, `schemas`, `services`, `models`, `db`, `core`.
- Padrao de rotas: `FastAPI APIRouter` em `app/api/routers/*` com dependencia via `Depends`.
- ORM: `SQLAlchemy` (sincrono) + `Alembic` para migracoes.
- Autenticacao: JWT bearer em `app/api/deps.py` (`get_current_user`) e autorizacao admin com `require_admin`.
- Novos modulos: entram via novo router incluido em `app/main.py`, novos schemas/modelos/services e sincronizacao no scheduler global quando necessario.

## Onde o Fala Ai foi encaixado

- Novo pacote: `backend/app/modules/fala_ai`.
- Router exposto em `backend/app/api/routers/fala_ai.py` e incluido no `main.py`.
- Modelos registrados no metadata central via `app/models/models.py` e exportados em `app/models/__init__.py`.
- Scheduler reaproveitado: `backend/app/scheduler.py` agora chama `sync_fala_ai_jobs`.

## Dependencias reaproveitadas

- Banco e sessao SQLAlchemy: `app/db/session.py`.
- Auth/autorizacao existente: `get_current_user` e `require_admin`.
- Scheduler existente: `APScheduler` em `app/scheduler.py`.
- Configuracao central: `app/core/config.py`.

## Endpoints criados

- `POST /api/fala-ai/checkin`
- `GET /api/fala-ai/checkins` (admin)
- `POST /api/fala-ai/webhook/teams`
- `GET /api/fala-ai/reminders` (admin)
- `POST /api/fala-ai/reminders` (admin)
- `PUT /api/fala-ai/reminders/{id}` (admin)
- `DELETE /api/fala-ai/reminders/{id}` (admin)
- `POST /api/fala-ai/reminders/{id}/send` (admin)
- `GET /api/fala-ai/report/daily` (admin)
- `GET /api/fala-ai/logs` (admin)
- `POST /api/fala-ai/reply`

## Banco de dados

Migracao: `backend/alembic/versions/20260318_0004_add_fala_ai_tables.py`

Tabelas:
- `fala_ai_checkins`
- `fala_ai_reminders`
- `fala_ai_logs`

## Integracao Teams

- Validacao de assinatura HMAC SHA256 por header:
  - `x-fala-ai-signature` (ou `x-teams-signature`)
  - formato esperado: `sha256=<digest_hex>`
- Segredo configuravel via `FALA_AI_TEAMS_WEBHOOK_SECRET`.
- Envio de mensagens pode ocorrer por:
  - Webhook: `FALA_AI_TEAMS_OUTGOING_WEBHOOK`
  - Bot Framework: `FALA_AI_TEAMS_BOT_APP_ID` + `FALA_AI_TEAMS_BOT_APP_SECRET` + contexto de conversa.

## Variaveis de ambiente novas

- `FALA_AI_TEAMS_WEBHOOK_SECRET`
- `FALA_AI_TEAMS_OUTGOING_WEBHOOK`
- `FALA_AI_TEAMS_BOT_APP_ID`
- `FALA_AI_TEAMS_BOT_APP_SECRET`
- `FALA_AI_TEAMS_DEFAULT_SERVICE_URL`
- `FALA_AI_TEAMS_DEFAULT_CONVERSATION_ID`
- `FALA_AI_TEAMS_DEFAULT_BOT_ID`
- `FALA_AI_MISSING_CHECKIN_CRON` (padrao: `0 16 * * 1-5`)

## Frontend

- Novo item de menu: **Fala Ai**.
- Nova rota: `/fala-ai`.
- Nova pagina: check-in manual, CRUD basico de lembretes (admin), relatorio diario e consulta ao bot.

## Extensibilidade futura

A estrutura do modulo ja separa:
- `service.py`: regras de negocio (base para gamificacao/ranking/PPR)
- `teams_integration.py`: adaptador de canal
- `scheduler.py`: orquestracao de lembretes e verificacao de ausencia

Isso permite plugar pontuacao, ranking e indicadores sem acoplamento com rotas.
