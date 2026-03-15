from marshmallow import Schema, ValidationError, fields, validates, EXCLUDE


class AddPositionSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    user_id = fields.Integer(required=True)
    ticker = fields.String(required=True)
    quantity = fields.Float(required=True)
    average_price = fields.Float(required=True)

    @validates("ticker")
    def validate_ticker(self, value):
        if len(value) > 10:
            raise ValidationError("Ticker must be 10 characters or less.")

    @validates("quantity")
    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError("Must be positive.")

    @validates("average_price")
    def validate_average_price(self, value):
        if value <= 0:
            raise ValidationError("Must be positive.")


class EditPositionSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    quantity = fields.Float(load_default=None)
    average_price = fields.Float(load_default=None)

    @validates("quantity")
    def validate_quantity(self, value):
        if value is not None and value <= 0:
            raise ValidationError("Must be positive.")

    @validates("average_price")
    def validate_average_price(self, value):
        if value is not None and value <= 0:
            raise ValidationError("Must be positive.")
