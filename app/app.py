import bcrypt
import logging

from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from flask_migrate import upgrade

from utils import setup_routes
from config import create_app, db
from models.user import User

logger = logging.getLogger(__name__)

app = create_app()

setup_routes(app)

CORS(app)

# Swagger configuration
SWAGGER_URL = "/swagger"
API_URL = "/static/swagger.json"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "InvestLink"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


def seed_admin():
    existing = User.query.filter_by(user_name="admin").first()
    if existing:
        return
    hashed = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8")
    admin = User(
        user_name="admin",
        name="Administrador",
        email="admin@investlink.local",
        profile="ADMIN",
        password=hashed,
    )
    db.session.add(admin)
    db.session.commit()
    logger.info("Usuário admin criado com sucesso.")


if __name__ == "__main__":
    with app.app_context():
        upgrade()
        seed_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
