# Documentação de Uso Técnico - ASM Digital (MVP)

## 1) Visão geral
Este MVP permite:
- configurar conectores (Redmine) em modo leitura;
- normalizar campos (Cliente/Sistema/Entrega) via mapeamento;
- gerar relatórios consolidados com filtros e exportação CSV/PDF;
- executar automações (mock) e registrar auditoria.

## 2) Pré-requisitos
- Docker + Docker Compose (Docker Desktop no Windows).

## 3) Como rodar
```bash
docker compose up --build
```

## 4) URLs
- Frontend: http://localhost:3000
- Backend (API): http://localhost:8000
- Swagger: http://localhost:8000/docs

## 5) Credenciais admin (seed automático)
As credenciais são criadas automaticamente no primeiro boot, com base no `.env`.

```
ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD=admin123
```

## 6) Variáveis de ambiente
Arquivo `.env.example` (copiar para `.env`):
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`
- `DATABASE_URL` (SQLAlchemy)
- `JWT_SECRET`, `JWT_EXPIRE_MINUTES`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `REDMINE_DEFAULT_TIMEOUT`, `REDMINE_RETRY_ATTEMPTS`, `REDMINE_RETRY_WAIT_SECONDS`
- `TEAMS_WEBHOOK_URL` (opcional)
- `NOTIFICATIONS_SIMULATION` (true/false)

## 7) Autenticação
- `POST /api/auth/login` → retorna `access_token`.
- `GET /api/auth/me` → retorna dados do usuário logado.
- O frontend salva o token e envia no header: `Authorization: Bearer <token>`.

## 8) Conector Redmine
### Cadastro (UI)
1. Acesse **Conectores**.
2. Clique em **Novo conector**.
3. Preencha:
   - `Base URL` (ex.: https://redmine.suaempresa.com)
   - `API Key`
4. Salve e clique em **Testar conexão**.

### Endpoints
- `GET /api/connectors`
- `POST /api/connectors`
- `PUT /api/connectors/{id}`
- `POST /api/connectors/{id}/test`

## 9) Mapeamento e normalização
Tipos de mapeamento:
- `redmine_fields`: define onde ler Cliente/Sistema/Entrega (custom fields, tags, regex subject).
- `normalization_dictionary`: regras de normalização (trim, uppercase, dedupe, dicionário de equivalências).
- `regex_rules`: regex opcional para limpeza/tratamento de valores.

Endpoints:
- `GET /api/mappings?type=...`
- `PUT /api/mappings?type=...`

## 10) Relatório Redmine
### Tela (UI)
1. Informe conector, IDs de projeto, período e status (opcional).
2. Clique em **Gerar relatório**.

### Campos normalizados
- Cliente | Sistema | Entrega | source_ref | source_url

### Endpoints
- `POST /api/reports/redmine-deliveries/generate`
- `GET /api/reports`
- `GET /api/reports/{id}`
- `GET /api/reports/{id}/export.csv`
- `GET /api/reports/{id}/export.pdf`

### Parâmetros relevantes
- `status_id`: `open`, `closed` ou vazio (todos).

## 11) Exportações
- CSV: baixa o arquivo com todas as linhas normalizadas.
- PDF: gera PDF com cabeçalho e tabela de resultados.

## 12) Auditoria e execuções
Cada execução registra:
- `duration_ms`
- `records`
- `errors`
Os dados ficam no `params_json` do report.

## 13) Automações (mock executável)
Automations configuradas (mock):
- Relatório trimestral Redmine
- FADPRO/IHPE
- Azure épicos vencidos
- Apropriação de horas
- Email do ponto → gerar mensagem de prazo de abono

Endpoints:
- `GET /api/automations`
- `POST /api/automations/{id}/run`
- `GET /api/automations/runs`

## 14) Notificações (Teams)
- Se `NOTIFICATIONS_SIMULATION=true`, apenas registra sem enviar.
- Se `false`, envia para `TEAMS_WEBHOOK_URL`.

## 15) Gestão de usuários (CRUD)
Rotas (admin):
- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{id}`
- `DELETE /api/users/{id}`

Campos principais:
- `name`, `email`, `password`, `role`, `is_active`

## 16) Troubleshooting
Backend não sobe / Alembic erro:
- Verifique BOM/encoding em `alembic.ini` e scripts (UTF-8 sem BOM).

Erro bcrypt:
- Senha maior que 72 bytes causa falha. Use senhas menores.

Frontend não inicia:
- Rebuild sem cache: `docker compose build --no-cache frontend`

Ver logs:
```bash
docker compose logs -f backend
docker compose logs -f frontend
```
