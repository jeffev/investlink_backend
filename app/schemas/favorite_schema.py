from marshmallow import Schema, fields, EXCLUDE


class NewFavoriteSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    user_id = fields.Integer(required=True)
    stock_ticker = fields.String(required=True)
    ceiling_price = fields.Float(load_default=None)
    target_price = fields.Float(load_default=None)


class EditFavoriteSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    ceiling_price = fields.Float(load_default=None)
    target_price = fields.Float(load_default=None)
    user_id = fields.Integer(load_default=None)
    stock_ticker = fields.String(load_default=None)
