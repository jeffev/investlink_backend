from flask import request
from flask_jwt_extended import get_jwt_identity

from services.stock_services import (
    list_stocks,
    view_stock,
    new_stock,
    edit_stock,
    delete_stock,
    update_all_stocks,
)


def list_stocks_json():
    user_id = get_jwt_identity()
    return list_stocks(user_id)


def view_stock_json(ticker):
    return view_stock(ticker.upper())


def new_stock_json():
    stock_data = request.get_json()
    return new_stock(stock_data)


def edit_stock_json(ticker):
    stock_data = request.get_json()
    return edit_stock(ticker.upper(), stock_data)


def delete_stock_json(ticker):
    return delete_stock(ticker.upper())


def update_stocks():
    return update_all_stocks()
