"""add the job run log and the daily score snapshot

Duas tabelas que mudam a natureza do produto, não só o esquema.

`job_runs` existe porque a atualização passou a rodar sozinha: sem registro de
execução, a tela não consegue dizer "atualizado há 2 horas" e ninguém descobre
que a rotina parou — o sintoma é "os dados congelaram", sem lugar para olhar.

`score_snapshots` existe porque `refresh_scores` apaga e reescreve a tabela de
score a cada execução, o que apaga a memória do produto. Sem o dia anterior não
há "entrou na lista hoje" nem "subiu 12 pontos na semana" — a diferença entre
um catálogo e um radar.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-10-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_name", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_runs_job_name", "job_runs", ["job_name"])
    # A tela pede sempre a última execução de um job; sem o índice composto
    # isso vira varredura da tabela inteira a cada abertura da vitrine.
    op.create_index(
        "ix_job_runs_nome_inicio", "job_runs", ["job_name", "started_at"]
    )

    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=4), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("profile", sa.String(length=20), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("score_total", sa.Float(), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        # Torna a gravação idempotente: rodar duas vezes no mesmo dia
        # atualiza a linha em vez de duplicar o histórico.
        sa.UniqueConstraint(
            "asset_type",
            "ticker",
            "profile",
            "snapshot_date",
            name="uq_score_snapshot_dia",
        ),
    )
    op.create_index("ix_score_snapshots_ticker", "score_snapshots", ["ticker"])
    op.create_index(
        "ix_score_snapshots_data", "score_snapshots", ["snapshot_date"]
    )
    # O delta compara duas datas de um mesmo perfil e tipo de ativo.
    op.create_index(
        "ix_score_snapshots_consulta",
        "score_snapshots",
        ["asset_type", "profile", "snapshot_date"],
    )


def downgrade():
    op.drop_index("ix_score_snapshots_consulta", table_name="score_snapshots")
    op.drop_index("ix_score_snapshots_data", table_name="score_snapshots")
    op.drop_index("ix_score_snapshots_ticker", table_name="score_snapshots")
    op.drop_table("score_snapshots")

    op.drop_index("ix_job_runs_nome_inicio", table_name="job_runs")
    op.drop_index("ix_job_runs_job_name", table_name="job_runs")
    op.drop_table("job_runs")
