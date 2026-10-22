import os

from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from config import db
from models.user import User
from schemas import load_payload
from schemas.user_schema import (
    ChangePasswordSchema,
    EditUserSchema,
    LoginSchema,
    NewUserSchema,
)
from services.user_services import (
    list_users,
    view_user,
    new_user,
    edit_user,
    delete_user,
    login_user,
    login_demo_user,
    change_password,
)


def _signup_allowed():
    # A demo pública roda com o cadastro fechado: todo visitante entra pela
    # mesma conta demo, e ninguém lota o banco gratuito com contas novas.
    return os.environ.get("ALLOW_SIGNUP", "true").lower() != "false"


def _is_demo_account(user):
    demo_user_name = os.environ.get("DEMO_USER_NAME")
    return (
        bool(demo_user_name) and user is not None and user.user_name == demo_user_name
    )


def _current_user():
    return db.session.get(User, get_jwt_identity())


def _can_access(user_id):
    current = _current_user()
    return current is not None and (
        current.profile == "ADMIN" or str(current.id) == str(user_id)
    )


def list_users_json():
    return list_users()


def view_user_json(user_id):
    if not _can_access(user_id):
        return jsonify({"message": "Unauthorized"}), 403
    return view_user(user_id)


def new_user_json():
    if not _signup_allowed():
        return jsonify({"message": "Cadastro desativado nesta demonstração."}), 403
    user_data, error = load_payload(NewUserSchema())
    if error:
        return error
    return new_user(user_data)


def edit_user_json(user_id):
    user_data, error = load_payload(EditUserSchema())
    if error:
        return error
    current_user_id = get_jwt_identity()
    current_user = db.session.get(User, current_user_id)
    if _is_demo_account(db.session.get(User, user_id)):
        return jsonify({"message": "A conta demo não pode ser alterada."}), 403
    current_profile = current_user.profile if current_user else "USER"
    return edit_user(user_id, user_data, current_user_id, current_profile)


def delete_user_json(user_id):
    return delete_user(user_id)


def login_user_json():
    login_data, error = load_payload(LoginSchema())
    if error:
        return error
    return login_user(login_data)


def login_demo_json():
    demo_user_name = os.environ.get("DEMO_USER_NAME")
    if not demo_user_name:
        return jsonify({"message": "Demo desativada."}), 404
    return login_demo_user(demo_user_name)


def change_password_json(user_id):
    if not _can_access(user_id):
        return jsonify({"message": "Unauthorized"}), 403
    if _is_demo_account(db.session.get(User, user_id)):
        return jsonify({"message": "A conta demo não pode ser alterada."}), 403
    data, error = load_payload(ChangePasswordSchema())
    if error:
        return error
    return change_password(user_id, data)
