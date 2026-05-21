"""add assistant knowledge base

Revision ID: 20260521_0024
Revises: 20260520_0023
Create Date: 2026-05-21 15:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260521_0024"
down_revision = "20260520_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_assistant_knowledge_documents_source_key"),
    )
    op.create_index(op.f("ix_assistant_knowledge_documents_id"), "assistant_knowledge_documents", ["id"], unique=False)
    op.create_index("ix_assistant_knowledge_documents_source_key", "assistant_knowledge_documents", ["source_key"], unique=False)
    op.create_index("ix_assistant_knowledge_documents_domain", "assistant_knowledge_documents", ["domain"], unique=False)
    op.create_index("ix_assistant_knowledge_documents_is_active", "assistant_knowledge_documents", ["is_active"], unique=False)

    op.create_table(
        "assistant_knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["assistant_knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assistant_knowledge_chunks_id"), "assistant_knowledge_chunks", ["id"], unique=False)
    op.create_index("ix_assistant_knowledge_chunks_document_id", "assistant_knowledge_chunks", ["document_id"], unique=False)
    op.create_index("ix_assistant_knowledge_chunks_domain", "assistant_knowledge_chunks", ["domain"], unique=False)
    op.create_index("ix_assistant_knowledge_chunks_document_chunk", "assistant_knowledge_chunks", ["document_id", "chunk_index"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_assistant_knowledge_chunks_document_chunk", table_name="assistant_knowledge_chunks")
    op.drop_index("ix_assistant_knowledge_chunks_domain", table_name="assistant_knowledge_chunks")
    op.drop_index("ix_assistant_knowledge_chunks_document_id", table_name="assistant_knowledge_chunks")
    op.drop_index(op.f("ix_assistant_knowledge_chunks_id"), table_name="assistant_knowledge_chunks")
    op.drop_table("assistant_knowledge_chunks")
    op.drop_index("ix_assistant_knowledge_documents_is_active", table_name="assistant_knowledge_documents")
    op.drop_index("ix_assistant_knowledge_documents_domain", table_name="assistant_knowledge_documents")
    op.drop_index("ix_assistant_knowledge_documents_source_key", table_name="assistant_knowledge_documents")
    op.drop_index(op.f("ix_assistant_knowledge_documents_id"), table_name="assistant_knowledge_documents")
    op.drop_table("assistant_knowledge_documents")
