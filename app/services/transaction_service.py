import logging
from datetime import date as date_type

from flask import jsonify

from config import db
from models.transaction import Transaction

VALID_TYPES = ("COMPRA", "VENDA")
VALID_ASSET_TYPES = ("STOCK", "FII")


def list_transactions(user_id):
    try:
        transactions = (
            Transaction.query.filter_by(user_id=user_id)
            .order_by(Transaction.date.desc(), Transaction.created_at.desc())
            .all()
        )
        data = [t.to_json() for t in transactions]

        total_compras = sum(t["total"] for t in data if t["type"] == "COMPRA")
        total_vendas = sum(t["total"] for t in data if t["type"] == "VENDA")
        resultado_realizado = round(total_vendas - total_compras, 2)

        return (
            jsonify(
                {
                    "data": data,
                    "summary": {
                        "total_compras": round(total_compras, 2),
                        "total_vendas": round(total_vendas, 2),
                        "resultado_realizado": resultado_realizado,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def create_transaction(user_id, data):
    try:
        ticker = (data.get("ticker") or "").strip().upper()
        asset_type = data.get("asset_type", "STOCK")
        tx_type = (data.get("type") or "").strip().upper()
        quantity = data.get("quantity")
        price = data.get("price")
        date_raw = data.get("date")

        if not ticker:
            return jsonify({"message": "ticker is required"}), 400
        if tx_type not in VALID_TYPES:
            return jsonify({"message": "type must be COMPRA or VENDA"}), 400
        if asset_type not in VALID_ASSET_TYPES:
            return jsonify({"message": "asset_type must be STOCK or FII"}), 400
        if quantity is None or float(quantity) <= 0:
            return jsonify({"message": "quantity must be positive"}), 400
        if price is None or float(price) <= 0:
            return jsonify({"message": "price must be positive"}), 400
        if not date_raw:
            return jsonify({"message": "date is required"}), 400

        if isinstance(date_raw, str):
            tx_date = date_type.fromisoformat(date_raw)
        else:
            tx_date = date_raw

        transaction = Transaction(
            user_id=user_id,
            ticker=ticker,
            asset_type=asset_type,
            type=tx_type,
            quantity=float(quantity),
            price=float(price),
            date=tx_date,
        )
        db.session.add(transaction)
        db.session.commit()
        return (
            jsonify(
                {"message": "Transaction created successfully", "id": transaction.id}
            ),
            201,
        )
    except (ValueError, TypeError) as e:
        return jsonify({"message": f"Invalid data: {e}"}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def delete_transaction(user_id, transaction_id):
    try:
        transaction = db.session.get(Transaction, transaction_id)
        if transaction is None:
            return jsonify({"message": "Transaction not found"}), 404
        if transaction.user_id != user_id:
            return jsonify({"message": "Unauthorized"}), 403
        db.session.delete(transaction)
        db.session.commit()
        return jsonify({"message": "Transaction deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
