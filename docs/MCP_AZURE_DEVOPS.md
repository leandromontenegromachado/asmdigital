# MCP Azure DevOps

Este projeto agora esta preparado para conectar um servidor MCP de Azure DevOps no workspace.

## 1) Suba o MCP Azure DevOps via Docker Compose

O `docker-compose.yml` possui o servico opcional `azure-devops-mcp` no profile `mcp`.
Imagem utilizada: `guang1/azure-devops-mcp:latest`.

Suba com:

```bash
docker compose --profile mcp up -d azure-devops-mcp
```

Variaveis relevantes no `.env`:
- `AZURE_MCP_PORT`
- `AZURE_DEVOPS_ORG`
- `AZURE_DEVOPS_ORG_URL`
- `AZURE_DEVOPS_PAT`
- `AZURE_DEVOPS_PROJECT`

Por padrao, o endpoint fica em:

`http://localhost:9010/mcp`

Se usar outra porta/host, ajuste `.vscode/mcp.json`.

## 2) Verifique a configuracao MCP no VS Code

Arquivo: `.vscode/mcp.json`

```json
{
  "mcpServers": {
    "azure-devops": {
      "type": "http",
      "url": "http://localhost:9010/mcp"
    }
  }
}
```

## 3) Configure conector Azure DevOps na aplicacao

Em `Conectores`:
- tipo: `Azure DevOps`
- `Endpoint URL`: `https://dev.azure.com/<organizacao>`
- `API Key`: PAT do Azure DevOps
- `Projetos`: lista separada por virgula (opcional)

## 4) Consultar quadro/horas/epico pela API

Endpoint:

`GET /api/azure-devops/connectors/{connector_id}/snapshot`

Query params opcionais:
- `project`
- `team`
- `area_path`
- `iteration_path`
- `top`

Retorna:
- status por estado (`by_state`)
- horas (`original`, `remaining`, `completed`)
- verificacao de vinculo com epico (`with_epic`, `without_epic`)
- itens detalhados (PBI/Tarefa/Epico/Pai)
