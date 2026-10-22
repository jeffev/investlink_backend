"""
A sonda de saúde é o que o deploy consulta para decidir entre seguir e reverter.

Se ela responder 200 com o banco fora de alcance, o deploy automático promove
uma versão quebrada; por isso o teste cobre principalmente o caminho de falha.
"""

from unittest.mock import patch


def test_health_responde_ok_com_banco_acessivel(app, client):
    app.add_url_rule("/health", view_func=_view())

    with patch("routes.health_routes.db") as mock_db:
        mock_db.session.execute.return_value = None
        response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_health_responde_503_quando_o_banco_nao_responde(app, client):
    app.add_url_rule("/health", view_func=_view())

    with patch("routes.health_routes.db") as mock_db:
        mock_db.session.execute.side_effect = Exception("connection refused")
        response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json()["status"] == "degraded"


def test_health_nao_exige_autenticacao():
    # Sonda não carrega token: se a rota fosse protegida, o orquestrador leria
    # 401 como aplicação de pé e nunca reiniciaria um contêiner quebrado.
    from utils import setup_routes
    from config import create_app

    application = create_app()
    setup_routes(application)

    rule = next(r for r in application.url_map.iter_rules() if r.rule == "/health")
    view = application.view_functions[rule.endpoint]

    assert not hasattr(view, "__wrapped__")


def _view():
    from routes.health_routes import health_json

    return health_json
