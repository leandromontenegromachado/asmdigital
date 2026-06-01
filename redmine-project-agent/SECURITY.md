# Segurança e permissões

Este agente foi desenhado para operar em modo consultivo.

## Permissões recomendadas no Redmine

Use um usuário/token com acesso apenas de leitura.

Permitir:

- visualizar projetos;
- visualizar issues;
- visualizar versões;
- visualizar usuários e responsáveis;
- visualizar comentários/journals quando necessário para análise.

Não permitir:

- criar issues;
- editar issues;
- comentar em issues;
- alterar status;
- alterar responsável;
- alterar prioridade;
- alterar versão;
- excluir qualquer dado.

## Garantias da primeira versão

O código atual usa apenas chamadas `GET` no cliente Redmine.

Arquivos relevantes:

- `redmine_project_agent/redmine_client.py`
- `redmine_project_agent/cli.py`

Se no futuro forem adicionadas ações, elas devem ficar em outro módulo e exigir aprovação explícita.
