import functools
import logging

from flask import jsonify
from models.user_layout import UserLayout
from config import db


def handle_db_operations(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error in {func.__name__}: {e}")
            return (
                jsonify({"message": "An error occurred, please try again later"}),
                500,
            )

    return wrapper


@handle_db_operations
def get_user_layout(user_id, layout=None):
    if layout:
        user_layout = UserLayout.query.filter_by(user_id=user_id, layout=layout).first()
        if user_layout is None:
            return jsonify(None), 400
        return jsonify(user_layout.estado), 200
    else:
        user_layouts = UserLayout.query.filter_by(user_id=user_id).all()
        return jsonify([layout.to_json() for layout in user_layouts]), 200


@handle_db_operations
def save_user_layout(user_id, layout, estado):
    user_layout = UserLayout.query.filter_by(user_id=user_id, layout=layout).first()

    if user_layout:
        user_layout.estado = estado
        message = "User layout updated successfully"
    else:
        user_layout = UserLayout(user_id=user_id, layout=layout, estado=estado)
        db.session.add(user_layout)
        message = "User layout added successfully"

    return jsonify({"message": message}), 201


@handle_db_operations
def delete_user_layout(layout_id):
    user_layout = db.session.get(UserLayout, layout_id)
    if user_layout is None:
        return jsonify({"message": "Layout not found"}), 404

    db.session.delete(user_layout)
    return jsonify({"message": "Layout deleted successfully"}), 200
