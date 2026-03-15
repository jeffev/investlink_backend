from flask import request
from flask_jwt_extended import get_jwt_identity

from config import db
from models.user import User
from services.user_services import (
    list_users,
    view_user,
    new_user,
    edit_user,
    delete_user,
    login_user,
    change_password,
)


def list_users_json():
    return list_users()


def view_user_json(user_id):
    return view_user(user_id)


def new_user_json():
    user_data = request.get_json()
    return new_user(user_data)


def edit_user_json(user_id):
    user_data = request.get_json()
    current_user_id = get_jwt_identity()
    current_user = db.session.get(User, current_user_id)
    current_profile = current_user.profile if current_user else "USER"
    return edit_user(user_id, user_data, current_user_id, current_profile)


def delete_user_json(user_id):
    return delete_user(user_id)


def login_user_json():
    login_data = request.get_json()
    return login_user(login_data)


def change_password_json(user_id):
    data = request.get_json()
    return change_password(user_id, data)
