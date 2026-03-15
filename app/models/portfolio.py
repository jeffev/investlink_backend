from datetime import datetime

from config import db


class Portfolio(db.Model):
    __tablename__ = "portfolio"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker = db.Column(db.String(10), db.ForeignKey("stocks.ticker"), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    average_price = db.Column(db.Float, nullable=False)
    total_invested = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship("User", backref="portfolio")
    stock = db.relationship("Stock", backref="portfolio")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.total_invested = round(self.quantity * self.average_price, 2)

    def __repr__(self):
        return (
            f"<Portfolio(user_id={self.user_id}, ticker={self.ticker}, "
            f"quantity={self.quantity}, average_price={self.average_price})>"
        )

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "total_invested": self.total_invested,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
