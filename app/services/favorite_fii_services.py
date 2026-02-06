from flask import jsonify
from config import db
from models.favorite_fiis import FavoriteFii
from models.user import User
from models.fii import Fii


def handle_db_operations(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            print(f"Error in {func.__name__}: {e}")
            return jsonify({"message": f"Error in {func.__name__}"}), 500

    return wrapper


@handle_db_operations
def list_favorites_fii(user_id):
    user_favorites = FavoriteFii.query.filter_by(user_id=user_id).all()
    favorites_json = [favorite.to_json() for favorite in user_favorites]
    return jsonify(favorites_json)


@handle_db_operations
def view_favorite_fii(favorite_id):
    favorite = FavoriteFii.query.get(favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404
    return jsonify(favorite.to_json())


@handle_db_operations
def new_favorite_fii(favorite_data):
    user_id = favorite_data.get("user_id")
    fii_ticker = favorite_data.get("fii_ticker")

    if not User.query.get(user_id):
        return jsonify({"message": "User not found"}), 404

    if not Fii.query.get(fii_ticker):
        return jsonify({"message": "FII not found"}), 404

    existing_favorite = FavoriteFii.query.filter_by(
        user_id=user_id, fii_ticker=fii_ticker
    ).first()
    if existing_favorite:
        return jsonify({"message": "This FII is already favorited by this user"}), 400

    new_favorite = FavoriteFii(**favorite_data)
    db.session.add(new_favorite)
    return jsonify({"message": "Favorite added successfully"}), 201


@handle_db_operations
def edit_favorite_fii(favorite_id, favorite_data):
    user_id = favorite_data.get("user_id")
    fii_ticker = favorite_data.get("fii_ticker")

    if user_id is not None and not User.query.get(user_id):
        return jsonify({"message": "User not found"}), 404

    if fii_ticker is not None and not Fii.query.get(fii_ticker):
        return jsonify({"message": "FII not found"}), 404

    favorite = FavoriteFii.query.get(favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404

    for key, value in favorite_data.items():
        setattr(favorite, key, value)

    return jsonify({"message": "Favorite edited successfully"}), 200


@handle_db_operations
def delete_favorite_fii(favorite_id):
    favorite = FavoriteFii.query.get(favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404

    db.session.delete(favorite)
    return jsonify({"message": "Favorite deleted successfully"}), 200


@handle_db_operations
def add_favorite_fii(user_id, ticker):
    existing_favorite = FavoriteFii.query.filter_by(
        user_id=user_id, fii_ticker=ticker
    ).first()
    if existing_favorite:
        return jsonify({"message": "This FII is already favorited by this user"}), 400

    new_favorite = FavoriteFii(user_id=user_id, fii_ticker=ticker)
    db.session.add(new_favorite)
    return jsonify({"message": "Favorite added successfully"}), 201


@handle_db_operations
def remove_favorite_fii(user_id, ticker):
    favorite = FavoriteFii.query.filter_by(user_id=user_id, fii_ticker=ticker).first()
    if not favorite:
        return jsonify({"message": "Favorite not found"}), 404

    db.session.delete(favorite)
    return jsonify({"message": "Favorite deleted successfully"}), 200
