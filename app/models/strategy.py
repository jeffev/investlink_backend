from datetime import datetime

from config import db


class Strategy(db.Model):
    __tablename__ = "strategies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    asset_type = db.Column(db.String(10), nullable=False)  # "STOCK" | "FII"
    filters = db.Column(db.Text, nullable=False)  # JSON array de filtros
    sorting = db.Column(db.Text, nullable=True)  # JSON array de ordenação
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="strategies")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<Strategy(user_id={self.user_id}, name={self.name}, asset_type={self.asset_type})>"

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "asset_type": self.asset_type,
            "filters": self.filters,
            "sorting": self.sorting,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
