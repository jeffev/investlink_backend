from flask import request
from flask_jwt_extended import get_jwt_identity

from services.user_layout_service import get_user_layout, save_user_layout


def get_user_layout_json(layout):
    user_id = get_jwt_identity()
    return get_user_layout(user_id, layout)


def save_user_layout_json():
    user_id = get_jwt_identity()
    layout_data = request.get_json()

    layout = layout_data.get("layout")
    estado = layout_data.get("estado")

    return save_user_layout(user_id, layout, estado)
