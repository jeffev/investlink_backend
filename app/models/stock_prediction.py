from config import db


class StockPrediction(db.Model):
    __tablename__ = "stock_predictions"

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), db.ForeignKey("stocks.ticker"), nullable=False)
    run_date = db.Column(db.DateTime, nullable=False)
    label = db.Column(db.String(20), nullable=False)
    prob_barata = db.Column(db.Float)
    prob_neutra = db.Column(db.Float)
    prob_cara = db.Column(db.Float)
    composite_score = db.Column(db.Float)
    model_version = db.Column(db.String(50))

    def to_json(self):
        return {
            "ticker": self.ticker,
            "label": self.label,
            "prob_barata": self.prob_barata,
            "prob_neutra": self.prob_neutra,
            "prob_cara": self.prob_cara,
            "composite_score": self.composite_score,
            "model_version": self.model_version,
            "run_date": self.run_date.isoformat() if self.run_date else None,
        }
