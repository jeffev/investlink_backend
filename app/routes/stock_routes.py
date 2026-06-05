import json
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
from services.stock_history_service import get_stock_price_history


def list_stocks_json():
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    sort_by = request.args.get("sort_by", None)
    sort_dir = request.args.get("sort_dir", "asc")
    filters_raw = request.args.get("filters", None)
    filters = json.loads(filters_raw) if filters_raw else None
    search = request.args.get("search", None)
    return list_stocks(user_id, page, per_page, sort_by, sort_dir, filters, search)


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


def get_stock_history_json(ticker):
    days = request.args.get("days", 90, type=int)
    return get_stock_price_history(ticker.upper(), days)
