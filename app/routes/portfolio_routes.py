from flask import request
from flask_jwt_extended import get_jwt_identity

from services.portfolio_services import (
    add_position,
    delete_position,
    edit_position,
    get_portfolio_summary,
    list_portfolio,
)
from services.portfolio_fii_services import (
    add_fii_position,
    delete_fii_position,
    edit_fii_position,
    get_portfolio_fii_summary,
    list_portfolio_fii,
)
from services.projected_income_service import get_projected_income
from schemas import load_payload
from schemas.portfolio_schema import (
    AddFiiPositionSchema,
    AddPositionSchema,
    EditPositionSchema,
)


def list_portfolio_json():
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 200, type=int)
    return list_portfolio(user_id, page, per_page)


def portfolio_summary_json():
    user_id = get_jwt_identity()
    return get_portfolio_summary(user_id)


def add_position_json():
    position_data, error = load_payload(AddPositionSchema())
    if error:
        return error
    # O dono vem do token, nunca do corpo.
    position_data["user_id"] = get_jwt_identity()
    return add_position(position_data)


def edit_position_json(position_id):
    position_data, error = load_payload(EditPositionSchema())
    if error:
        return error
    return edit_position(position_id, position_data)


def delete_position_json(position_id):
    return delete_position(position_id)


def list_portfolio_fii_json():
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 200, type=int)
    return list_portfolio_fii(user_id, page, per_page)


def portfolio_fii_summary_json():
    user_id = get_jwt_identity()
    return get_portfolio_fii_summary(user_id)


def add_fii_position_json():
    # Schema próprio: a carteira de fundos usa `fii_ticker`, não `ticker`.
    position_data, error = load_payload(AddFiiPositionSchema())
    if error:
        return error
    position_data["user_id"] = get_jwt_identity()
    return add_fii_position(position_data)


def edit_fii_position_json(position_id):
    position_data, error = load_payload(EditPositionSchema())
    if error:
        return error
    return edit_fii_position(position_id, position_data)


def delete_fii_position_json(position_id):
    return delete_fii_position(position_id)


def projected_income_json():
    user_id = get_jwt_identity()
    return get_projected_income(user_id)
