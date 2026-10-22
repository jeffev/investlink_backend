import functools
import logging

from flask import jsonify
from sqlalchemy import or_
from config import db
from models.favorite import Favorite
from models.stock import Stock
from models.user import User
from services.prediction_service import get_latest_predictions_map, attach_ml_fields


def handle_db_errors(func):
    """Handles rollback and logging on exception.

    Write operations must commit explicitly.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logging.error(f"An error occurred in {func.__name__}: {e}")
            return (
                jsonify({"message": "An error occurred, please try again later"}),
                500,
            )

    return wrapper


@handle_db_errors
def list_favorites(user_id, page=1, per_page=50):
    query = Favorite.query.filter_by(user_id=user_id)
    total = query.count()
    user_favorites = query.offset((page - 1) * per_page).limit(per_page).all()
    pred_map = get_latest_predictions_map()
    favorites_json = []
    for favorite in user_favorites:
        fav_dict = favorite.to_json()
        if fav_dict["stock"] is not None:
            ticker = fav_dict["stock"].get("ticker")
            fav_dict["stock"] = attach_ml_fields(
                fav_dict["stock"], pred_map.get(ticker)
            )
        favorites_json.append(fav_dict)
    return (
        jsonify(
            {
                "data": favorites_json,
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": (total + per_page - 1) // per_page,
                },
            }
        ),
        200,
    )


@handle_db_errors
def get_price_alerts(user_id):
    alerts = (
        Favorite.query.join(Favorite.stock)
        .filter(
            Favorite.user_id == user_id,
            or_(
                (Favorite.ceiling_price.isnot(None))
                & (Stock.price <= Favorite.ceiling_price),
                (Favorite.target_price.isnot(None))
                & (Stock.price <= Favorite.target_price),
            ),
        )
        .all()
    )
    result = []
    for fav in alerts:
        stock = fav.stock
        discount = (
            round(((fav.ceiling_price - stock.price) / fav.ceiling_price) * 100, 2)
            if fav.ceiling_price
            else None
        )
        result.append(
            {
                "ticker": stock.ticker,
                "companyname": stock.companyname,
                "current_price": stock.price,
                "ceiling_price": fav.ceiling_price,
                "target_price": fav.target_price,
                "discount_to_ceiling_percent": discount,
            }
        )
    return jsonify(result), 200


@handle_db_errors
def view_favorite(favorite_id, current_user_id):
    favorite = db.session.get(Favorite, favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404
    if favorite.user_id != current_user_id:
        return jsonify({"message": "Unauthorized"}), 403
    return jsonify(favorite.to_json()), 200


@handle_db_errors
def new_favorite(favorite_data):
    user_id = favorite_data.get("user_id")
    stock_ticker = favorite_data.get("stock_ticker")

    if not db.session.get(User, user_id):
        return jsonify({"message": "User not found"}), 404

    if not db.session.get(Stock, stock_ticker):
        return jsonify({"message": "Stock not found"}), 404

    existing_favorite = Favorite.query.filter_by(
        user_id=user_id, stock_ticker=stock_ticker
    ).first()
    if existing_favorite:
        return jsonify({"message": "This stock is already favorited by this user"}), 400

    # Campo a campo, e não `Favorite(**favorite_data)`: com o desempacotamento
    # qualquer chave do corpo virava coluna, e o `user_id` recebido nunca foi
    # comparado com o de quem pediu — dava para criar favorita na conta alheia.
    db.session.add(
        Favorite(
            user_id=user_id,
            stock_ticker=stock_ticker,
            ceiling_price=favorite_data.get("ceiling_price"),
            target_price=favorite_data.get("target_price"),
        )
    )
    db.session.commit()
    return jsonify({"message": "Favorite added successfully"}), 201


@handle_db_errors
def edit_favorite(favorite_id, favorite_data, current_user_id):
    user_id = favorite_data.get("user_id")
    stock_ticker = favorite_data.get("stock_ticker")

    if user_id is not None and not db.session.get(User, user_id):
        return jsonify({"message": "User not found"}), 404

    if stock_ticker is not None and not db.session.get(Stock, stock_ticker):
        return jsonify({"message": "Stock not found"}), 404

    favorite = db.session.get(Favorite, favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404

    if favorite.user_id != current_user_id:
        return jsonify({"message": "Unauthorized"}), 403

    for key, value in favorite_data.items():
        setattr(favorite, key, value)

    db.session.commit()
    return jsonify({"message": "Favorite edited successfully"}), 200


@handle_db_errors
def delete_favorite(favorite_id, current_user_id):
    favorite = db.session.get(Favorite, favorite_id)
    if favorite is None:
        return jsonify({"message": "Favorite not found"}), 404

    if favorite.user_id != current_user_id:
        return jsonify({"message": "Unauthorized"}), 403

    db.session.delete(favorite)
    db.session.commit()
    return jsonify({"message": "Favorite deleted successfully"}), 200


@handle_db_errors
def add_favorite(user_id, ticker):
    existing_favorite = Favorite.query.filter_by(
        user_id=user_id, stock_ticker=ticker
    ).first()
    if existing_favorite:
        return jsonify({"message": "This stock is already favorited by this user"}), 400

    db.session.add(Favorite(user_id=user_id, stock_ticker=ticker))
    db.session.commit()
    return jsonify({"message": "Favorite added successfully"}), 201


@handle_db_errors
def remove_favorite(user_id, ticker):
    favorite = Favorite.query.filter_by(user_id=user_id, stock_ticker=ticker).first()
    if not favorite:
        return jsonify({"message": "Favorite not found"}), 404

    db.session.delete(favorite)
    db.session.commit()
    return jsonify({"message": "Favorite deleted successfully"}), 200
