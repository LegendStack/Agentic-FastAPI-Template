"""Add HNSW index for pgvector and cost tracking table.

Revision ID: d5e8f3b2a1c9
Revises: c4219a7d8b2e
Create Date: 2026-01-31 20:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e8f3b2a1c9"
down_revision: str | None = "c4219a7d8b2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add HNSW index for faster approximate nearest neighbor search
    and create the cost tracking table.
    """
    # Create HNSW index on document_section embedding column
    # HNSW provides faster queries at the cost of slightly less precision
    # m=16: number of connections per layer
    # ef_construction=64: quality of index construction
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_section_embedding_hnsw_idx
        ON document_section
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # Create LLM cost tracking table
    op.create_table(
        "llm_cost_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("thread_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(32), default="azure_openai"),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(32), default="chat"),
        sa.Column("input_tokens", sa.Integer(), default=0),
        sa.Column("output_tokens", sa.Integer(), default=0),
        sa.Column("total_tokens", sa.Integer(), default=0),
        sa.Column("input_cost_cents", sa.Numeric(10, 4), default=0),
        sa.Column("output_cost_cents", sa.Numeric(10, 4), default=0),
        sa.Column("total_cost_cents", sa.Numeric(10, 4), default=0),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("metadata_json", sa.JSON(), default={}),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
    )

    # Create indexes for common queries
    op.create_index("ix_llm_cost_records_request_id", "llm_cost_records", ["request_id"])
    op.create_index("ix_llm_cost_records_thread_id", "llm_cost_records", ["thread_id"])
    op.create_index("ix_llm_cost_records_user_id", "llm_cost_records", ["user_id"])
    op.create_index("ix_llm_cost_records_tenant_id", "llm_cost_records", ["tenant_id"])
    op.create_index("ix_llm_cost_records_created_at", "llm_cost_records", ["created_at"])


def downgrade() -> None:
    """Remove HNSW index and cost tracking table."""
    op.drop_index("ix_llm_cost_records_created_at", table_name="llm_cost_records")
    op.drop_index("ix_llm_cost_records_tenant_id", table_name="llm_cost_records")
    op.drop_index("ix_llm_cost_records_user_id", table_name="llm_cost_records")
    op.drop_index("ix_llm_cost_records_thread_id", table_name="llm_cost_records")
    op.drop_index("ix_llm_cost_records_request_id", table_name="llm_cost_records")
    op.drop_table("llm_cost_records")

    op.execute("DROP INDEX IF EXISTS document_section_embedding_hnsw_idx;")
