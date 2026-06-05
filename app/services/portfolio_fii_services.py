import logging

from flask import jsonify

from config import db
from models.fii import Fii
from models.portfolio_fii import PortfolioFii
from models.user import User


def _calculate_fii_pnl(position_json, fii):
    quantity = position_json["quantity"]
    total_invested = position_json["total_invested"]
    current_price = fii.price if fii else None
    current_value = round(quantity * current_price, 2) if current_price else None
    pnl = (
        round(current_value - total_invested, 2) if current_value is not None else None
    )
    pnl_percent = (
        round((pnl / total_invested) * 100, 2)
        if pnl is not None and total_invested
        else None
    )
    monthly_income = _calculate_monthly_income(quantity, fii)
    return {
        **position_json,
        "companyname": fii.companyname if fii else None,
        "current_price": current_price,
        "current_value": current_value,
        "pnl": pnl,
        "pnl_percent": pnl_percent,
        "monthly_income": monthly_income,
    }


def _calculate_monthly_income(quantity, fii):
    if fii is None:
        return 0.0
    if fii.lastdividend and fii.lastdividend > 0:
        return round(quantity * fii.lastdividend, 2)
    if fii.dy and fii.dy > 0 and fii.price and fii.price > 0:
        return round((quantity * fii.price * fii.dy / 100) / 12, 2)
    return 0.0


def list_portfolio_fii(user_id):
    try:
        positions = PortfolioFii.query.filter_by(user_id=user_id).all()
        result = [_calculate_fii_pnl(p.to_json(), p.fii) for p in positions]
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def get_portfolio_fii_summary(user_id):
    try:
        positions = PortfolioFii.query.filter_by(user_id=user_id).all()
        total_invested = 0.0
        current_value = 0.0
        for position in positions:
            total_invested += position.total_invested
            if position.fii and position.fii.price:
                current_value += position.quantity * position.fii.price
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
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def add_fii_position(position_data):
    try:
        user_id = position_data.get("user_id")
        fii_ticker = position_data.get("fii_ticker")
        quantity = position_data.get("quantity")
        average_price = position_data.get("average_price")

        if not user_id or not fii_ticker or quantity is None or average_price is None:
            return jsonify({"message": "Missing required fields"}), 400

        if not db.session.get(User, user_id):
            return jsonify({"message": "User not found"}), 404

        if not db.session.get(Fii, fii_ticker):
            return jsonify({"message": "FII not found"}), 404

        if quantity <= 0 or average_price <= 0:
            return (
                jsonify({"message": "Quantity and average_price must be positive"}),
                400,
            )

        position = PortfolioFii(
            user_id=user_id,
            fii_ticker=fii_ticker,
            quantity=quantity,
            average_price=average_price,
        )
        db.session.add(position)
        db.session.commit()
        return jsonify({"message": "FII position added successfully"}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def edit_fii_position(position_id, position_data):
    try:
        position = db.session.get(PortfolioFii, position_id)
        if position is None:
            return jsonify({"message": "Position not found"}), 404

        quantity = position_data.get("quantity", position.quantity)
        average_price = position_data.get("average_price", position.average_price)

        if quantity <= 0 or average_price <= 0:
            return (
                jsonify({"message": "Quantity and average_price must be positive"}),
                400,
            )

        position.quantity = quantity
        position.average_price = average_price
        position.total_invested = round(quantity * average_price, 2)

        db.session.commit()
        return jsonify({"message": "FII position updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def delete_fii_position(position_id):
    try:
        position = db.session.get(PortfolioFii, position_id)
        if position is None:
            return jsonify({"message": "Position not found"}), 404

        db.session.delete(position)
        db.session.commit()
        return jsonify({"message": "FII position deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
