from marshmallow import Schema, fields, EXCLUDE


class NewFavoriteSchema(Schema):
    """
    Favoritar uma ação.

    Sem `user_id`: o dono sai do token, como já era feito no portfólio. Aceitar
    o campo pelo corpo deixava um usuário autenticado criar favorita **na conta
    de outro** — o serviço faz `Favorite(**favorite_data)` e nunca comparou o
    `user_id` recebido com o de quem pediu.
    """

    class Meta:
        unknown = EXCLUDE

    stock_ticker = fields.String(required=True)
    ceiling_price = fields.Float(load_default=None)
    target_price = fields.Float(load_default=None)


class EditFavoriteSchema(Schema):
    """
    Edição parcial: só os campos enviados entram no dicionário.

    Nada de `load_default=None` — `edit_favorite` percorre o que recebe e faz
    `setattr`, então um default preencheria de nulo todo campo que o cliente
    não mandou e apagaria o preço-teto de quem só queria mudar o alvo.

    `stock_ticker` e `user_id` ficaram de fora: trocar o ticker é outra
    favorita, e trocar o dono é transferir a favorita para a conta de outro.
    """

    class Meta:
        unknown = EXCLUDE

    # `allow_none` porque limpar o campo é ação legítima: apagar o preço-teto
    # é desligar o alerta, e não mandar um valor inválido.
    ceiling_price = fields.Float(allow_none=True)
    target_price = fields.Float(allow_none=True)
