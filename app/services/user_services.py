import bcrypt
import logging
import re
from datetime import timedelta
from flask import jsonify
from flask_jwt_extended import create_access_token

from models.user import User
from config import db

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

expires = timedelta(hours=3)


def list_users():
    try:
        all_users = User.query.all()
        users_json = [user.to_json() for user in all_users]
        return jsonify(users_json)
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({"message": "Error listing users"}), 500


def view_user(user_id):
    try:
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404
        return jsonify(user.to_json())
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

        password = user_data.pop("password")
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        user_data["password"] = hashed_password

        new_user = User(**user_data)
        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity=new_user.id, expires_delta=expires)

        response_data = {
            "profile": new_user.profile,
            "name": new_user.name,
            "user_name": new_user.user_name,
            "access_token": access_token,
        }

        return jsonify(response_data), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding user: {e}")
        return jsonify({"message": "Error adding user"}), 500


def edit_user(user_id, user_data):
    try:
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404

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
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404

        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user: {e}")
        return jsonify({"message": "Error deleting user"}), 500


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
            access_token = create_access_token(identity=user.id, expires_delta=expires)

            response_data = {
                "profile": user.profile,
                "name": user.name,
                "user_name": user.user_name,
                "access_token": access_token,
            }
            return jsonify(response_data), 200
        else:
            return jsonify({"message": "Invalid username or password"}), 401
    except Exception as e:
        logger.error(f"Error logging in user: {e}")
        return jsonify({"message": "Error logging in user"}), 500


def validate_email(email):
    # Expressão regular para validar email
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


def validate_username(user_name):
    # Expressão regular para validar nome de usuário (mínimo 3 caracteres, sem espaços)
    username_regex = r"^[a-zA-Z0-9_.-]{3,}$"
    return re.match(username_regex, user_name) is not None
