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
    get_price_alerts,
)


def list_favorites_json():
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    return list_favorites(user_id, page=page, per_page=per_page)


def view_favorite_json(favorite_id):
    current_user_id = get_jwt_identity()
    return view_favorite(favorite_id, current_user_id)


def new_favorite_json():
    favorite_data = request.get_json()
    return new_favorite(favorite_data)


def edit_favorite_json(favorite_id):
    current_user_id = get_jwt_identity()
    favorite_data = request.get_json()
    return edit_favorite(favorite_id, favorite_data, current_user_id)


def delete_favorite_json(favorite_id):
    current_user_id = get_jwt_identity()
    return delete_favorite(favorite_id, current_user_id)


def add_favorite_stock(ticker):
    user_id = get_jwt_identity()
    return add_favorite(user_id, ticker)


def remove_favorite_stock(ticker):
    user_id = get_jwt_identity()
    return remove_favorite(user_id, ticker)


def list_price_alerts_json():
    user_id = get_jwt_identity()
    return get_price_alerts(user_id)
