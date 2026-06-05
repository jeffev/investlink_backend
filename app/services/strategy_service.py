import json
import logging

from flask import jsonify

from config import db
from models.strategy import Strategy

VALID_ASSET_TYPES = ("STOCK", "FII")


def list_strategies(user_id, asset_type="STOCK"):
    try:
        strategies = (
            Strategy.query.filter_by(user_id=user_id, asset_type=asset_type)
            .order_by(Strategy.created_at.asc())
            .all()
        )
        return jsonify([s.to_json() for s in strategies]), 200
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def create_strategy(user_id, data):
    try:
        name = data.get("name", "").strip()
        asset_type = data.get("asset_type", "")
        filters_raw = data.get("filters", "")
        sorting_raw = data.get("sorting", None)

        if not name:
            return jsonify({"message": "Name is required"}), 400

        if len(name) > 100:
            return jsonify({"message": "Name must be 100 characters or less"}), 400

        if asset_type not in VALID_ASSET_TYPES:
            return jsonify({"message": "asset_type must be STOCK or FII"}), 400

        try:
            parsed = (
                json.loads(filters_raw) if isinstance(filters_raw, str) else filters_raw
            )
            if not parsed:
                return jsonify({"message": "filters must not be empty"}), 400
            filters_str = json.dumps(parsed)
        except (json.JSONDecodeError, TypeError):
            return jsonify({"message": "filters must be valid JSON"}), 400

        sorting_str = None
        if sorting_raw is not None:
            try:
                parsed_sort = (
                    json.loads(sorting_raw)
                    if isinstance(sorting_raw, str)
                    else sorting_raw
                )
                sorting_str = json.dumps(parsed_sort)
            except (json.JSONDecodeError, TypeError):
                return jsonify({"message": "sorting must be valid JSON"}), 400

        strategy = Strategy(
            user_id=user_id,
            name=name,
            asset_type=asset_type,
            filters=filters_str,
            sorting=sorting_str,
        )
        db.session.add(strategy)
        db.session.commit()
        return (
            jsonify({"message": "Strategy created successfully", "id": strategy.id}),
            201,
        )
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def delete_strategy(user_id, strategy_id):
    try:
        strategy = db.session.get(Strategy, strategy_id)
        if strategy is None:
            return jsonify({"message": "Strategy not found"}), 404
        if strategy.user_id != user_id:
            return jsonify({"message": "Unauthorized"}), 403
        db.session.delete(strategy)
        db.session.commit()
        return jsonify({"message": "Strategy deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
