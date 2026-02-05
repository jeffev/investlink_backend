from flask import jsonify
from config import db
from models.favorite import Favorite
from models.stock import Stock
from models.user import User


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
def list_favorites(user_id):
    user_favorites = Favorite.query.filter_by(user_id=user_id).all()
    favorites_json = [favorite.to_json() for favorite in user_favorites]
    return jsonify(favorites_json)


@handle_db_operations
def view_favorite(favorite_id):
    favorite = Favorite.query.get(favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404
    return jsonify(favorite.to_json())


@handle_db_operations
def new_favorite(favorite_data):
    user_id = favorite_data.get("user_id")
    stock_ticker = favorite_data.get("stock_ticker")

    if not User.query.get(user_id):
        return jsonify({"message": "User not found"}), 404

    if not Stock.query.get(stock_ticker):
        return jsonify({"message": "Stock not found"}), 404

    existing_favorite = Favorite.query.filter_by(
        user_id=user_id, stock_ticker=stock_ticker
    ).first()
    if existing_favorite:
        return jsonify({"message": "This stock is already favorited by this user"}), 400

    new_favorite = Favorite(**favorite_data)
    db.session.add(new_favorite)
    return jsonify({"message": "Favorite added successfully"}), 201


@handle_db_operations
def edit_favorite(favorite_id, favorite_data):
    user_id = favorite_data.get("user_id")
    stock_ticker = favorite_data.get("stock_ticker")

    if user_id is not None and not User.query.get(user_id):
        return jsonify({"message": "User not found"}), 404

    if stock_ticker is not None and not Stock.query.get(stock_ticker):
        return jsonify({"message": "Stock not found"}), 404

    favorite = Favorite.query.get(favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404

    for key, value in favorite_data.items():
        setattr(favorite, key, value)

    return jsonify({"message": "Favorite edited successfully"}), 200


@handle_db_operations
def delete_favorite(favorite_id):
    favorite = Favorite.query.get(favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404

    db.session.delete(favorite)
    return jsonify({"message": "Favorite deleted successfully"}), 200


@handle_db_operations
def add_favorite(user_id, ticker):
    existing_favorite = Favorite.query.filter_by(
        user_id=user_id, stock_ticker=ticker
    ).first()
    if existing_favorite:
        return jsonify({"message": "This stock is already favorited by this user"}), 400

    new_favorite = Favorite(user_id=user_id, stock_ticker=ticker)
    db.session.add(new_favorite)
    return jsonify({"message": "Favorite added successfully"}), 201


@handle_db_operations
def remove_favorite(user_id, ticker):
    favorite = Favorite.query.filter_by(user_id=user_id, stock_ticker=ticker).first()
    if not favorite:
        return jsonify({"message": "Favorite not found"}), 404

    db.session.delete(favorite)
    return jsonify({"message": "Favorite deleted successfully"}), 200
