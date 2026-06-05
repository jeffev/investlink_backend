from datetime import datetime

from config import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    asset_type = db.Column(
        db.String(10), nullable=False, default="STOCK"
    )  # STOCK | FII
    type = db.Column(db.String(10), nullable=False)  # COMPRA | VENDA
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)  # quantity * price
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="transactions")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.total = round(self.quantity * self.price, 2)

    def __repr__(self):
        return f"<Transaction(user={self.user_id}, {self.type} {self.ticker} x{self.quantity})>"

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "asset_type": self.asset_type,
            "type": self.type,
            "quantity": self.quantity,
            "price": self.price,
            "total": self.total,
            "date": self.date.isoformat() if self.date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
