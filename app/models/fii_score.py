import json

from config import db


class FiiScore(db.Model):
    """
    O score de FII, uma linha por ticker e perfil.

    Tabela separada de `stock_scores` porque os pilares são outros: Graham, ROE
    e CAGR de lucro não existem num fundo imobiliário, e forçar os dois ativos
    na mesma estrutura produziria colunas sempre nulas de um lado ou do outro.

    Fundos inelegíveis também são gravados, com `eligible` falso e o motivo
    preenchido — sem isso ninguém consegue responder "por que XPML11 não
    aparece na lista?".
    """

    __tablename__ = "fii_scores"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(
        db.String(10), db.ForeignKey("fiis.ticker"), nullable=False, index=True
    )
    profile = db.Column(db.String(20), nullable=False)
    run_date = db.Column(db.DateTime, nullable=False)

    score_total = db.Column(db.Float)
    score_valuation = db.Column(db.Float)
    score_renda = db.Column(db.Float)
    score_liquidez = db.Column(db.Float)
    score_estrutura = db.Column(db.Float)
    score_ciclo = db.Column(db.Float)

    eligible = db.Column(db.Boolean, nullable=False, default=True)
    exclusion_reasons = db.Column(db.Text)
    reasons = db.Column(db.Text)
    red_flags = db.Column(db.Text)

    @staticmethod
    def _load(raw):
        if not raw:
            return []
        try:
            return json.loads(raw)
        except ValueError:
            return []

    def to_json(self):
        return {
            "ticker": self.ticker,
            "profile": self.profile,
            "run_date": self.run_date.isoformat() if self.run_date else None,
            "score_total": self.score_total,
            "pillars": [
                {
                    "key": "valuation",
                    "label": "Valuation",
                    "value": self.score_valuation,
                },
                {"key": "renda", "label": "Renda", "value": self.score_renda},
                {"key": "liquidez", "label": "Liquidez", "value": self.score_liquidez},
                {
                    "key": "estrutura",
                    "label": "Estrutura",
                    "value": self.score_estrutura,
                },
                {
                    "key": "ciclo",
                    "label": "Momento do ciclo",
                    "value": self.score_ciclo,
                },
            ],
            "eligible": self.eligible,
            "exclusion_reasons": self._load(self.exclusion_reasons),
            "reasons": self._load(self.reasons),
            "red_flags": self._load(self.red_flags),
        }
