from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import AssistantKnowledgeChunk, AssistantKnowledgeDocument, User
from app.services.ai_model_service import generate_ai_text, resolve_ai_model


STOPWORDS = {
    "a",
    "as",
    "o",
    "os",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "e",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "para",
    "por",
    "com",
    "como",
    "que",
    "qual",
    "quais",
    "um",
    "uma",
    "me",
    "voce",
    "sistema",
}


@dataclass(frozen=True)
class KnowledgeHit:
    id: int
    title: str
    domain: str
    content: str
    score: float
    metadata: dict[str, Any]


class AssistantKnowledgeService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_seeded(self) -> int:
        existing = self.db.query(AssistantKnowledgeDocument).filter(
            AssistantKnowledgeDocument.source_key.like("system:%")
        ).count()
        if existing:
            return 0
        count = 0
        for doc in SYSTEM_DOCUMENTS:
            self.upsert_document(**doc)
            count += 1
        self.db.commit()
        return count

    def upsert_document(
        self,
        *,
        source_key: str,
        title: str,
        domain: str,
        content: str,
        metadata_json: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> AssistantKnowledgeDocument:
        document = (
            self.db.query(AssistantKnowledgeDocument)
            .filter(AssistantKnowledgeDocument.source_key == source_key)
            .first()
        )
        if not document:
            document = AssistantKnowledgeDocument(source_key=source_key)
            self.db.add(document)
        document.title = title
        document.domain = domain
        document.content = content.strip()
        document.metadata_json = metadata_json or {}
        document.is_active = is_active
        self.db.flush()

        self.db.query(AssistantKnowledgeChunk).filter(AssistantKnowledgeChunk.document_id == document.id).delete()
        for index, chunk in enumerate(_chunk_text(document.content)):
            self.db.add(
                AssistantKnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    title=title,
                    domain=domain,
                    content=chunk,
                    keywords_json=_keywords(f"{title} {domain} {chunk}"),
                    metadata_json={"source_key": source_key, **(metadata_json or {})},
                )
            )
        return document

    def search(self, query: str, *, limit: int = 5, min_score: float = 0.12) -> list[KnowledgeHit]:
        self.ensure_seeded()
        query_keywords = _keywords(query)
        if not query_keywords:
            return []
        chunks = (
            self.db.query(AssistantKnowledgeChunk)
            .join(AssistantKnowledgeDocument)
            .filter(AssistantKnowledgeDocument.is_active.is_(True))
            .all()
        )
        hits: list[KnowledgeHit] = []
        for chunk in chunks:
            score = _score(query_keywords, chunk.keywords_json or [], chunk.content, chunk.title, chunk.domain)
            if score >= min_score:
                hits.append(
                    KnowledgeHit(
                        id=chunk.id,
                        title=chunk.title,
                        domain=chunk.domain,
                        content=chunk.content,
                        score=round(score, 4),
                        metadata=chunk.metadata_json or {},
                    )
                )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def context_for_prompt(self, query: str, *, limit: int = 5) -> str:
        hits = self.search(query, limit=limit)
        if not hits:
            return ""
        parts = []
        for index, hit in enumerate(hits, start=1):
            parts.append(f"[{index}] {hit.title} ({hit.domain}, score={hit.score})\n{hit.content}")
        return "\n\n".join(parts)

    def answer_question(self, query: str, user: User | None = None) -> tuple[str, dict[str, Any]] | None:
        hits = self.search(query, limit=5, min_score=0.16)
        if not hits:
            return None
        context = "\n\n".join(f"- {hit.title} ({hit.domain}): {hit.content}" for hit in hits)
        model = resolve_ai_model(self.db, "assistant")
        if model.api_key:
            try:
                answer = generate_ai_text(
                    model,
                    system_instruction=(
                        "Voce responde perguntas sobre o sistema ASM Digital usando apenas a base de conhecimento enviada. "
                        "Se a pergunta pedir execucao de acao, explique a funcionalidade e diga que o Assistente deve pedir confirmacao quando alterar dados. "
                        "Responda em portugues, de forma direta."
                    ),
                    prompt=f"Pergunta: {query}\n\nBase de conhecimento:\n{context}",
                    max_tokens=900,
                ).strip()
                if answer:
                    return answer, {"knowledge_hits": [hit.__dict__ for hit in hits]}
            except Exception:
                pass
        first = hits[0]
        return first.content, {"knowledge_hits": [hit.__dict__ for hit in hits]}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.lower().strip().split())


def _keywords(value: str) -> list[str]:
    normalized = _normalize(value)
    tokens = re.findall(r"[a-z0-9_]{3,}", normalized)
    return sorted({token for token in tokens if token not in STOPWORDS})


def _score(query_keywords: list[str], chunk_keywords: list[str], content: str, title: str, domain: str) -> float:
    chunk_set = set(chunk_keywords)
    query_set = set(query_keywords)
    if not query_set or not chunk_set:
        return 0.0
    overlap = len(query_set.intersection(chunk_set)) / max(len(query_set), 1)
    normalized_text = _normalize(f"{title} {domain} {content}")
    phrase_bonus = 0.0
    for token in query_set:
        if token in normalized_text:
            phrase_bonus += 0.015
    return overlap + min(phrase_bonus, 0.25)


def _chunk_text(content: str, max_chars: int = 1400) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content.strip()) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks or [content.strip()]


SYSTEM_DOCUMENTS: list[dict[str, Any]] = [
    {
        "source_key": "system:assistant-core",
        "title": "Assistente Operacional ASM Digital",
        "domain": "general",
        "metadata_json": {"generated_from": "assistant_core"},
        "content": """
O Assistente Operacional do ASM Digital permite consultar informacoes e executar funcionalidades do sistema por chat ou voz.
Ele interpreta a intencao, identifica dominio e acao, valida permissao, monta previa da acao e registra historico.
Acoes que alteram dados ou disparam efeitos externos exigem confirmacao antes de executar.
Consultas somente leitura podem responder diretamente.
Dominios conhecidos: Relatorios IA, Relatorios Redmine, Rotinas, Notificacoes, Funcionarios, Eventos Gerenciais, Pendencias, Avaliacao 360, ChefIA/FalaAI, Conectores e Agendamento de reunioes.
""",
    },
    {
        "source_key": "system:evaluation-360",
        "title": "Avaliacao 360",
        "domain": "evaluation",
        "metadata_json": {"generated_from": "evaluation_models_and_routes"},
        "content": """
A area de Avaliacao 360 trabalha com ciclos de avaliacao, funcionarios avaliados, respostas 360, pontuacoes consolidadas, potencial, alertas e analise de feedback por IA.
O Assistente pode consultar a situacao de avaliacao 360 de um funcionario pelo nome, por exemplo: "Como esta avaliacao 360 do Leandro Montenegro Machado?".
Para responder, o Assistente busca o funcionario, localiza o ciclo mais recente com dados vinculados e retorna ciclo, status, notas de performance, comportamento e potencial, nota final preliminar, categoria sugerida ou final, posicao nine box, media dos feedbacks por tipo de relacao, resumo gerado por IA, feedback sugerido e alertas.
A consulta de Avaliacao 360 e somente leitura e nao exige confirmacao.
Alteracoes de ciclos, importacoes, calibracoes, calculo de notas e execucao de analise IA devem ser feitas por usuarios autorizados nas telas especificas ou por acoes futuras com confirmacao.
""",
    },
    {
        "source_key": "system:reports-redmine",
        "title": "Relatorios Redmine",
        "domain": "reports_redmine",
        "metadata_json": {"generated_from": "reports_action"},
        "content": """
Relatorios Redmine consultam demandas, chamados e entregas a partir de templates de relatorio e conectores externos.
O Assistente entende pedidos como listar demandas abertas, demandas por responsavel, demandas atrasadas e executar relatorio Redmine.
Executar relatorio pode criar nova execucao e consultar conector externo, por isso exige confirmacao.
Depois de confirmado, o Assistente deve responder a pergunta com um resumo do resultado e tambem informar o link do relatorio completo quando houver registros.
""",
    },
    {
        "source_key": "system:routines-notifications",
        "title": "Rotinas e Notificacoes",
        "domain": "routines",
        "metadata_json": {"generated_from": "assistant_capabilities"},
        "content": """
Rotinas automatizam execucoes periodicas, como gerar relatorios em horarios definidos e disparar etapas operacionais.
Criar, editar, excluir ou executar rotina com efeito externo exige confirmacao.
Notificacoes podem ser enviadas a responsaveis ou grupos com base em relatorios e regras. Enviar notificacao exige confirmacao.
O Assistente deve mostrar parametros identificados, dados faltantes, impacto e risco antes de confirmar.
""",
    },
    {
        "source_key": "system:employees-pending",
        "title": "Funcionarios e Pendencias",
        "domain": "employees",
        "metadata_json": {"generated_from": "assistant_capabilities"},
        "content": """
Funcionarios representam colaboradores cadastrados no ASM Digital, com nome, e-mail, setor, cargo, gestor, status ativo e participacao em avaliacao.
Consultar funcionarios e uma acao de leitura. Cadastrar, editar ou alterar funcionario exige permissao administrativa e confirmacao.
Pendencias representam itens operacionais que podem ser consultados, resolvidos, ignorados ou escalados.
Resolver, ignorar ou escalar pendencia altera dados e exige confirmacao.
""",
    },
    {
        "source_key": "system:permissions-confirmations",
        "title": "Permissoes e Confirmacoes",
        "domain": "general",
        "metadata_json": {"generated_from": "assistant_permissions"},
        "content": """
Regras iniciais de permissao do Assistente: admin pode executar tudo; gerente pode consultar e executar acoes operacionais como relatorios, rotinas, notificacoes e pendencias; funcionario pode consultar informacoes permitidas e solicitar leituras.
Acoes administrativas exigem admin.
Nenhuma acao que altera dados deve ser executada diretamente: criar ou editar templates, criar rotinas, enviar notificacoes, criar ou resolver pendencias, alterar funcionarios, alterar regras, agendar reuniao e alterar conectores exigem confirmacao.
""",
    },
]
