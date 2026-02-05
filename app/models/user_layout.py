from config import db


class UserLayout(db.Model):
    __tablename__ = "user_layouts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    layout = db.Column(db.String(50), nullable=False)
    estado = db.Column(db.Text, nullable=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<UserLayout(user_id={self.user_id}, layout={self.layout}, estado={self.estado})>"

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "layout": self.layout,
            "estado": self.estado,
        }
