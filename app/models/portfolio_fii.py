from datetime import datetime

from config import db


class PortfolioFii(db.Model):
    __tablename__ = "portfolio_fii"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    fii_ticker = db.Column(db.String(10), db.ForeignKey("fiis.ticker"), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    average_price = db.Column(db.Float, nullable=False)
    total_invested = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship("User", backref="portfolio_fii")
    fii = db.relationship("Fii", backref="portfolio_fii")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.total_invested = round(self.quantity * self.average_price, 2)

    def __repr__(self):
        return (
            f"<PortfolioFii(user_id={self.user_id}, fii_ticker={self.fii_ticker}, "
            f"quantity={self.quantity}, average_price={self.average_price})>"
        )

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "fii_ticker": self.fii_ticker,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "total_invested": self.total_invested,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
