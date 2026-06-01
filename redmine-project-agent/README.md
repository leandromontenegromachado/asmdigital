# Redmine Project Advisor Agent

Primeira versão de um agente consultivo para avaliar projetos no Redmine.

Ele é **somente leitura**:

- consulta dados do Redmine via API;
- calcula métricas objetivas;
- classifica risco do projeto;
- gera sugestões para o gestor;
- não comenta, não edita issue, não altera status e não cria tarefas.

## Configuração

Crie um arquivo `.env` ou defina variáveis de ambiente:

```text
REDMINE_URL=https://redmine.suaempresa.com
REDMINE_API_KEY=token_somente_leitura
```

O token ideal deve ter permissão apenas para ler projetos, issues, usuários, versões e comentários.

## Uso com Redmine

```powershell
python -m redmine_project_agent.cli --project-id 123 --days-stale 7 --output markdown
```

Saída JSON:

```powershell
python -m redmine_project_agent.cli --project-id 123 --output json
```

## Uso com arquivo local

Para testar sem conectar no Redmine:

```powershell
python -m redmine_project_agent.cli --input examples/sample_project.json --output markdown
```

## Uso dentro do seu assistente

Use o assistente atual como porta de entrada e registre o agente como uma ferramenta interna.

```python
from redmine_project_agent import avaliar_projeto_redmine

resultado = avaliar_projeto_redmine(project_id=123)
```

Para testar sem Redmine:

```python
from redmine_project_agent import avaliar_projeto_redmine

resultado = avaliar_projeto_redmine(input_path="examples/sample_project.json")
```

Se o seu assistente aceitar definicao de ferramentas, use:

```python
from redmine_project_agent import tool_definition

tool = tool_definition()
```

Contrato recomendado:

- o assistente conversa com o usuario;
- a ferramenta `avaliar_projeto_redmine` consulta e avalia;
- o Redmine client apenas busca dados;
- o gerador de relatorios atual continua separado;
- nenhuma resposta deve ser publicada no Redmine por este agente.

## O que ele avalia

- issues atrasadas;
- issues sem responsável;
- issues de alta prioridade;
- issues sem atualização recente;
- versões próximas com muitas pendências;
- excesso de trabalho em andamento;
- risco geral do projeto: `verde`, `amarelo`, `laranja` ou `vermelho`.

## Saída esperada

O agente retorna:

- status do projeto;
- resumo executivo;
- evidências;
- riscos principais;
- sugestões de decisão;
- perguntas úteis para o gestor;
- métricas usadas;
- nível de confiança.

## Próximo passo recomendado

Rodar por 1 ou 2 semanas em modo observador e comparar a análise do agente com a avaliação humana antes de conectar qualquer ação operacional.
