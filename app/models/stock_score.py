import json

from config import db


class StockScore(db.Model):
    """
    The five-pillar fundamental score, one row per ticker per profile.

    Ineligible companies are stored too, with `eligible` false and the reason
    filled in. A screener that simply omits them cannot answer the question the
    investor actually asks — "why isn't PETR4 on this list?".
    """

    __tablename__ = "stock_scores"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(
        db.String(10), db.ForeignKey("stocks.ticker"), nullable=False, index=True
    )
    profile = db.Column(db.String(20), nullable=False)
    run_date = db.Column(db.DateTime, nullable=False)

    score_total = db.Column(db.Float)
    score_valuation = db.Column(db.Float)
    score_qualidade = db.Column(db.Float)
    score_saude = db.Column(db.Float)
    score_crescimento = db.Column(db.Float)
    score_dividendos = db.Column(db.Float)
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
                {
                    "key": "qualidade",
                    "label": "Qualidade",
                    "value": self.score_qualidade,
                },
                {
                    "key": "saude",
                    "label": "Saúde financeira",
                    "value": self.score_saude,
                },
                {
                    "key": "crescimento",
                    "label": "Crescimento",
                    "value": self.score_crescimento,
                },
                {
                    "key": "dividendos",
                    "label": "Dividendos",
                    "value": self.score_dividendos,
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
