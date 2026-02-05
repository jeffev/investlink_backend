from config import db


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    stock_ticker = db.Column(db.String(10), db.ForeignKey("stocks.ticker"))
    ceiling_price = db.Column(db.Float)
    target_price = db.Column(db.Float)

    user = db.relationship("User", backref="favorites")
    stock = db.relationship("Stock", backref="favorites")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<Favorite(user_id={self.user_id}, stock_ticker={self.stock_ticker}, ceiling_price={self.ceiling_price}, target_price={self.target_price})>"

    def to_json(self):
        stock_json = self.stock.to_json() if self.stock else None
        return {
            "id": self.id,
            "user_id": self.user_id,
            "stock": stock_json,
            "ceiling_price": self.ceiling_price,
            "target_price": self.target_price,
        }
