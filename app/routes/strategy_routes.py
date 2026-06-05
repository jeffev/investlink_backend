from flask import request
from flask_jwt_extended import get_jwt_identity

from services.strategy_service import create_strategy, delete_strategy, list_strategies


def list_strategies_json():
    user_id = get_jwt_identity()
    asset_type = request.args.get("asset_type", "STOCK")
    return list_strategies(user_id, asset_type)


def create_strategy_json():
    user_id = get_jwt_identity()
    data = request.get_json()
    return create_strategy(user_id, data)


def delete_strategy_json(strategy_id):
    user_id = get_jwt_identity()
    return delete_strategy(user_id, strategy_id)
