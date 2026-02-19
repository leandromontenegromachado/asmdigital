# MCP Redmine

Este projeto inclui um servidor MCP para Redmine via Docker Compose.

## 1) Configurar variáveis

Edite seu arquivo `.env` (ou exporte variáveis) com:

```env
REDMINE_URL=https://redmine.suaempresa.com
REDMINE_API_KEY=seu_token_api_key
REDMINE_MCP_PORT=9000
```

## 2) Subir serviço

```bash
docker compose up -d redmine-mcp
```

## 3) Validar endpoint MCP

```bash
curl http://localhost:9000/mcp
```

## 4) Conectar no editor/cliente MCP

Já foi criado o arquivo `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "redmine": {
      "type": "http",
      "url": "http://localhost:9000/mcp"
    }
  }
}
```

## Observações

- O servidor usa o pacote `redmine-mcp-server`.
- Transporte configurado: `streamable-http`.
- Se sua rede corporativa usar proxy/SSL interno, configure proxy/certificados no container.
