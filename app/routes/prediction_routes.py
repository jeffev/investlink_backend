from flask import request

from services.prediction_service import get_all_predictions, get_prediction_by_ticker


def list_predictions_json():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 200, type=int)
    return get_all_predictions(page, per_page)


def view_prediction_json(ticker):
    return get_prediction_by_ticker(ticker.upper())
