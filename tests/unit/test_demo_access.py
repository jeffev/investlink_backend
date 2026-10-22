"""
As travas que a demo pública exige.

Na demo todo visitante entra pela mesma conta, então qualquer rota que um
usuário comum alcança vira rota de qualquer pessoa da internet. Antes destas
travas um usuário comum listava e apagava contas alheias e editava ou excluía
ações e FIIs da base inteira.
"""

from unittest.mock import patch

import pytest

from models.user import User
from routes.user_routes import (
    change_password_json,
    edit_user_json,
    new_user_json,
    view_user_json,
)
from utils import setup_routes

COMUM = User(id=7, user_name="comum", profile="USER")
ADMIN = User(id=1, user_name="admin", profile="ADMIN")
DEMO = User(id=5, user_name="demo", profile="USER")


def _status(resposta):
    return resposta[1]


def _chamar(app, view, user_id, logado, alvo=None, json=None, env=None):
    alvo = alvo or logado
    with app.test_request_context(json=json or {}):
        with (
            patch("routes.user_routes.get_jwt_identity", return_value=logado.id),
            patch("routes.user_routes.db") as db,
            patch.dict("os.environ", env or {}, clear=False),
        ):
            db.session.get.side_effect = lambda _model, uid: {
                logado.id: logado,
                alvo.id: alvo,
            }.get(uid)
            with patch("routes.user_routes.view_user", return_value=("ok", 200)):
                with patch(
                    "routes.user_routes.change_password", return_value=("ok", 200)
                ):
                    with patch(
                        "routes.user_routes.edit_user", return_value=("ok", 200)
                    ):
                        return view(user_id)


def test_usuario_comum_nao_ve_conta_alheia(app):
    assert _status(_chamar(app, view_user_json, ADMIN.id, COMUM, ADMIN)) == 403


def test_usuario_ve_a_propria_conta(app):
    assert _status(_chamar(app, view_user_json, COMUM.id, COMUM)) == 200


def test_admin_ve_qualquer_conta(app):
    assert _status(_chamar(app, view_user_json, COMUM.id, ADMIN, COMUM)) == 200


def test_usuario_comum_nao_troca_senha_alheia(app):
    payload = {"current_password": "a", "new_password": "b"}
    resposta = _chamar(app, change_password_json, ADMIN.id, COMUM, ADMIN, payload)
    assert _status(resposta) == 403


def test_a_conta_demo_nao_troca_a_senha(app):
    # Senão o primeiro visitante trocava a senha e trancava a demo para o resto.
    payload = {"current_password": "a", "new_password": "b"}
    env = {"DEMO_USER_NAME": "demo"}
    resposta = _chamar(app, change_password_json, DEMO.id, DEMO, json=payload, env=env)
    assert _status(resposta) == 403


def test_a_conta_demo_nao_e_editada(app):
    env = {"DEMO_USER_NAME": "demo"}
    resposta = _chamar(app, edit_user_json, DEMO.id, DEMO, json={"name": "x"}, env=env)
    assert _status(resposta) == 403


def test_cadastro_fechado_devolve_403(app):
    with app.test_request_context(json={}):
        with (
            patch.dict("os.environ", {"ALLOW_SIGNUP": "false"}),
            patch("routes.user_routes.new_user") as service,
        ):
            resposta = new_user_json()
    assert _status(resposta) == 403
    service.assert_not_called()


@pytest.mark.parametrize(
    "metodo, rota",
    [
        ("GET", "/v1/users"),
        ("DELETE", "/v1/user/<int:user_id>"),
        ("POST", "/v1/stocks"),
        ("PUT", "/v1/stock/<string:ticker>"),
        ("DELETE", "/v1/stock/<string:ticker>"),
        ("POST", "/v1/fiis"),
        ("PUT", "/v1/fii/<string:ticker>"),
        ("DELETE", "/v1/fii/<string:ticker>"),
    ],
)
def test_rotas_que_mexem_na_base_exigem_admin(metodo, rota):
    from flask import Flask

    registradas = {}
    falso = Flask(__name__)
    falso.add_url_rule = lambda path, methods, view_func: registradas.update(
        {(methods[0], path): view_func}
    )

    with patch("utils.protected_route") as protegida:
        protegida.side_effect = lambda view, required_profile=None: (
            view,
            required_profile,
        )
        setup_routes(falso)

    assert registradas[(metodo, rota)][1] == "ADMIN"
