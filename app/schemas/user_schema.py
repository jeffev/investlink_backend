import re

from marshmallow import Schema, ValidationError, fields, validates, EXCLUDE


class NewUserSchema(Schema):
    """
    Cadastro público — `POST /v1/users` não exige token, só limite de taxa.

    `profile` **não** está aqui de propósito. O serviço faz `User(**user_data)`,
    então enquanto o campo era aceito bastava mandar `"profile": "ADMIN"` no
    corpo do cadastro para sair com perfil de administrador, que é o mesmo
    perfil que libera `/v1/stocks/update` e a reconciliação. Com o campo fora
    do schema e `unknown = EXCLUDE`, o que o cliente mandar é descartado antes
    de chegar ao model, e o perfil passa a vir do default da coluna.
    """

    class Meta:
        unknown = EXCLUDE

    user_name = fields.String(required=True)
    name = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String(required=True)

    @validates("user_name")
    def validate_user_name(self, value):
        if not re.match(r"^[a-zA-Z0-9_.-]{3,}$", value):
            raise ValidationError("Invalid username format.")


class EditUserSchema(Schema):
    """
    Edição de cadastro.

    `profile` continua aceito porque a troca de perfil é operação de
    administrador — quem pode fazê-la é decidido em `edit_user`, comparando o
    perfil de quem pede (`EDITABLE_FIELDS_ADMIN`). Aqui o campo só é
    transportado.

    Edição parcial: sem `load_default`, só as chaves enviadas entram no
    dicionário. `edit_user` percorre o que recebe e faz `setattr`, então um
    default de nulo apagaria o e-mail de quem só queria trocar o nome — e, num
    usuário comum, o `profile` nulo ainda derrubaria o pedido inteiro em
    "Field 'profile' is not editable".
    """

    class Meta:
        unknown = EXCLUDE

    user_name = fields.String()
    name = fields.String()
    email = fields.Email()
    profile = fields.String()


class LoginSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    user_name = fields.String(required=True)
    password = fields.String(required=True)


class ChangePasswordSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    current_password = fields.String(required=True)
    new_password = fields.String(required=True)
