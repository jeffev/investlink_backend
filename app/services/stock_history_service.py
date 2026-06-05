import logging
from datetime import date, timedelta

from flask import jsonify

from config import db  # noqa: F401 — mantido para consistência com o padrão do projeto
from models.stock import Stock
from models.stock_price_history import StockPriceHistory


def get_stock_price_history(ticker, days=90):
    try:
        stock = Stock.query.get(ticker)
        if stock is None:
            return jsonify({"message": "Stock not found"}), 404

        query = StockPriceHistory.query.filter_by(ticker=ticker)

        if days > 0:
            cutoff = date.today() - timedelta(days=days)
            query = query.filter(StockPriceHistory.date >= cutoff)

        records = query.order_by(StockPriceHistory.date.asc()).all()

        data = [
            {
                "date": record.date.isoformat(),
                "open": record.open_price,
                "high": record.high,
                "low": record.low,
                "close": record.close_price,
                "volume": record.volume,
            }
            for record in records
        ]

        return jsonify({"ticker": ticker, "data": data}), 200

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
