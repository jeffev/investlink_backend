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


def get_all_predictions():
    try:
        predictions = get_latest_predictions_map().values()
        return jsonify({"data": [p.to_json() for p in predictions]}), 200
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
