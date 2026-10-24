from config import db


class ScoreSnapshot(db.Model):
    """
    A nota de cada ativo, guardada por dia.

    `refresh_scores` apaga a tabela de score e reescreve do zero a cada
    execução. Isso mantém a nota sempre coerente com o retrato atual — e
    apaga a memória do produto: sem o dia anterior, não dá para dizer o que
    entrou na lista hoje, quem subiu de nota na semana nem quem saiu.

    É a diferença entre um catálogo e um radar. O catálogo responde "quais são
    os melhores agora"; o radar responde "o que mudou desde a última vez que
    você olhou", que é a única razão de abrir o app amanhã de novo.

    Guarda só o essencial para o delta — nota e elegibilidade. Os motivos e os
    alertas continuam em `stock_scores`/`fii_scores`, sempre do retrato atual,
    porque explicar o passado exigiria o fundamento daquele dia, que não é o
    que está gravado.
    """

    __tablename__ = "score_snapshots"
    __table_args__ = (
        db.UniqueConstraint(
            "asset_type",
            "ticker",
            "profile",
            "snapshot_date",
            name="uq_score_snapshot_dia",
        ),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.String(4), nullable=False)
    ticker = db.Column(db.String(10), nullable=False, index=True)
    profile = db.Column(db.String(20), nullable=False)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)

    score_total = db.Column(db.Float)
    eligible = db.Column(db.Boolean, nullable=False, default=True)

    def to_json(self):
        return {
            "asset_type": self.asset_type,
            "ticker": self.ticker,
            "profile": self.profile,
            "snapshot_date": (
                self.snapshot_date.isoformat() if self.snapshot_date else None
            ),
            "score_total": self.score_total,
            "eligible": self.eligible,
        }
