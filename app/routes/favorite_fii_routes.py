from flask import request
from flask_jwt_extended import get_jwt_identity
from services.favorite_fii_services import (
    list_favorites_fii,
    view_favorite_fii,
    new_favorite_fii,
    edit_favorite_fii,
    delete_favorite_fii,
    add_favorite_fii,
    remove_favorite_fii,
)


def list_favorites_fii_json():
    user_id = get_jwt_identity()
    return list_favorites_fii(user_id)


def view_favorite_fii_json(favorite_id):
    return view_favorite_fii(favorite_id)


def new_favorite_fii_json():
    favorite_data = request.get_json()
    return new_favorite_fii(favorite_data)


def edit_favorite_fii_json(favorite_id):
    favorite_data = request.get_json()
    return edit_favorite_fii(favorite_id, favorite_data)


def delete_favorite_fii_json(favorite_id):
    return delete_favorite_fii(favorite_id)


def add_favorite_fii_json(ticker):
    user_id = get_jwt_identity()
    return add_favorite_fii(user_id, ticker)


def remove_favorite_fii_json(ticker):
    user_id = get_jwt_identity()
    return remove_favorite_fii(user_id, ticker)
