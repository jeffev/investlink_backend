from flask import jsonify
from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt_identity

from models.user import User
from config import db, limiter

from routes.stock_routes import (
    list_stocks_json,
    view_stock_json,
    bulk_view_stocks_json,
    new_stock_json,
    edit_stock_json,
    delete_stock_json,
    update_all_stocks,
    get_stock_history_json,
    get_historical_context_json,
    reconcile_fundamentals_json,
)
from routes.user_routes import (
    list_users_json,
    view_user_json,
    new_user_json,
    edit_user_json,
    delete_user_json,
    login_user_json,
    login_demo_json,
    change_password_json,
)
from routes.favorite_routes import (
    list_favorites_json,
    view_favorite_json,
    new_favorite_json,
    edit_favorite_json,
    delete_favorite_json,
    add_favorite_stock,
    remove_favorite_stock,
    list_price_alerts_json,
)
from routes.user_layout_routes import (
    get_user_layout_json,
    save_user_layout_json,
    delete_user_layout_json,
)
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
from routes.auth_routes import refresh_token_json
from routes.health_routes import health_json
from routes.benchmark_routes import get_benchmarks_json
from routes.transaction_routes import (
    list_transactions_json,
    create_transaction_json,
    delete_transaction_json,
)
from routes.strategy_routes import (
    list_strategies_json,
    create_strategy_json,
    delete_strategy_json,
)
from routes.prediction_routes import list_predictions_json, view_prediction_json
from routes.backtest_routes import run_backtest_json
from routes.news_routes import get_news_json
from routes.opportunity_routes import (
    list_opportunities_json,
    list_profiles_json,
    get_stock_score_json,
    backtest_score_json,
)
from routes.portfolio_routes import (
    add_position_json,
    delete_position_json,
    edit_position_json,
    list_portfolio_json,
    portfolio_summary_json,
    list_portfolio_fii_json,
    portfolio_fii_summary_json,
    add_fii_position_json,
    edit_fii_position_json,
    delete_fii_position_json,
    projected_income_json,
)


def protected_route(view_func, required_profile=None):
    @wraps(view_func)
    @jwt_required()
    def decorated_view(*args, **kwargs):
        current_user_id = get_jwt_identity()

        if current_user_id is None:
            return jsonify({"message": "Invalid token"}), 401

        # Recupera o usuário do banco de dados
        user = db.session.get(User, current_user_id)
        if user is None:
            return jsonify({"message": "User not found"}), 404

        # Verifica o perfil do usuário, se necessário
        if required_profile and user.profile != required_profile:
            return jsonify({"message": "Unauthorized"}), 403

        # Chama a função da rota original
        return view_func(*args, **kwargs)

    return decorated_view


def setup_routes(app):
    # Health route — fora do /v1 porque é infraestrutura, não API pública
    app.add_url_rule("/health", methods=["GET"], view_func=health_json)

    # Auth routes
    app.add_url_rule("/v1/auth/refresh", methods=["POST"], view_func=refresh_token_json)

    # Benchmark routes
    app.add_url_rule(
        "/v1/benchmarks",
        methods=["GET"],
        view_func=protected_route(get_benchmarks_json),
    )

    # Transaction routes
    app.add_url_rule(
        "/v1/transactions",
        methods=["GET"],
        view_func=protected_route(list_transactions_json),
    )
    app.add_url_rule(
        "/v1/transactions",
        methods=["POST"],
        view_func=protected_route(create_transaction_json),
    )
    app.add_url_rule(
        "/v1/transaction/<int:transaction_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_transaction_json),
    )

    # Strategy routes
    app.add_url_rule(
        "/v1/strategies",
        methods=["GET"],
        view_func=protected_route(list_strategies_json),
    )
    app.add_url_rule(
        "/v1/strategies",
        methods=["POST"],
        view_func=protected_route(create_strategy_json),
    )
    app.add_url_rule(
        "/v1/strategy/<int:strategy_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_strategy_json),
    )

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
        "/v1/stocks",
        methods=["POST"],
        view_func=protected_route(new_stock_json, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>",
        methods=["PUT"],
        view_func=protected_route(edit_stock_json, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>",
        methods=["DELETE"],
        view_func=protected_route(delete_stock_json, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/stocks/update-stocks",
        methods=["PUT"],
        view_func=protected_route(update_all_stocks, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>/history",
        methods=["GET"],
        view_func=protected_route(get_stock_history_json),
    )
    app.add_url_rule(
        "/v1/stocks/bulk",
        methods=["GET"],
        view_func=protected_route(bulk_view_stocks_json),
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>/historical-context",
        methods=["GET"],
        view_func=protected_route(get_historical_context_json),
    )
    app.add_url_rule(
        "/v1/stocks/reconciliation",
        methods=["GET"],
        view_func=protected_route(
            reconcile_fundamentals_json, required_profile="ADMIN"
        ),
    )

    # User routes
    app.add_url_rule(
        "/v1/users",
        methods=["GET"],
        view_func=protected_route(list_users_json, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/user/<int:user_id>",
        methods=["GET"],
        view_func=protected_route(view_user_json),
    )
    app.add_url_rule(
        "/v1/users",
        methods=["POST"],
        view_func=limiter.limit("5 per minute")(new_user_json),
    )
    app.add_url_rule(
        "/v1/user/<int:user_id>",
        methods=["PUT"],
        view_func=protected_route(edit_user_json),
    )
    app.add_url_rule(
        "/v1/user/<int:user_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_user_json, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/user/login",
        methods=["POST"],
        view_func=limiter.limit("5 per minute")(login_user_json),
    )
    app.add_url_rule(
        "/v1/user/demo-login",
        methods=["POST"],
        view_func=limiter.limit("20 per minute")(login_demo_json),
    )
    app.add_url_rule(
        "/v1/user/<int:user_id>/password",
        methods=["PUT"],
        view_func=protected_route(change_password_json),
    )

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
        "/v1/favorites/alerts",
        methods=["GET"],
        view_func=protected_route(list_price_alerts_json),
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
    app.add_url_rule(
        "/v1/user_layout/<string:layout>",
        methods=["DELETE"],
        view_func=protected_route(delete_user_layout_json),
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
        "/v1/fiis",
        methods=["POST"],
        view_func=protected_route(new_fii_json, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/fii/<string:ticker>",
        methods=["PUT"],
        view_func=protected_route(edit_fii_json, required_profile="ADMIN"),
    )
    app.add_url_rule(
        "/v1/fii/<string:ticker>",
        methods=["DELETE"],
        view_func=protected_route(delete_fii_json, required_profile="ADMIN"),
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

    # Prediction routes
    app.add_url_rule(
        "/v1/stocks/predictions",
        methods=["GET"],
        view_func=protected_route(list_predictions_json),
    )
    app.add_url_rule(
        "/v1/stocks/<string:ticker>/prediction",
        methods=["GET"],
        view_func=protected_route(view_prediction_json),
    )

    # Portfolio routes (ações)
    app.add_url_rule(
        "/v1/portfolio",
        methods=["GET"],
        view_func=protected_route(list_portfolio_json),
    )
    app.add_url_rule(
        "/v1/portfolio/summary",
        methods=["GET"],
        view_func=protected_route(portfolio_summary_json),
    )
    app.add_url_rule(
        "/v1/portfolio",
        methods=["POST"],
        view_func=protected_route(add_position_json),
    )
    app.add_url_rule(
        "/v1/portfolio/<int:position_id>",
        methods=["PUT"],
        view_func=protected_route(edit_position_json),
    )
    app.add_url_rule(
        "/v1/portfolio/<int:position_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_position_json),
    )

    # Portfolio routes (FIIs) — registradas antes de /<int:id> para não colidir
    app.add_url_rule(
        "/v1/portfolio/fii",
        methods=["GET"],
        view_func=protected_route(list_portfolio_fii_json),
    )
    app.add_url_rule(
        "/v1/portfolio/fii/summary",
        methods=["GET"],
        view_func=protected_route(portfolio_fii_summary_json),
    )
    app.add_url_rule(
        "/v1/portfolio/fii",
        methods=["POST"],
        view_func=protected_route(add_fii_position_json),
    )
    app.add_url_rule(
        "/v1/portfolio/fii/<int:position_id>",
        methods=["PUT"],
        view_func=protected_route(edit_fii_position_json),
    )
    app.add_url_rule(
        "/v1/portfolio/fii/<int:position_id>",
        methods=["DELETE"],
        view_func=protected_route(delete_fii_position_json),
    )

    # Projected income
    app.add_url_rule(
        "/v1/portfolio/projected-income",
        methods=["GET"],
        view_func=protected_route(projected_income_json),
    )

    # Backtest routes
    app.add_url_rule(
        "/v1/strategy/<int:strategy_id>/backtest",
        methods=["GET"],
        view_func=protected_route(run_backtest_json),
    )

    # News routes
    app.add_url_rule(
        "/v1/news",
        methods=["GET"],
        view_func=protected_route(get_news_json),
    )

    # Opportunity routes
    app.add_url_rule(
        "/v1/opportunities",
        methods=["GET"],
        view_func=protected_route(list_opportunities_json),
    )
    app.add_url_rule(
        "/v1/opportunities/profiles",
        methods=["GET"],
        view_func=protected_route(list_profiles_json),
    )
    app.add_url_rule(
        "/v1/opportunities/backtest",
        methods=["GET"],
        view_func=protected_route(backtest_score_json),
    )
    app.add_url_rule(
        "/v1/stock/<string:ticker>/score",
        methods=["GET"],
        view_func=protected_route(get_stock_score_json),
    )
