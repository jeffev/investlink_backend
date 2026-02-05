from flask import request

from services.user_services import (
    list_users,
    view_user,
    new_user,
    edit_user,
    delete_user,
    login_user,
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
    return edit_user(user_id, user_data)


def delete_user_json(user_id):
    return delete_user(user_id)


def login_user_json():
    login_data = request.get_json()
    return login_user(login_data)
