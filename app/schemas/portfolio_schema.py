from marshmallow import Schema, ValidationError, fields, validates, EXCLUDE

MAX_TICKER_LENGTH = 10


class _BasePositionSchema(Schema):
    """
    O que ação e FII têm em comum numa posição nova.

    O ticker fica nas subclasses porque o nome do campo **não** é o mesmo: a
    carteira de ações usa `ticker` e a de fundos usa `fii_ticker`, tanto no
    model quanto no corpo que o frontend manda. Um schema único recusaria
    todo pedido de FII.
    """

    class Meta:
        unknown = EXCLUDE

    quantity = fields.Float(required=True)
    average_price = fields.Float(required=True)

    @validates("quantity")
    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError("Must be positive.")

    @validates("average_price")
    def validate_average_price(self, value):
        if value <= 0:
            raise ValidationError("Must be positive.")


def _validate_ticker(value):
    if len(value) > MAX_TICKER_LENGTH:
        raise ValidationError(f"Ticker must be {MAX_TICKER_LENGTH} characters or less.")


class AddPositionSchema(_BasePositionSchema):
    """
    Nova posição de ação.

    Sem `user_id`: a rota o injeta a partir do token depois de validar. Se o
    campo viesse pelo corpo, quem quisesse escreveria na carteira alheia.

    A tipagem aqui é o que separa 400 de 500: `quantity` chegava como texto e
    só explodia na comparação `quantity <= 0`, lá dentro do serviço.
    """

    ticker = fields.String(required=True, validate=_validate_ticker)


class AddFiiPositionSchema(_BasePositionSchema):
    """Nova posição de FII — mesmo formato, outro nome de campo."""

    fii_ticker = fields.String(required=True, validate=_validate_ticker)


class EditPositionSchema(Schema):
    """
    Edição parcial de posição, de ação ou de FII — os dois serviços usam os
    mesmos dois campos.

    Nada de `load_default=None` — `edit_position` faz
    `position_data.get("quantity", position.quantity)`, e um default de nulo
    venceria o valor atual: a chave existiria, o `get` devolveria `None` e a
    comparação seguinte quebraria com 500.
    """

    class Meta:
        unknown = EXCLUDE

    quantity = fields.Float()
    average_price = fields.Float()

    @validates("quantity")
    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError("Must be positive.")

    @validates("average_price")
    def validate_average_price(self, value):
        if value <= 0:
            raise ValidationError("Must be positive.")
