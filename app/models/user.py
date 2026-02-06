from config import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(80))
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    profile = db.Column(db.String(255))
    password = db.Column(db.String(255))

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return (
            f"<User(user_name={self.user_name}, name={self.name}, "
            f"email={self.email}, profile={self.profile})>"
        )

    def to_json(self):
        return {
            "id": self.id,
            "user_name": self.user_name,
            "name": self.name,
            "email": self.email,
            "profile": self.profile,
        }
