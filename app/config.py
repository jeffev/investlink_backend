from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
import os

load_dotenv()

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
# Em memória cada worker do gunicorn conta sozinho, então o limite efetivo é
# multiplicado pelo número de workers. Com RATELIMIT_STORAGE_URI apontando para
# um Redis (ex.: redis://redis:6379/0) a contagem passa a ser uma só.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)

# Teto do corpo da requisição. Nenhuma tela manda mais que alguns KB; sem teto,
# a conta demo — que qualquer visitante abre — gravava estratégia e layout do
# tamanho que quisesse no banco.
MAX_CONTENT_LENGTH = 1024 * 1024


def _is_production():
    return os.getenv("FLASK_ENV", "development").lower() == "production"


def resolve_jwt_secret():
    """
    Chave que assina os tokens.

    O default existe para o ambiente local e os testes subirem sem
    configuração. Em produção ele é público (está no repositório): quem o
    conhece assina um token com o `sub` do admin. Lá a ausência da variável
    derruba o boot, como já acontece com ADMIN_PASSWORD.
    """
    secret = os.getenv("JWT_SECRET_KEY")
    if secret:
        return secret
    if _is_production():
        raise RuntimeError("JWT_SECRET_KEY é obrigatório quando FLASK_ENV=production.")
    return "fallback_secret_key"


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///:memory:"
    )
    app.config["JWT_SECRET_KEY"] = resolve_jwt_secret()
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    # Os tokens carregam o id inteiro no `sub`. Do PyJWT 2.10 em diante o
    # `sub` precisa ser texto e o token antigo cairia em 422; desligar só essa
    # checagem de formato mantém as sessões abertas. Assinatura e expiração
    # continuam verificadas.
    app.config["JWT_VERIFY_SUB"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # Atrás do Caddy, o remote_addr é o do proxy: sem isto o limite de taxa
    # conta todo mundo como um IP só, e quem esgota o /login ou o /demo-login
    # tranca a entrada de todos os visitantes. PROXY_FIX_HOPS é o número de
    # proxies confiáveis na frente; só vale ligar quando a API não é
    # alcançável direto, senão o cliente forja o X-Forwarded-For.
    proxy_hops = int(os.getenv("PROXY_FIX_HOPS", "1" if _is_production() else "0"))
    if proxy_hops > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        return (
            jsonify({"message": "Muitas tentativas. Tente novamente em 1 minuto."}),
            429,
        )

    return app
