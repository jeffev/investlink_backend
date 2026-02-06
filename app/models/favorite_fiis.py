from config import db


class FavoriteFii(db.Model):
    __tablename__ = "favorites_fii"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    fii_ticker = db.Column(db.String(10), db.ForeignKey("fiis.ticker"))
    ceiling_price = db.Column(db.Float)
    target_price = db.Column(db.Float)

    user = db.relationship("User", backref="favorites_fii")
    fii = db.relationship("Fii", backref="favorites_fii")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return (
            f"<FavoriteFII(user_id={self.user_id}, fii_ticker={self.fii_ticker}, "
            f"ceiling_price={self.ceiling_price}, target_price={self.target_price})>"
        )

    def to_json(self):
        fii_json = self.fii.to_json() if self.fii else None
        return {
            "id": self.id,
            "user_id": self.user_id,
            "fii": fii_json,
            "ceiling_price": self.ceiling_price,
            "target_price": self.target_price,
        }
