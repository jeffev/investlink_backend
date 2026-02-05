from flask import request
from flask_jwt_extended import get_jwt_identity

from services.favorite_services import (
    list_favorites,
    view_favorite,
    new_favorite,
    edit_favorite,
    delete_favorite,
    add_favorite,
    remove_favorite,
)


def list_favorites_json():
    user_id = get_jwt_identity()
    return list_favorites(user_id)


def view_favorite_json(favorite_id):
    return view_favorite(favorite_id)


def new_favorite_json():
    favorite_data = request.get_json()
    return new_favorite(favorite_data)


def edit_favorite_json(favorite_id):
    favorite_data = request.get_json()
    return edit_favorite(favorite_id, favorite_data)


def delete_favorite_json(favorite_id):
    return delete_favorite(favorite_id)


def add_favorite_stock(ticker):
    user_id = get_jwt_identity()
    return add_favorite(user_id, ticker)


def remove_favorite_stock(ticker):
    user_id = get_jwt_identity()
    return remove_favorite(user_id, ticker)
