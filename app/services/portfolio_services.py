import functools
import logging

from flask import jsonify

from config import db
from models.portfolio import Portfolio
from models.stock import Stock
from models.user import User


def handle_db_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logging.error(f"An error occurred in {func.__name__}: {e}")
            return (
                jsonify({"message": "An error occurred, please try again later"}),
                500,
            )

    return wrapper


def _calculate_pnl(position_json, current_price):
    quantity = position_json["quantity"]
    total_invested = position_json["total_invested"]
    current_value = round(quantity * current_price, 2) if current_price else None
    pnl = (
        round(current_value - total_invested, 2) if current_value is not None else None
    )
    pnl_percent = (
        round((pnl / total_invested) * 100, 2)
        if pnl is not None and total_invested
        else None
    )
    return {
        **position_json,
        "current_price": current_price,
        "current_value": current_value,
        "pnl": pnl,
        "pnl_percent": pnl_percent,
    }


@handle_db_errors
def list_portfolio(user_id):
    positions = Portfolio.query.filter_by(user_id=user_id).all()
    result = []
    for position in positions:
        stock = position.stock
        current_price = stock.price if stock else None
        enriched = _calculate_pnl(position.to_json(), current_price)
        enriched["companyname"] = stock.companyname if stock else None
        enriched["sectorname"] = stock.sectorname if stock else None
        result.append(enriched)
    return jsonify(result), 200


@handle_db_errors
def get_portfolio_summary(user_id):
    positions = Portfolio.query.filter_by(user_id=user_id).all()
    total_invested = 0.0
    current_value = 0.0
    for position in positions:
        total_invested += position.total_invested
        if position.stock and position.stock.price:
            current_value += position.quantity * position.stock.price
    total_pnl = round(current_value - total_invested, 2)
    total_pnl_percent = (
        round((total_pnl / total_invested) * 100, 2) if total_invested else 0.0
    )
    return (
        jsonify(
            {
                "total_invested": round(total_invested, 2),
                "current_value": round(current_value, 2),
                "total_pnl": total_pnl,
                "total_pnl_percent": total_pnl_percent,
            }
        ),
        200,
    )


@handle_db_errors
def add_position(position_data):
    user_id = position_data.get("user_id")
    ticker = position_data.get("ticker")
    quantity = position_data.get("quantity")
    average_price = position_data.get("average_price")

    if not user_id or not ticker or quantity is None or average_price is None:
        return jsonify({"message": "Missing required fields"}), 400

    if not db.session.get(User, user_id):
        return jsonify({"message": "User not found"}), 404

    if not db.session.get(Stock, ticker):
        return jsonify({"message": "Stock not found"}), 404

    if quantity <= 0 or average_price <= 0:
        return jsonify({"message": "Quantity and average_price must be positive"}), 400

    position = Portfolio(
        user_id=user_id,
        ticker=ticker,
        quantity=quantity,
        average_price=average_price,
    )
    db.session.add(position)
    db.session.commit()
    return jsonify({"message": "Position added successfully"}), 201


@handle_db_errors
def edit_position(position_id, position_data):
    position = db.session.get(Portfolio, position_id)
    if position is None:
        return jsonify({"message": "Position not found"}), 404

    quantity = position_data.get("quantity", position.quantity)
    average_price = position_data.get("average_price", position.average_price)

    if quantity <= 0 or average_price <= 0:
        return jsonify({"message": "Quantity and average_price must be positive"}), 400

    position.quantity = quantity
    position.average_price = average_price
    position.total_invested = round(quantity * average_price, 2)

    db.session.commit()
    return jsonify({"message": "Position updated successfully"}), 200


@handle_db_errors
def delete_position(position_id):
    position = db.session.get(Portfolio, position_id)
    if position is None:
        return jsonify({"message": "Position not found"}), 404

    db.session.delete(position)
    db.session.commit()
    return jsonify({"message": "Position deleted successfully"}), 200
