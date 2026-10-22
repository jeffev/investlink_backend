import logging

from flask import jsonify
from sqlalchemy import func

from models.stock_prediction import StockPrediction
from config import db


def get_latest_predictions_map():
    """Retorna {ticker: StockPrediction} com a predição mais recente por ticker."""
    latest_subq = (
        db.session.query(
            StockPrediction.ticker,
            func.max(StockPrediction.run_date).label("max_run_date"),
        )
        .group_by(StockPrediction.ticker)
        .subquery()
    )
    predictions = (
        db.session.query(StockPrediction)
        .join(
            latest_subq,
            db.and_(
                StockPrediction.ticker == latest_subq.c.ticker,
                StockPrediction.run_date == latest_subq.c.max_run_date,
            ),
        )
        .all()
    )
    return {p.ticker: p for p in predictions}


def attach_ml_fields(stock_json, pred):
    """Adiciona campos de ML ao dict da ação. pred pode ser None."""
    stock_json["ml_label"] = pred.label if pred else None
    stock_json["ml_score"] = round(pred.composite_score, 1) if pred else None
    stock_json["ml_prob_barata"] = pred.prob_barata if pred else None
    stock_json["ml_prob_neutra"] = pred.prob_neutra if pred else None
    stock_json["ml_prob_cara"] = pred.prob_cara if pred else None
    return stock_json


DEFAULT_PER_PAGE = 200


def get_all_predictions(page=1, per_page=DEFAULT_PER_PAGE):
    """
    Latest prediction per ticker, one page at a time.

    Paginated to match every other listing, but the page defaults wide enough
    that the dashboard still gets the whole universe in one call.
    """
    try:
        per_page = max(1, min(per_page, 1000))
        page = max(1, page)
        predictions = sorted(
            get_latest_predictions_map().values(), key=lambda p: p.ticker
        )
        total = len(predictions)
        start = (page - 1) * per_page
        window = predictions[start : start + per_page]
        return (
            jsonify(
                {
                    "data": [p.to_json() for p in window],
                    "pagination": {
                        "total": total,
                        "current_page": page,
                        "per_page": per_page,
                        "pages": (total + per_page - 1) // per_page,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def get_prediction_by_ticker(ticker):
    try:
        prediction = (
            db.session.query(StockPrediction)
            .filter(StockPrediction.ticker == ticker)
            .order_by(StockPrediction.run_date.desc())
            .first()
        )

        if prediction is None:
            return jsonify({"message": "Prediction not found"}), 404

        return jsonify(prediction.to_json()), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
