import re

from marshmallow import Schema, ValidationError, fields, validates, EXCLUDE


class NewUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    user_name = fields.String(required=True)
    name = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String(required=True)
    profile = fields.String(load_default="USER")

    @validates("user_name")
    def validate_user_name(self, value):
        if not re.match(r"^[a-zA-Z0-9_.-]{3,}$", value):
            raise ValidationError("Invalid username format.")


class EditUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(load_default=None)
    email = fields.Email(load_default=None)
    profile = fields.String(load_default=None)
