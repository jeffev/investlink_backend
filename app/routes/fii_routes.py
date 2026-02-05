from flask import request
from flask_jwt_extended import get_jwt_identity

from services.fii_services import (
    list_fiis,
    view_fii,
    new_fii,
    edit_fii,
    delete_fii,
    update_all_fiis,
)


def list_fiis_json():
    user_id = get_jwt_identity()
    return list_fiis(user_id)


def view_fii_json(ticker):
    return view_fii(ticker.upper())


def new_fii_json():
    fii_data = request.get_json()
    return new_fii(fii_data)


def edit_fii_json(ticker):
    fii_data = request.get_json()
    return edit_fii(ticker.upper(), fii_data)


def delete_fii_json(ticker):
    return delete_fii(ticker.upper())


def update_fiis():
    return update_all_fiis()
