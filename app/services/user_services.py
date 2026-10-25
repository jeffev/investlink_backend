import bcrypt
import logging
import re
from datetime import timedelta
from flask import jsonify
from flask_jwt_extended import create_access_token, create_refresh_token

from models.user import User
from config import db

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

expires = timedelta(hours=3)

# Cadastro público nunca escolhe o próprio perfil.
DEFAULT_PROFILE = "USER"


def list_users():
    try:
        all_users = User.query.all()
        users_json = [user.to_json() for user in all_users]
        return jsonify(users_json), 200
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({"message": "Error listing users"}), 500


def view_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404
        return jsonify(user.to_json()), 200
    except Exception as e:
        logger.error(f"Error viewing user: {e}")
        return jsonify({"message": "Error viewing user"}), 500


def new_user(user_data):
    try:
        if not user_data.get("user_name"):
            return jsonify({"message": "User name is required"}), 400
        if not user_data.get("email"):
            return jsonify({"message": "Email is required"}), 400
        if not validate_email(user_data["email"]):
            return jsonify({"message": "Invalid email format"}), 400
        if not validate_username(user_data["user_name"]):
            return jsonify({"message": "Invalid username format"}), 400

        existing_user = User.query.filter_by(user_name=user_data["user_name"]).first()
        if existing_user:
            return jsonify({"message": "User already exists"}), 400

        existing_email = User.query.filter_by(email=user_data["email"]).first()
        if existing_email:
            return jsonify({"message": "Email already in use"}), 400

        hashed_password = bcrypt.hashpw(
            user_data["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # Campo a campo, e não `User(**user_data)`: com o desempacotamento,
        # todo campo do corpo virava coluna, e como o cadastro é público
        # bastava enviar "profile": "ADMIN" para sair com o perfil que libera
        # as rotas de administração. O schema já descarta o campo; isto
        # garante que ele continue descartado se alguém chamar o serviço
        # direto.
        new_user = User(
            user_name=user_data["user_name"],
            name=user_data["name"],
            email=user_data["email"],
            password=hashed_password,
            profile=DEFAULT_PROFILE,
        )
        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity=new_user.id, expires_delta=expires)
        refresh_token = create_refresh_token(identity=new_user.id)

        response_data = {
            "profile": new_user.profile,
            "name": new_user.name,
            "user_name": new_user.user_name,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

        return jsonify(response_data), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding user: {e}")
        return jsonify({"message": "Error adding user"}), 500


EDITABLE_FIELDS_USER = {"user_name", "name", "email"}
EDITABLE_FIELDS_ADMIN = {"user_name", "name", "email", "profile"}


def edit_user(user_id, user_data, requesting_user_id, requesting_user_profile):
    try:
        user = db.session.get(User, user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404

        if requesting_user_profile != "ADMIN" and requesting_user_id != user_id:
            return jsonify({"message": "Unauthorized"}), 403

        allowed_fields = (
            EDITABLE_FIELDS_ADMIN
            if requesting_user_profile == "ADMIN"
            else EDITABLE_FIELDS_USER
        )
        for key in user_data:
            if key not in allowed_fields:
                return jsonify({"message": f"Field '{key}' is not editable"}), 400

        # O login busca pelo nome de usuário e pega o primeiro: sem esta
        # checagem, renomear a própria conta para "admin" disputava a entrada
        # com a conta de verdade.
        new_user_name = user_data.get("user_name")
        if new_user_name is not None and new_user_name != user.user_name:
            if not validate_username(new_user_name):
                return jsonify({"message": "Invalid username format"}), 400
            if User.query.filter_by(user_name=new_user_name).first():
                return jsonify({"message": "User already exists"}), 400

        for key, value in user_data.items():
            setattr(user, key, value)

        db.session.commit()
        return jsonify({"message": "User edited successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing user: {e}")
        return jsonify({"message": "Error editing user"}), 500


def delete_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404

        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user: {e}")
        return jsonify({"message": "Error deleting user"}), 500


def _session_payload(user):
    return {
        "profile": user.profile,
        "name": user.name,
        "user_name": user.user_name,
        "access_token": create_access_token(identity=user.id, expires_delta=expires),
        "refresh_token": create_refresh_token(identity=user.id),
    }


def login_demo_user(demo_user_name):
    """
    Entrada da demo pública sem senha: o visitante recebe a sessão da conta
    compartilhada. Sem senha não há credencial embutida no frontend para vazar
    nem para alguém trocar e trancar a demo.
    """
    try:
        user = User.query.filter_by(user_name=demo_user_name).first()
        if user is None:
            return jsonify({"message": "Conta demo não encontrada"}), 404
        return jsonify(_session_payload(user)), 200
    except Exception as e:
        logger.error(f"Error logging in demo user: {e}")
        return jsonify({"message": "Error logging in user"}), 500


def login_user(login_data):
    try:
        if "user_name" not in login_data or "password" not in login_data:
            return (
                jsonify(
                    {"message": "Both user name and password are required for login."}
                ),
                400,
            )

        user = User.query.filter_by(user_name=login_data.get("user_name")).first()

        if user and bcrypt.checkpw(
            login_data["password"].encode("utf-8"), user.password.encode("utf-8")
        ):
            return jsonify(_session_payload(user)), 200
        else:
            return jsonify({"message": "Invalid username or password"}), 401
    except Exception as e:
        logger.error(f"Error logging in user: {e}")
        return jsonify({"message": "Error logging in user"}), 500


def change_password(user_id, data):
    try:
        if not data.get("current_password") or not data.get("new_password"):
            return (
                jsonify({"message": "current_password and new_password are required"}),
                400,
            )

        user = db.session.get(User, user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404

        if not bcrypt.checkpw(
            data["current_password"].encode("utf-8"), user.password.encode("utf-8")
        ):
            return jsonify({"message": "Current password is incorrect"}), 400

        user.password = bcrypt.hashpw(
            data["new_password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        db.session.commit()
        return jsonify({"message": "Password changed successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error changing password: {e}")
        return jsonify({"message": "Error changing password"}), 500


def validate_email(email):
    # Expressão regular para validar email
    email_regex = r"^(?!.*\.\.)[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


def validate_username(user_name):
    # Expressão regular para validar nome de usuário (mínimo 3 caracteres, sem espaços)
    username_regex = r"^[a-zA-Z0-9_.-]{3,}$"
    return re.match(username_regex, user_name) is not None
