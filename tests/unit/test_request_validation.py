"""
A validação de entrada na borda HTTP, endpoint por endpoint.

Os schemas Marshmallow existiam desde o sprint E e nunca tinham sido chamados:
não havia um `.load()` no backend inteiro. O que este arquivo cobre é o que
passava por causa disso — inclusive dois buracos que não eram de formato:

    O cadastro é público e o serviço fazia `User(**user_data)`, então
    `"profile": "ADMIN"` no corpo saía com perfil de administrador.

    A favorita aceitava `user_id` pelo corpo e nunca o comparava com o de quem
    pediu, então dava para criar favorita na conta de outro.

Os testes chamam as funções de rota dentro de um `test_request_context`, que é
onde o corpo é lido — o serviço é dublê.
"""

from unittest.mock import MagicMock, patch

import pytest

from models.user import User
from routes.favorite_fii_routes import edit_favorite_fii_json, new_favorite_fii_json
from routes.favorite_routes import edit_favorite_json, new_favorite_json
from routes.portfolio_routes import (
    add_fii_position_json,
    add_position_json,
    edit_position_json,
)
from routes.stock_routes import list_stocks_json
from routes.user_routes import (
    change_password_json,
    edit_user_json,
    login_user_json,
    new_user_json,
)

TOKEN_USER_ID = 7
OUTRO_USUARIO = 99


def _body(response):
    return response[0].get_json()


def _status(response):
    return response[1]


# ── Cadastro público ─────────────────────────────────────────────────────────


def _registrar(app, payload):
    with app.test_request_context(json=payload):
        with patch("routes.user_routes.new_user") as service:
            service.return_value = (MagicMock(), 201)
            resposta = new_user_json()
        return resposta, service


VALIDO = {
    "user_name": "novousuario",
    "name": "Novo Usuário",
    "email": "novo@exemplo.com",
    "password": "senha-secreta",
}


def test_o_cadastro_publico_nao_deixa_escolher_o_perfil(app):
    # Era escalação de privilégio de verdade: `POST /v1/users` não exige token,
    # e o perfil ADMIN libera /v1/stocks/update e a reconciliação.
    resposta, service = _registrar(app, {**VALIDO, "profile": "ADMIN"})

    assert _status(resposta) == 201
    enviado = service.call_args[0][0]
    assert "profile" not in enviado


def test_o_cadastro_passa_os_campos_declarados(app):
    _, service = _registrar(app, VALIDO)
    assert service.call_args[0][0] == VALIDO


def test_cadastro_sem_campo_obrigatorio_e_recusado(app):
    resposta, service = _registrar(app, {"user_name": "alguem"})

    assert _status(resposta) == 400
    assert set(_body(resposta)["errors"]) == {"name", "email", "password"}
    service.assert_not_called()


def test_email_invalido_e_recusado_antes_do_servico(app):
    resposta, service = _registrar(app, {**VALIDO, "email": "nao-e-email"})

    assert _status(resposta) == 400
    assert "email" in _body(resposta)["errors"]
    service.assert_not_called()


def test_email_com_pontos_consecutivos_e_recusado(app):
    # Regra do projeto, documentada no CLAUDE.md; o `fields.Email` do
    # marshmallow concorda com ela.
    resposta, _ = _registrar(app, {**VALIDO, "email": "no..me@exemplo.com"})
    assert _status(resposta) == 400


def test_usuario_com_formato_invalido_e_recusado(app):
    resposta, _ = _registrar(app, {**VALIDO, "user_name": "ab"})

    assert _status(resposta) == 400
    assert "user_name" in _body(resposta)["errors"]


def test_campo_desconhecido_e_descartado_em_silencio(app):
    _, service = _registrar(app, {**VALIDO, "is_admin": True, "id": 1})
    enviado = service.call_args[0][0]

    assert "is_admin" not in enviado
    assert "id" not in enviado


# ── Corpo malformado ─────────────────────────────────────────────────────────


def test_corpo_ausente_devolve_400_e_nao_500(app):
    # A rota fazia `dados["user_id"] = ...` logo depois do get_json(), então um
    # pedido sem corpo virava TypeError e era contado como falha do servidor.
    with app.test_request_context(json=None):
        with patch("routes.user_routes.new_user") as service:
            resposta = new_user_json()

    assert _status(resposta) == 400
    service.assert_not_called()


def test_corpo_que_nao_e_objeto_devolve_400(app):
    with app.test_request_context(json=["isto", "e", "uma", "lista"]):
        resposta = new_user_json()

    assert _status(resposta) == 400
    assert "_body" in _body(resposta)["errors"]


def test_corpo_que_nao_e_json_devolve_400(app):
    with app.test_request_context(data="isto não é json", content_type="text/plain"):
        resposta = new_user_json()

    assert _status(resposta) == 400


# ── Login e troca de senha ───────────────────────────────────────────────────


def test_login_sem_senha_e_recusado(app):
    with app.test_request_context(json={"user_name": "alguem"}):
        with patch("routes.user_routes.login_user") as service:
            resposta = login_user_json()

    assert _status(resposta) == 400
    service.assert_not_called()


def test_troca_de_senha_exige_a_senha_atual(app):
    dono = User(id=TOKEN_USER_ID, user_name="dono", profile="USER")
    with app.test_request_context(json={"new_password": "nova"}):
        with (
            patch("routes.user_routes.change_password") as service,
            patch("routes.user_routes.get_jwt_identity", return_value=TOKEN_USER_ID),
            patch("routes.user_routes.db") as db,
        ):
            db.session.get.return_value = dono
            resposta = change_password_json(TOKEN_USER_ID)

    assert _status(resposta) == 400
    assert "current_password" in _body(resposta)["errors"]
    service.assert_not_called()


# ── Edição de usuário ────────────────────────────────────────────────────────


def test_edicao_parcial_nao_inventa_campos_nulos(app):
    # `edit_user` percorre o que recebe e faz setattr. Um schema com
    # `load_default=None` mandaria `email=None` junto e apagaria o e-mail de
    # quem só queria trocar o nome — e num usuário comum o `profile=None` ainda
    # levaria a "Field 'profile' is not editable".
    with app.test_request_context(json={"name": "Nome Novo"}):
        with (
            patch("routes.user_routes.edit_user") as service,
            patch("routes.user_routes.get_jwt_identity", return_value=TOKEN_USER_ID),
            patch("routes.user_routes.db"),
        ):
            service.return_value = (MagicMock(), 200)
            edit_user_json(TOKEN_USER_ID)

    assert service.call_args[0][1] == {"name": "Nome Novo"}


# ── Posições da carteira ─────────────────────────────────────────────────────


POSICAO = {"ticker": "PETR4", "quantity": 100, "average_price": 30.5}


def _adicionar(app, payload, view=add_position_json, alvo="add_position"):
    with app.test_request_context(json=payload):
        with (
            patch(f"routes.portfolio_routes.{alvo}") as service,
            patch(
                "routes.portfolio_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            service.return_value = (MagicMock(), 201)
            resposta = view()
        return resposta, service


def test_o_dono_da_posicao_vem_do_token_e_nao_do_corpo(app):
    _, service = _adicionar(app, {**POSICAO, "user_id": OUTRO_USUARIO})
    assert service.call_args[0][0]["user_id"] == TOKEN_USER_ID


def test_quantidade_em_texto_e_recusada_com_400(app):
    # Antes o texto atravessava o serviço e só quebrava na comparação
    # `quantity <= 0`, o que devolvia 500 para um erro do cliente.
    resposta, service = _adicionar(app, {**POSICAO, "quantity": "cem"})

    assert _status(resposta) == 400
    assert "quantity" in _body(resposta)["errors"]
    service.assert_not_called()


def test_quantidade_negativa_e_recusada_antes_do_banco(app):
    resposta, service = _adicionar(app, {**POSICAO, "quantity": -5})

    assert _status(resposta) == 400
    service.assert_not_called()


def test_preco_medio_zero_e_recusado(app):
    resposta, _ = _adicionar(app, {**POSICAO, "average_price": 0})
    assert _status(resposta) == 400


def test_ticker_longo_demais_e_recusado(app):
    resposta, _ = _adicionar(app, {**POSICAO, "ticker": "TICKERGIGANTE11"})

    assert _status(resposta) == 400
    assert "ticker" in _body(resposta)["errors"]


POSICAO_FII = {"fii_ticker": "HGLG11", "quantity": 10, "average_price": 147.6}


def test_a_posicao_de_fii_usa_o_proprio_nome_de_campo(app):
    # A carteira de fundos manda `fii_ticker`; reusar o schema de ação, que
    # exige `ticker`, recusaria todo pedido de FII.
    _, service = _adicionar(
        app, POSICAO_FII, view=add_fii_position_json, alvo="add_fii_position"
    )

    enviado = service.call_args[0][0]
    assert enviado["fii_ticker"] == "HGLG11"
    assert enviado["user_id"] == TOKEN_USER_ID


def test_a_posicao_de_fii_sem_ticker_e_recusada(app):
    resposta, service = _adicionar(
        app,
        {"quantity": 10, "average_price": 147.6},
        view=add_fii_position_json,
        alvo="add_fii_position",
    )

    assert _status(resposta) == 400
    assert "fii_ticker" in _body(resposta)["errors"]
    service.assert_not_called()


def test_a_posicao_de_fii_passa_pelas_mesmas_regras_numericas(app):
    resposta, service = _adicionar(
        app,
        {**POSICAO_FII, "quantity": 0},
        view=add_fii_position_json,
        alvo="add_fii_position",
    )

    assert _status(resposta) == 400
    service.assert_not_called()


def test_quantidade_em_texto_numerico_e_convertida(app):
    # Formulário HTML manda número como string; recusar isso seria rigor sem
    # ganho. O que não pode é texto que não é número.
    _, service = _adicionar(app, {**POSICAO, "quantity": "100"})
    assert service.call_args[0][0]["quantity"] == 100.0


def test_edicao_de_posicao_so_leva_o_que_foi_enviado(app):
    # `edit_position` faz `position_data.get("quantity", position.quantity)`;
    # uma chave com None venceria o valor atual e quebraria a comparação.
    with app.test_request_context(json={"quantity": 50}):
        with (
            patch("routes.portfolio_routes.edit_position") as service,
            patch(
                "routes.portfolio_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            service.return_value = (MagicMock(), 200)
            edit_position_json(1)

    assert service.call_args[0][1] == {"quantity": 50.0}


def test_edicao_de_posicao_leva_o_dono_do_token(app):
    # Sem o dono, o serviço editava a posição de qualquer conta pelo id.
    with app.test_request_context(json={"quantity": 50}):
        with (
            patch("routes.portfolio_routes.edit_position") as service,
            patch(
                "routes.portfolio_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            service.return_value = (MagicMock(), 200)
            edit_position_json(1)

    assert service.call_args[0][2] == TOKEN_USER_ID


# ── Favoritas de FII ─────────────────────────────────────────────────────────


def test_a_favorita_de_fii_nasce_no_dono_do_token(app):
    # Mesmo buraco que a favorita de ação tinha: `user_id` vinha do corpo.
    with app.test_request_context(
        json={"fii_ticker": "KNRI11", "user_id": OUTRO_USUARIO, "id": 1}
    ):
        with (
            patch("routes.favorite_fii_routes.new_favorite_fii") as service,
            patch(
                "routes.favorite_fii_routes.get_jwt_identity",
                return_value=TOKEN_USER_ID,
            ),
        ):
            service.return_value = (MagicMock(), 201)
            new_favorite_fii_json()

    enviado = service.call_args[0][0]
    assert enviado["user_id"] == TOKEN_USER_ID
    assert "id" not in enviado


def test_a_edicao_de_favorita_de_fii_nao_troca_dono(app):
    with app.test_request_context(
        json={"target_price": 90.0, "user_id": OUTRO_USUARIO, "fii_ticker": "X"}
    ):
        with (
            patch("routes.favorite_fii_routes.edit_favorite_fii") as service,
            patch(
                "routes.favorite_fii_routes.get_jwt_identity",
                return_value=TOKEN_USER_ID,
            ),
        ):
            service.return_value = (MagicMock(), 200)
            edit_favorite_fii_json(1)

    assert service.call_args[0][1] == {"target_price": 90.0}


# ── Filtros das listagens ────────────────────────────────────────────────────


@pytest.mark.parametrize("filtros", ["nao-e-json", '{"id": "dy"}', "[1, 2]"])
def test_filtro_malformado_e_400_e_nao_500(app, filtros):
    with app.test_request_context(query_string={"filters": filtros}):
        with (
            patch("routes.stock_routes.list_stocks") as service,
            patch("routes.stock_routes.get_jwt_identity", return_value=TOKEN_USER_ID),
        ):
            resposta = list_stocks_json()

    assert _status(resposta) == 400
    service.assert_not_called()


# ── Favoritas ────────────────────────────────────────────────────────────────


def test_a_favorita_nasce_no_dono_do_token(app):
    # Era possível criar favorita na conta de outro: o serviço lia o `user_id`
    # do corpo e nunca o comparava com o de quem pediu.
    with app.test_request_context(
        json={"stock_ticker": "PETR4", "user_id": OUTRO_USUARIO}
    ):
        with (
            patch("routes.favorite_routes.new_favorite") as service,
            patch(
                "routes.favorite_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            service.return_value = (MagicMock(), 201)
            new_favorite_json()

    assert service.call_args[0][0]["user_id"] == TOKEN_USER_ID


def test_a_edicao_de_favorita_nao_troca_dono_nem_ticker(app):
    with app.test_request_context(
        json={
            "ceiling_price": 40.0,
            "user_id": OUTRO_USUARIO,
            "stock_ticker": "VALE3",
        }
    ):
        with (
            patch("routes.favorite_routes.edit_favorite") as service,
            patch(
                "routes.favorite_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            service.return_value = (MagicMock(), 200)
            edit_favorite_json(1)

    enviado = service.call_args[0][1]
    assert enviado == {"ceiling_price": 40.0}


def test_favorita_sem_ticker_e_recusada(app):
    with app.test_request_context(json={"ceiling_price": 40.0}):
        with (
            patch("routes.favorite_routes.new_favorite") as service,
            patch(
                "routes.favorite_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            resposta = new_favorite_json()

    assert _status(resposta) == 400
    service.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"ceiling_price": "quarenta"},
        {"target_price": "trinta"},
    ],
)
def test_preco_de_favorita_em_texto_e_recusado(app, payload):
    with app.test_request_context(json=payload):
        with (
            patch("routes.favorite_routes.edit_favorite") as service,
            patch(
                "routes.favorite_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            resposta = edit_favorite_json(1)

    assert _status(resposta) == 400
    service.assert_not_called()


def test_limpar_o_preco_teto_e_permitido(app):
    # Apagar o teto é desligar o alerta, não mandar valor inválido.
    with app.test_request_context(json={"ceiling_price": None}):
        with (
            patch("routes.favorite_routes.edit_favorite") as service,
            patch(
                "routes.favorite_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            service.return_value = (MagicMock(), 200)
            edit_favorite_json(1)

    assert service.call_args[0][1] == {"ceiling_price": None}


def test_preco_teto_em_texto_numerico_e_convertido(app):
    # A tabela de favoritas edita em célula de texto e manda string.
    with app.test_request_context(json={"ceiling_price": "40,5".replace(",", ".")}):
        with (
            patch("routes.favorite_routes.edit_favorite") as service,
            patch(
                "routes.favorite_routes.get_jwt_identity", return_value=TOKEN_USER_ID
            ),
        ):
            service.return_value = (MagicMock(), 200)
            edit_favorite_json(1)

    assert service.call_args[0][1] == {"ceiling_price": 40.5}


# ── Compatibilidade com o que o frontend manda de verdade ────────────────────
#
# Validação na borda só é melhoria enquanto o cliente continua passando. O
# schema de FII já teria recusado a carteira inteira aqui: o modal manda
# `fii_ticker` e o schema de ação exige `ticker`.


@pytest.mark.parametrize(
    "origem, schema_path, payload",
    [
        (
            "Register.js",
            "schemas.user_schema.NewUserSchema",
            {
                "email": "pessoa@exemplo.com",
                "name": "Pessoa",
                "user_name": "pessoa",
                "password": "senha123",
            },
        ),
        (
            "auth.service.js login",
            "schemas.user_schema.LoginSchema",
            {"user_name": "pessoa", "password": "senha123"},
        ),
        (
            "Perfil.js",
            "schemas.user_schema.ChangePasswordSchema",
            {"current_password": "antiga", "new_password": "nova"},
        ),
        (
            "AddPositionModal.js",
            "schemas.portfolio_schema.AddPositionSchema",
            {"ticker": "PETR4", "quantity": 100, "average_price": 30.5},
        ),
        (
            "AddFiiPositionModal.js",
            "schemas.portfolio_schema.AddFiiPositionSchema",
            {"fii_ticker": "HGLG11", "quantity": 10, "average_price": 147.6},
        ),
        (
            "Portfolio.js edição de célula",
            "schemas.portfolio_schema.EditPositionSchema",
            {"average_price": "35.2"},
        ),
        (
            "Favoritas.js edição de célula",
            "schemas.favorite_schema.EditFavoriteSchema",
            {"ceiling_price": "40.5", "target_price": "38"},
        ),
    ],
)
def test_o_payload_real_do_frontend_passa_no_schema(origem, schema_path, payload):
    import importlib

    module_name, class_name = schema_path.rsplit(".", 1)
    schema = getattr(importlib.import_module(module_name), class_name)()

    carregado = schema.load(payload)

    assert carregado, f"{origem} deixou de ser aceito pelo schema"
