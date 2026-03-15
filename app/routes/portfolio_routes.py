from flask import request
from flask_jwt_extended import get_jwt_identity

from services.portfolio_services import (
    add_position,
    delete_position,
    edit_position,
    get_portfolio_summary,
    list_portfolio,
)


def list_portfolio_json():
    user_id = get_jwt_identity()
    return list_portfolio(user_id)


def portfolio_summary_json():
    user_id = get_jwt_identity()
    return get_portfolio_summary(user_id)


def add_position_json():
    user_id = get_jwt_identity()
    position_data = request.get_json()
    position_data["user_id"] = user_id
    return add_position(position_data)


def edit_position_json(position_id):
    position_data = request.get_json()
    return edit_position(position_id, position_data)


def delete_position_json(position_id):
    return delete_position(position_id)
