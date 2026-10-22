"""
Validação da entrada na borda HTTP.

Os schemas existiam desde o sprint E e **nunca foram chamados**: não havia um
`.load()` em lugar nenhum do backend. Na prática cada serviço repetia à mão um
pedaço da checagem, cada um com sua própria mensagem, e o que ninguém checava
entrava direto no model.

Duas coisas que só aparecem quando a validação some:

    `request.get_json()` levanta quando o corpo não é JSON, e a rota que fazia
    `dados["user_id"] = ...` logo em seguida devolvia 500 para um pedido
    malformado — erro do cliente contado como falha do servidor.

    `User(**user_data)` e `Favorite(**favorite_data)` gravam o que vier. Todo
    campo que o schema não declara é um campo que o cliente escolhe.
"""

from flask import jsonify, request
from marshmallow import ValidationError

BODY_ERROR_KEY = "_body"


def load_payload(schema):
    """
    Lê e valida o corpo da requisição.

    Devolve `(dados, None)` quando passa e `(None, resposta_400)` quando não —
    e nunca levanta. A rota decide o que fazer com o erro; o serviço só é
    chamado com dado já no formato certo.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (
            jsonify(
                {
                    "errors": {
                        BODY_ERROR_KEY: ["Corpo da requisição não é um JSON válido."]
                    }
                }
            ),
            400,
        )

    try:
        return schema.load(payload), None
    except ValidationError as error:
        return None, (jsonify({"errors": error.messages}), 400)
