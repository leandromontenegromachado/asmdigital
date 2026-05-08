# Guia de Uso - ASM Digital

Este documento descreve como usar, operar e publicar o ASM Digital. Ele cobre os módulos atuais do sistema: autenticação, conectores, relatórios Redmine, relatórios por linguagem natural, rotinas, funcionários, notificações inteligentes, avaliação, ChefIA/Fala AI e integrações MCP.

## 1. Visão Geral

O ASM Digital é uma aplicação web para apoiar gestão operacional, relatórios e automações internas.

Principais capacidades:

- Configurar conectores corporativos, principalmente Redmine e Azure DevOps.
- Gerar relatórios Redmine com filtros, consulta salva, CSV e PDF.
- Criar prompts reutilizáveis para relatórios por linguagem natural.
- Executar relatórios sob demanda ou por agendamento.
- Gerenciar rotinas automatizadas.
- Cadastrar funcionários reutilizáveis por notificações e avaliação.
- Configurar notificações inteligentes por rotina.
- Registrar histórico de execuções e notificações.
- Apoiar processos de avaliação e promoção.
- Usar ChefIA/Fala AI para check-ins, lembretes e relatórios.

## 2. Acesso ao Sistema

URLs padrão em ambiente local:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Swagger/OpenAPI: `http://localhost:8000/docs`

Credenciais iniciais são criadas automaticamente no primeiro boot:

```env
ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD=admin123
```

No servidor de teste, use a URL publicada pela máquina, por exemplo:

```text
http://pro-pae-4095:3000/login
```

## 3. Subir a Aplicação

### 3.1. Subir localmente

Na raiz do projeto:

```bash
docker compose up -d --build
```

Verificar containers:

```bash
docker compose ps
```

Ver logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

Validar saúde:

```bash
curl http://localhost:8000/health
curl -I http://localhost:3000/login
```

### 3.2. Atualizar servidor de teste

No servidor:

```bash
cd ~/asmdigital
git pull origin main
docker compose build backend frontend
docker compose up -d db backend frontend redmine-mcp
docker compose ps
```

Se houver migração nova, o backend executa Alembic automaticamente ao subir.

Verificar logs após atualização:

```bash
docker compose logs --tail 120 backend
```

## 4. Variáveis de Ambiente

Use `.env.example` como base para `.env`.

Principais variáveis:

```env
POSTGRES_DB=asmdigital
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/asmdigital

ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD=admin123
CORS_ORIGINS=http://localhost:3000
APP_PUBLIC_URL=http://localhost:3000

REDMINE_DEFAULT_TIMEOUT=20
REDMINE_RETRY_ATTEMPTS=3
REDMINE_RETRY_WAIT_SECONDS=2

FALA_AI_GEMINI_API_KEY=
FALA_AI_GEMINI_MODEL=gemini-3-flash-preview

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=asmdigital@company.com
SMTP_USE_TLS=true
```

Observações:

- `APP_PUBLIC_URL` é usado em links enviados por email/notificação.
- Se `SMTP_HOST` estiver vazio, o envio por email fica simulado/registrado.
- Para Redmine interno, a máquina precisa estar conectada à VPN/rede corporativa.

## 5. Autenticação e Usuários

### 5.1. Login

Endpoint:

```http
POST /api/auth/login
```

O frontend salva o token JWT e envia:

```http
Authorization: Bearer <token>
```

### 5.2. Gestão de usuários

Menu:

- **Configurações > Usuários**

Funcionalidades:

- Criar usuário.
- Editar nome, email, perfil e status.
- Resetar senha.
- Ativar/inativar usuário.

Endpoints:

- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{id}`
- `POST /api/users/{id}/reset-password`

## 6. Conectores

Menu:

- **Conectores**

### 6.1. Redmine

Passos:

1. Acesse **Conectores**.
2. Clique em **Novo conector**.
3. Selecione tipo `Redmine`.
4. Informe:
   - Base URL: `https://redmine.intra.rs.gov.br`
   - API Key
   - Projetos padrão, quando aplicável
5. Salve.
6. Clique em **Testar conexão**.

Endpoints:

- `GET /api/connectors`
- `POST /api/connectors`
- `PUT /api/connectors/{id}`
- `POST /api/connectors/{id}/test`
- `GET /api/connectors/{id}/redmine/queries`

### 6.2. Azure DevOps

O sistema também possui suporte para dados de Azure DevOps. Consulte `docs/MCP_AZURE_DEVOPS.md` para detalhes do MCP e variáveis necessárias.

## 7. Relatório Redmine

Menu:

- **Relatórios**

Uso básico:

1. Selecione o conector `Redmine`.
2. Informe o projeto, por exemplo `asm-dem`.
3. Informe data inicial e final.
4. Se quiser, informe uma Query ID salva do Redmine.
5. Clique em **Gerar relatório**.

Campos de resultado:

- Cliente
- Sistema
- Entrega
- Referência
- URL
- Campos dinâmicos conforme o prompt/consulta

Exportações:

- **Exportar CSV**
- **Exportar PDF**

Endpoints:

- `POST /api/reports/redmine-deliveries/generate`
- `GET /api/reports`
- `GET /api/reports/{id}`
- `GET /api/reports/{id}/export.csv`
- `GET /api/reports/{id}/export.pdf`

Observações importantes:

- Consulta salva do Redmine pode ser usada por `query_id`.
- Se a consulta salva não retornar dados úteis para o prompt, o sistema pode usar filtros diretos no Redmine.
- Para consultar Redmine interno, a VPN precisa estar ativa.

## 8. Relatórios por Linguagem Natural

Menu:

- **Relatórios IA**

Esse módulo permite criar prompts reutilizáveis para gerar relatórios sob demanda ou agendados.

### 8.1. Criar template

1. Acesse **Relatórios IA**.
2. Clique em **Novo**.
3. Informe:
   - Nome
   - Conector
   - Brief para IA
   - Prompt final
   - Projeto padrão
   - Query padrão, opcional
   - Status e período padrão
4. Clique em **Salvar template**.

### 8.2. Gerar prompt Markdown

O botão **Gerar prompt Markdown** monta um prompt inicial baseado no brief. O prompt pode ser editado antes de salvar/executar.

### 8.3. Executar sob demanda

Clique em **Executar agora**. O sistema:

1. Interpreta o prompt.
2. Define filtros de projeto/status/período/query.
3. Executa o relatório.
4. Abre diretamente a tela de resultado.

Na tela de resultado, é possível:

- Ver resumo.
- Ver tabela de dados.
- Exportar CSV/PDF.
- Alterar o prompt.
- Executar novamente.

### 8.4. Agendamento simples

O agendamento foi simplificado. Em vez de editar CRON diretamente, a tela permite:

- Habilitar agendamento.
- Escolher hora.
- Escolher dias da semana.

Exemplo:

- Todos os dias às 08:00.
- Segunda-feira às 08:00.
- Segunda, quarta e sexta às 17:00.

O sistema converte isso internamente para CRON.

## 9. Gestão de Rotinas

Menu:

- **Rotinas**

Essa tela mostra:

- Relatórios agendados por linguagem natural.
- Rotinas cadastradas.
- Últimas execuções.

### 9.1. Relatórios agendados por linguagem natural

Os templates de relatórios IA com agendamento aparecem no topo da tela.

Ações disponíveis:

- **Executar**: roda o relatório imediatamente.
- **Execuções**: mostra execuções anteriores.
- **Abrir**: abre o último relatório gerado.

### 9.2. Rotinas cadastradas

Uma rotina pode ter uma ou mais tarefas. Tipos suportados:

- Relatório Redmine.
- Prompt Report.
- Azure DevOps Quadro.
- Webhook.
- Sleep.
- Custom.

Cada rotina permite:

- Nome.
- Agendamento CRON.
- Ativar/pausar.
- Executar manualmente.
- Editar tarefas.
- Excluir.
- Email para aviso de execução.

### 9.3. Últimas execuções

A tabela **Últimas execuções** junta:

- Execuções de rotinas cadastradas.
- Execuções de relatórios por linguagem natural.

Quando a execução gera relatório, a tabela mostra o link **Abrir relatório**.

Endpoints:

- `GET /api/automations`
- `POST /api/automations`
- `PUT /api/automations/{id}`
- `DELETE /api/automations/{id}`
- `POST /api/automations/{id}/run`
- `GET /api/automations/runs`

## 10. Funcionários

Menu:

- **Funcionários**

O cadastro de funcionários é reutilizável por:

- Notificações inteligentes.
- Avaliação para promoção.
- Outros módulos futuros.

Campos principais:

- Nome
- Email
- Matrícula
- Teams user ID
- Cargo
- Setor
- Gestor
- Ativo
- Recebe notificação
- Participa avaliação
- Canal preferencial: email, Teams ou interna

Uso:

1. Acesse **Funcionários**.
2. Clique em **Novo**.
3. Preencha os dados.
4. Defina o gestor, se houver.
5. Defina canal preferencial.
6. Salve.

Endpoints:

- `GET /api/employees`
- `POST /api/employees`
- `GET /api/employees/{id}`
- `PUT /api/employees/{id}`

## 11. Notificações Inteligentes

Menu:

- **Notificações**

Esse módulo permite que uma rotina gere mensagens automáticas para responsáveis, gestores ou destinatários definidos.

### 11.1. Conceitos

Template de mensagem:

- Define assunto e corpo.
- Pode usar variáveis do resultado da rotina.

Regra de notificação:

- Define para qual rotina a notificação vale.
- Define se está ativa.
- Define destinatário.
- Define canal preferencial e fallback.
- Define se exige aprovação.
- Define se gestor deve ser notificado.

Histórico:

- Registra todas as notificações.
- Registra erros.
- Registra tentativas.
- Permite reenvio manual.

### 11.2. Canais suportados

- `email`
- `teams`
- `internal`

Email:

- Usa SMTP se configurado.
- Se SMTP não estiver configurado, registra/simula envio.

Teams:

- Implementação desacoplada e preparada para Microsoft Graph.
- Nesta fase, o envio é registrado/simulado.

Interna:

- Registra a notificação no histórico interno.

### 11.3. Criar template

1. Acesse **Notificações**.
2. Na seção **Template de mensagem**, informe:
   - Nome
   - Canal
   - Assunto
   - Corpo
3. Use variáveis entre `{{ }}`.
4. Clique em **Salvar template**.

Exemplo de template:

```text
Olá, {{nome_responsavel}}.

A rotina "{{nome_rotina}}" identificou uma pendência relacionada ao projeto "{{nome_projeto}}".

Status: {{status}}
Dias em atraso: {{dias_atraso}}
Data da execução: {{data_execucao}}

Ação sugerida:
{{acao_sugerida}}

Acesse o relatório completo em:
{{link_relatorio}}
```

### 11.4. Criar regra

1. Acesse **Notificações**.
2. Escolha a rotina.
3. Escolha o template.
4. Defina destinatário:
   - Responsável do resultado.
   - Gestor do responsável.
   - Funcionário fixo.
5. Escolha canal preferencial.
6. Escolha canal fallback.
7. Opcionalmente marque:
   - Exige aprovação.
   - Notificar gestor também.
8. Salve.

### 11.5. Variáveis disponíveis

As variáveis vêm do resultado estruturado da rotina e de campos calculados:

- `nome_responsavel`
- `nome_rotina`
- `nome_projeto`
- `status`
- `dias_atraso`
- `data_execucao`
- `acao_sugerida`
- `link_relatorio`
- `execucao_id`
- `rotina_id`

Também podem ser usadas chaves presentes no JSON original do resultado.

### 11.6. Resultado estruturado esperado

Exemplo:

```json
{
  "rotina": "Projetos em atraso",
  "data_execucao": "2026-05-07",
  "deve_notificar": true,
  "resultados": [
    {
      "projeto": "Portal de Serviços",
      "status": "Atrasado",
      "dias_atraso": 12,
      "responsavel_nome": "Maria Silva",
      "responsavel_id": 1,
      "acao_sugerida": "Atualizar o cronograma e informar nova previsão de entrega."
    }
  ]
}
```

Para identificar o responsável, o sistema procura, nesta ordem:

1. `responsavel_id`, `employee_id`, `funcionario_id` ou `assigned_to_id`.
2. `responsavel_email`, `email` ou `assigned_to_email`.
3. `responsavel_nome`, `nome_responsavel`, `assigned_to` ou `responsavel`.

### 11.7. Histórico e reenvio

Na seção **Histórico de notificações** é possível:

- Ver rotina.
- Ver funcionário.
- Ver canal.
- Ver status.
- Ver erro.
- Reenviar notificações com status `erro`.

Status possíveis:

- `pendente`
- `enviado`
- `erro`
- `cancelado`
- `aguardando_aprovacao`

Endpoints:

- `GET /api/notification-templates`
- `POST /api/notification-templates`
- `PUT /api/notification-templates/{id}`
- `DELETE /api/notification-templates/{id}`
- `GET /api/notification-rules`
- `POST /api/notification-rules`
- `PUT /api/notification-rules/{id}`
- `DELETE /api/notification-rules/{id}`
- `GET /api/notifications`
- `POST /api/notifications/{id}/retry`

## 12. Eventos, Pendencias e Regras Gerenciais

Menu:

- **Executivo**
- **Regras Gerenciais**

Esse modulo permite transformar eventos gerenciais em acoes configuraveis. A regra fica separada do relatorio ou da rotina, evitando logica fixa dentro de cada rotina.

Fluxo basico:

1. Uma rotina, relatorio ou acao do sistema gera um evento gerencial.
2. O usuario cria uma regra gerencial.
3. A regra verifica o evento usando `condition_json`.
4. Se a condicao for atendida, o sistema executa a acao definida em `action_json`.
5. Toda acao aplicada fica registrada no historico.

### 12.1. Dashboard Executivo

Menu:

- **Executivo**

O dashboard executivo mostra:

- Total de eventos de hoje.
- Eventos novos.
- Eventos `high`.
- Eventos `critical`.
- Pendencias abertas.
- Pendencias vencidas.
- Pendencias escaladas.
- Rotinas com falha hoje.
- Top 5 projetos com mais eventos.
- Top 5 responsaveis com mais pendencias.
- Lista de eventos criticos.
- Lista de pendencias vencidas.

Endpoint:

- `GET /api/executive-dashboard/summary`

### 12.2. Criar regra gerencial

Menu:

- **Regras Gerenciais**

Campos principais:

- **Nome**: nome da regra.
- **Descricao**: explicacao de quando a regra deve ser aplicada.
- **Prioridade**: ordem de execucao. Numero menor executa antes.
- **Regra ativa**: indica se a regra deve ser considerada.
- **Condition JSON**: condicao que o evento precisa atender.
- **Action JSON**: acao que deve ser registrada/executada.

Exemplo:

Nome:

```text
Falha de rotina vira pendencia
```

Condition JSON:

```json
{
  "event_type": {
    "eq": "ROUTINE_FAILED"
  }
}
```

Action JSON:

```json
{
  "type": "create_pending_item"
}
```

Essa regra cria uma pendencia quando o evento gerencial for do tipo `ROUTINE_FAILED`.

### 12.3. Operadores do `condition_json`

Operadores disponiveis:

- `eq`: igual.
- `neq`: diferente.
- `gt`: maior que.
- `gte`: maior ou igual.
- `lt`: menor que.
- `lte`: menor ou igual.
- `contains`: contem texto ou item.

Exemplo por severidade:

```json
{
  "severity": {
    "eq": "high"
  }
}
```

Exemplo usando dado dentro do `payload_json`:

```json
{
  "field": "payload_json.dias_atraso",
  "op": "gte",
  "value": 5
}
```

Exemplo com duas condicoes obrigatorias:

```json
{
  "all": [
    {
      "field": "event_type",
      "op": "eq",
      "value": "ROUTINE_FAILED"
    },
    {
      "field": "severity",
      "op": "eq",
      "value": "high"
    }
  ]
}
```

Exemplo com alternativas:

```json
{
  "any": [
    {
      "field": "severity",
      "op": "eq",
      "value": "critical"
    },
    {
      "field": "payload_json.dias_atraso",
      "op": "gte",
      "value": 10
    }
  ]
}
```

### 12.4. Acoes do `action_json`

Criar pendencia:

```json
{
  "type": "create_pending_item"
}
```

Marcar evento como processado:

```json
{
  "type": "mark_processed"
}
```

Ignorar evento:

```json
{
  "type": "ignore"
}
```

Registrar placeholder de notificacao:

```json
{
  "type": "notify_responsible"
}
```

Observacao: `notify_responsible` ainda nao envia notificacao real nesta fase. Ele apenas registra a acao executada para manter historico e preparar a integracao futura.

Tambem e possivel executar mais de uma acao:

```json
{
  "actions": [
    {
      "type": "create_pending_item"
    },
    {
      "type": "notify_responsible"
    }
  ]
}
```

### 12.5. Aplicar regras em um evento

As regras podem ser aplicadas em um evento gerencial pelo endpoint:

- `POST /api/management-events/{id}/apply-rules`

O retorno informa:

- ID do evento.
- Quantidade de regras encontradas.
- Lista de acoes executadas/registradas.

Endpoints de regras:

- `GET /api/management-events/rules`
- `POST /api/management-events/rules`
- `GET /api/management-events/rules/{rule_id}`
- `PUT /api/management-events/rules/{rule_id}`
- `DELETE /api/management-events/rules/{rule_id}`

Observacao: excluir uma regra pela tela/API desativa a regra para preservar o historico de acoes ja executadas.

## 13. ChefIA / Fala AI

Menu:

- **ChefIA**

Funções principais:

- Check-in manual.
- Lembretes.
- Relatório diário.
- Consulta ao bot.
- Integração preparada com Teams.

Mais detalhes:

- `docs/FALA_AI.md`

## 14. Avaliação

Menu:

- **Avaliação**

Submódulos:

- Ciclos
- CSV e IA
- Pontuação
- Relatório IA
- Calibração
- Lista final

O cadastro de funcionários é compartilhado com esse módulo. Use **Funcionários** para manter dados básicos atualizados.

## 15. MCP Redmine

O projeto inclui servidor MCP para Redmine.

Subir:

```bash
docker compose up -d redmine-mcp
```

Validar:

```bash
curl http://localhost:9000/mcp
```

Configuração principal:

```env
REDMINE_URL=https://redmine.intra.rs.gov.br
REDMINE_API_KEY=seu_token
REDMINE_MCP_PORT=9000
```

Mais detalhes:

- `docs/MCP_REDMINE.md`

## 16. Publicação no Servidor de Teste

Fluxo recomendado:

1. Subir alterações para o GitHub.
2. Entrar no servidor de teste.
3. Atualizar repositório.
4. Rebuildar backend/frontend.
5. Subir containers.
6. Validar logs e healthcheck.

Comandos:

```bash
cd ~/asmdigital
git pull origin main
docker compose build backend frontend
docker compose up -d db backend frontend redmine-mcp
docker compose ps
docker compose logs --tail 120 backend
```

Validar:

```bash
curl http://localhost:8000/health
curl -I http://localhost:3000/login
```

Se acessado por outra máquina via Windows/WSL, conferir portproxy:

```powershell
netsh interface portproxy show all
```

Se necessário, recriar como administrador:

```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=3000 connectaddress=IP_DO_LINUX connectport=3000
New-NetFirewallRule -DisplayName "ASMDIGITAL Frontend 3000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000
```

## 17. Troubleshooting

### 17.1. Redmine não retorna dados

Verificar:

- VPN ligada.
- URL do Redmine acessível no servidor.
- API Key válida.
- Projeto correto, por exemplo `asm-dem`.
- Query ID correta.

Teste:

```bash
docker compose logs --tail 120 backend
```

### 17.2. Docker não conecta ao daemon

Erro comum:

```text
Cannot connect to the Docker daemon
```

No WSL/ambiente Linux:

```bash
service docker start
docker info
```

### 17.3. Problemas de iptables no WSL

Se Docker falhar por `iptables`/`nft`, usar legacy pode ser necessário:

```bash
update-alternatives --set iptables /usr/sbin/iptables-legacy
update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
service docker restart
```

### 17.4. Frontend não atualiza

Rebuild:

```bash
docker compose build frontend
docker compose up -d frontend
```

No navegador:

```text
Ctrl + F5
```

### 17.5. Migration falha

Ver logs:

```bash
docker compose logs --tail 120 backend
```

Conferir versão do banco:

```bash
docker compose exec -T db psql -U postgres -d asmdigital -c "select version_num from alembic_version;"
```

### 17.6. Email não envia

Verificar:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS`

Se SMTP estiver vazio, o sistema registra/simula envio.

## 18. Endpoints Principais

Autenticação:

- `POST /api/auth/login`
- `GET /api/auth/me`

Usuários:

- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{id}`

Funcionários:

- `GET /api/employees`
- `POST /api/employees`
- `PUT /api/employees/{id}`

Conectores:

- `GET /api/connectors`
- `POST /api/connectors`
- `PUT /api/connectors/{id}`
- `POST /api/connectors/{id}/test`

Relatórios:

- `POST /api/reports/redmine-deliveries/generate`
- `GET /api/reports`
- `GET /api/reports/{id}`
- `GET /api/reports/{id}/export.csv`
- `GET /api/reports/{id}/export.pdf`

Relatórios IA:

- `GET /api/prompt-reports`
- `POST /api/prompt-reports`
- `PUT /api/prompt-reports/{id}`
- `POST /api/prompt-reports/{id}/run`
- `GET /api/prompt-reports/{id}/runs`

Rotinas:

- `GET /api/automations`
- `POST /api/automations`
- `PUT /api/automations/{id}`
- `DELETE /api/automations/{id}`
- `POST /api/automations/{id}/run`
- `GET /api/automations/runs`

Notificações:

- `GET /api/notification-templates`
- `POST /api/notification-templates`
- `GET /api/notification-rules`
- `POST /api/notification-rules`
- `GET /api/notifications`
- `POST /api/notifications/{id}/retry`

Dashboard executivo:

- `GET /api/executive-dashboard/summary`

Eventos gerenciais:

- `GET /api/management-events`
- `POST /api/management-events`
- `GET /api/management-events/{id}`
- `PUT /api/management-events/{id}`
- `POST /api/management-events/{id}/process`
- `POST /api/management-events/{id}/ignore`
- `POST /api/management-events/{id}/convert-to-pending`
- `POST /api/management-events/{id}/apply-rules`

Regras gerenciais:

- `GET /api/management-events/rules`
- `POST /api/management-events/rules`
- `GET /api/management-events/rules/{rule_id}`
- `PUT /api/management-events/rules/{rule_id}`
- `DELETE /api/management-events/rules/{rule_id}`

Pendencias:

- `GET /api/pending-items`
- `POST /api/pending-items`
- `GET /api/pending-items/{id}`
- `PUT /api/pending-items/{id}`
- `POST /api/pending-items/{id}/comment`
- `POST /api/pending-items/{id}/resolve`
- `POST /api/pending-items/{id}/ignore`
- `POST /api/pending-items/{id}/escalate`
- `POST /api/pending-items/{id}/reopen`
- `GET /api/pending-items/dashboard/summary`

## 19. Arquitetura Resumida

Backend:

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- APScheduler

Frontend:

- React
- Vite
- Tailwind
- Axios

Infra:

- Docker Compose
- Nginx no frontend
- PostgreSQL persistente em volume Docker

Pastas principais:

```text
backend/app/api/routers
backend/app/services
backend/app/schemas
backend/app/models
backend/alembic/versions
frontend/src/api
frontend/src/pages
frontend/src/components
docs
```

## 20. Boas Práticas de Operação

- Manter `.env` fora do Git.
- Usar `.env.example` apenas como referência.
- Antes de publicar no teste, executar build local quando possível.
- Conferir logs do backend após migrations.
- Configurar `APP_PUBLIC_URL` corretamente no servidor.
- Manter VPN ativa para integrações internas.
- Para notificações reais por email, configurar SMTP antes de ativar regras em produção.
