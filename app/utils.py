from flask import jsonify
from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt_identity

from models.user import User

from routes.stock_routes import (
    list_stocks_json,
    view_stock_json,
    new_stock_json,
    edit_stock_json,
    delete_stock_json,
    update_all_stocks,
)
from routes.user_routes import (
    list_users_json,
    view_user_json,
    new_user_json,
    edit_user_json,
    delete_user_json,
    login_user_json,
)
from routes.favorite_routes import (
    list_favorites_json,
    view_favorite_json,
    new_favorite_json,
    edit_favorite_json,
    delete_favorite_json,
    add_favorite_stock,
    remove_favorite_stock,
)
from routes.user_layout_routes import get_user_layout_json, save_user_layout_json
from routes.fii_routes import (
    list_fiis_json,
    view_fii_json,
    new_fii_json,
    edit_fii_json,
    delete_fii_json,
    update_all_fiis,
)
from routes.favorite_fii_routes import (
    list_favorites_fii_json,
    view_favorite_fii_json,
    new_favorite_fii_json,
    edit_favorite_fii_json,
    delete_favorite_fii_json,
    add_favorite_fii_json,
    remove_favorite_fii_json,
)


def protected_route(view_func, required_profile=None):
    @wraps(view_func)
    @jwt_required()
    def decorated_view(*args, **kwargs):
        current_user_id = get_jwt_identity()

        if current_user_id is None:
            return jsonify({"message": "Invalid token"}), 401

        # Recupera o usuário do banco de dados
        user = User.query.get(current_user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404

        # Verifica o perfil do usuário, se necessário
        if required_profile and user.profile != required_profile:
            return jsonify({"message": "Unauthorized"}), 403

        # Chama a função da rota original
        return view_func(*args, **kwargs)

    return decorated_view


def setup_routes(app):
    # Stock routes
    app.add_url_rule(
        "/v1/stocks", methods=["GET"], view_func=protected_route(list_stocks_json)
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>",
        methods=["GET"],
        view_func=protected_route(view_stock_json),
    )
    app.add_url_rule(
        "/v1/stocks", methods=["POST"], view_func=protected_route(new_stock_json)
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>",
        methods=["PUT"],
        view_func=protected_route(edit_stock_json),
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>",
        methods=["DELETE"],
        view_func=protected_route(delete_stock_json),
    )
    app.add_url_rule(
        "/v1/stocks/update-stocks",
        methods=["PUT"],
        view_func=protected_route(update_all_stocks, required_profile="ADMIN"),
    )

    # User routes
    app.add_url_rule(
        "/v1/users", methods=["GET"], view_func=protected_route(list_users_json)
    )
    app.add_url_rule(
        "/v1/user/<int:user_id>",
        methods=["GET"],
        view_func=protected_route(view_user_json),
    )
    app.add_url_rule("/v1/users", methods=["POST"], view_func=new_user_json)
    app.add_url_rule(
        "/v1/user/<int:user_id>",
        methods=["PUT"],
        view_func=protected_route(edit_user_json),
    )
    app.add_url_rule(
        "/v1/user/<int:user_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_user_json),
    )
    app.add_url_rule("/v1/user/login", methods=["POST"], view_func=login_user_json)

    # Favorite routes
    app.add_url_rule(
        "/v1/favorites", methods=["GET"], view_func=protected_route(list_favorites_json)
    )
    app.add_url_rule(
        "/v1/favorite/<int:favorite_id>",
        methods=["GET"],
        view_func=protected_route(view_favorite_json),
    )
    app.add_url_rule(
        "/v1/favorites", methods=["POST"], view_func=protected_route(new_favorite_json)
    )
    app.add_url_rule(
        "/v1/favorite/<int:favorite_id>",
        methods=["PUT"],
        view_func=protected_route(edit_favorite_json),
    )
    app.add_url_rule(
        "/v1/favorite/<int:favorite_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_favorite_json),
    )
    app.add_url_rule(
        "/v1/favorites/<string:ticker>",
        methods=["POST"],
        view_func=protected_route(add_favorite_stock),
    )
    app.add_url_rule(
        "/v1/favorites/<string:ticker>",
        methods=["DELETE"],
        view_func=protected_route(remove_favorite_stock),
    )

    # User layout routes
    app.add_url_rule(
        "/v1/user_layout/<string:layout>",
        methods=["GET"],
        view_func=protected_route(get_user_layout_json),
    )
    app.add_url_rule(
        "/v1/user_layout",
        methods=["POST"],
        view_func=protected_route(save_user_layout_json),
    )

    # FII routes
    app.add_url_rule(
        "/v1/fiis", methods=["GET"], view_func=protected_route(list_fiis_json)
    )
    app.add_url_rule(
        "/v1/fii/<string:ticker>",
        methods=["GET"],
        view_func=protected_route(view_fii_json),
    )
    app.add_url_rule(
        "/v1/fiis", methods=["POST"], view_func=protected_route(new_fii_json)
    )
    app.add_url_rule(
        "/v1/fii/<string:ticker>",
        methods=["PUT"],
        view_func=protected_route(edit_fii_json),
    )
    app.add_url_rule(
        "/v1/fii/<string:ticker>",
        methods=["DELETE"],
        view_func=protected_route(delete_fii_json),
    )
    app.add_url_rule(
        "/v1/fiis/update-fiis",
        methods=["PUT"],
        view_func=protected_route(update_all_fiis, required_profile="ADMIN"),
    )

    # Favorite FII routes
    app.add_url_rule(
        "/v1/favorites/fii",
        methods=["GET"],
        view_func=protected_route(list_favorites_fii_json),
    )
    app.add_url_rule(
        "/v1/favorite/fii/<int:favorite_id>",
        methods=["GET"],
        view_func=protected_route(view_favorite_fii_json),
    )
    app.add_url_rule(
        "/v1/favorites/fii",
        methods=["POST"],
        view_func=protected_route(new_favorite_fii_json),
    )
    app.add_url_rule(
        "/v1/favorite/fii/<int:favorite_id>",
        methods=["PUT"],
        view_func=protected_route(edit_favorite_fii_json),
    )
    app.add_url_rule(
        "/v1/favorite/fii/<int:favorite_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_favorite_fii_json),
    )
    app.add_url_rule(
        "/v1/favorites/fii/<string:ticker>",
        methods=["POST"],
        view_func=protected_route(add_favorite_fii_json),
    )
    app.add_url_rule(
        "/v1/favorites/fii/<string:ticker>",
        methods=["DELETE"],
        view_func=protected_route(remove_favorite_fii_json),
    )
