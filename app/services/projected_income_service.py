import logging

from flask import jsonify

from models.portfolio import Portfolio
from models.portfolio_fii import PortfolioFii


def _stock_monthly_income(quantity, stock):
    if stock and stock.price and stock.dy and stock.dy > 0:
        return round((quantity * stock.price * stock.dy / 100) / 12, 2)
    return 0.0


def _fii_monthly_income(quantity, fii):
    if fii is None:
        return 0.0
    if fii.lastdividend and fii.lastdividend > 0:
        return round(quantity * fii.lastdividend, 2)
    if fii.dy and fii.dy > 0 and fii.price and fii.price > 0:
        return round((quantity * fii.price * fii.dy / 100) / 12, 2)
    return 0.0


def get_projected_income(user_id):
    try:
        stock_positions = Portfolio.query.filter_by(user_id=user_id).all()
        fii_positions = PortfolioFii.query.filter_by(user_id=user_id).all()

        stocks_monthly = sum(
            _stock_monthly_income(p.quantity, p.stock) for p in stock_positions
        )
        fiis_monthly = sum(
            _fii_monthly_income(p.quantity, p.fii) for p in fii_positions
        )

        monthly = round(stocks_monthly + fiis_monthly, 2)
        return (
            jsonify(
                {
                    "monthly": monthly,
                    "yearly": round(monthly * 12, 2),
                    "stocks_monthly": round(stocks_monthly, 2),
                    "fiis_monthly": round(fiis_monthly, 2),
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
