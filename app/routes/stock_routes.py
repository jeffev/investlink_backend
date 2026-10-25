from flask import request
from flask_jwt_extended import get_jwt_identity

from schemas import load_filters_arg

from services.stock_services import (
    list_stocks,
    view_stock,
    bulk_view_stocks,
    new_stock,
    edit_stock,
    delete_stock,
    update_all_stocks,
)
from services.stock_history_service import get_stock_price_history
from services.reconciliation_service import reconcile_fundamentals
from services.historical_context_service import (
    DEFAULT_YEARS,
    get_historical_context,
)


def list_stocks_json():
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    sort_by = request.args.get("sort_by", None)
    sort_dir = request.args.get("sort_dir", "asc")
    filters, error = load_filters_arg()
    if error:
        return error
    search = request.args.get("search", None)
    profile = request.args.get("profile", None)
    return list_stocks(
        user_id, page, per_page, sort_by, sort_dir, filters, search, profile
    )


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


def bulk_view_stocks_json():
    tickers_raw = request.args.get("tickers", "")
    tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
    return bulk_view_stocks(tickers)


def reconcile_fundamentals_json():
    year = request.args.get("year", None, type=int)
    return reconcile_fundamentals(year)


def get_historical_context_json(ticker):
    years = request.args.get("years", DEFAULT_YEARS, type=int)
    return get_historical_context(ticker.upper(), years)
