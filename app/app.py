import bcrypt
import logging
import os
import secrets

from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from flask_migrate import upgrade

from utils import setup_routes
from config import create_app, db
from models.user import User

logger = logging.getLogger(__name__)

app = create_app()

setup_routes(app)

# Em produção o frontend mora em outro domínio (Vercel); CORS_ORIGINS lista os
# domínios aceitos, separados por vírgula. Sem a variável, vale qualquer origem,
# que é o que o desenvolvimento local espera.
_cors_origins = [
    o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()
]
CORS(app, origins=_cors_origins or "*")

# Swagger configuration
SWAGGER_URL = "/swagger"
API_URL = "/static/swagger.json"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "InvestLink"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


def is_production():
    return os.environ.get("FLASK_ENV", "development").lower() == "production"


def resolve_admin_password():
    """
    Senha do primeiro acesso.

    O default "admin" existe para o ambiente local subir sem configuração. Em
    produção ele seria uma credencial pública, então lá a ausência da variável
    derruba o boot em vez de criar um usuário com senha conhecida.
    """
    password = os.environ.get("ADMIN_PASSWORD")
    if password:
        return password
    if is_production():
        raise RuntimeError("ADMIN_PASSWORD é obrigatório quando FLASK_ENV=production.")
    return "admin"


def seed_admin():
    existing = User.query.filter_by(user_name="admin").first()
    if existing:
        return
    password = resolve_admin_password().encode("utf-8")
    hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8")
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


def seed_demo_user():
    """
    Conta compartilhada da demo pública, criada quando DEMO_USER_NAME existe.
    A entrada é pelo /v1/user/demo-login, sem senha; a senha gravada é
    aleatória e ninguém a conhece, então o login comum nunca abre essa conta.
    """
    user_name = os.environ.get("DEMO_USER_NAME")
    if not user_name or User.query.filter_by(user_name=user_name).first():
        return
    unusable = secrets.token_urlsafe(32).encode("utf-8")
    demo = User(
        user_name=user_name,
        name="Visitante",
        email=f"{user_name}@investlink.local",
        profile="USER",
        password=bcrypt.hashpw(unusable, bcrypt.gensalt()).decode("utf-8"),
    )
    db.session.add(demo)
    db.session.commit()


def prepare_database():
    """
    Deixa o banco pronto para receber tráfego: migrações e usuário inicial.

    Chamada tanto pelo `python app/app.py` local quanto pelo entrypoint do
    contêiner, antes de o gunicorn subir — aplicar migração com a aplicação já
    servindo é o que produz erro de coluna inexistente no meio do deploy.
    """
    with app.app_context():
        upgrade()
        seed_admin()
        seed_demo_user()


if __name__ == "__main__":
    prepare_database()
    app.run(host="0.0.0.0", port=5000, debug=not is_production())
