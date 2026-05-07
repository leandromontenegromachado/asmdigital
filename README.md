# ASM Digital

Sistema web para relatórios, automações, rotinas agendadas, notificações inteligentes e apoio à gestão operacional.

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Banco: PostgreSQL
- Frontend: React, Vite, Tailwind
- Infra: Docker Compose, Nginx

## Como Rodar

```bash
docker compose up -d --build
```

URLs padrão:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs

Credenciais iniciais, configuradas no `.env`:

```env
ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD=admin123
```

## Módulos Principais

- Conectores Redmine e Azure DevOps
- Relatórios Redmine com CSV/PDF
- Relatórios por linguagem natural
- Rotinas manuais e agendadas
- Cadastro de funcionários
- Notificações inteligentes por email, Teams ou interna
- Histórico de execuções e notificações
- ChefIA/Fala AI
- Avaliação e promoção
- MCP Redmine e Azure DevOps

## Documentação de Uso

O guia completo de operação está em:

- [docs/USAGE.md](docs/USAGE.md)

Documentos complementares:

- [docs/MCP_REDMINE.md](docs/MCP_REDMINE.md)
- [docs/MCP_AZURE_DEVOPS.md](docs/MCP_AZURE_DEVOPS.md)
- [docs/FALA_AI.md](docs/FALA_AI.md)

## Atualizar Servidor de Teste

```bash
cd ~/asmdigital
git pull origin main
docker compose build backend frontend
docker compose up -d db backend frontend redmine-mcp
docker compose ps
```

Validar:

```bash
curl http://localhost:8000/health
curl -I http://localhost:3000/login
```

## Estrutura

```text
backend/    API, serviços, modelos e migrations
frontend/   SPA React
docs/       Documentação técnica e de uso
mcp/        Integrações MCP
docker-compose.yml
```
