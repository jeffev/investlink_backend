from services.prediction_service import get_all_predictions, get_prediction_by_ticker


def list_predictions_json():
    return get_all_predictions()


def view_prediction_json(ticker):
    return get_prediction_by_ticker(ticker.upper())
