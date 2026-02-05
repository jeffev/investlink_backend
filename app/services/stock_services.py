import logging
import json
import requests
from flask import jsonify
from models.stock import Stock
from models.favorite import Favorite
from config import db


def list_stocks(user_id):
    try:
        all_stocks = Stock.query.all()
        favorites = {
            fav.stock_ticker for fav in Favorite.query.filter_by(user_id=user_id).all()
        }

        stocks_json = [
            {**stock.to_json(), "favorita": stock.ticker in favorites}
            for stock in all_stocks
        ]

        return jsonify(stocks_json)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def view_stock(ticker):
    try:
        stock = Stock.query.get(ticker)
        if not stock:
            return jsonify({"message": "Stock not found"}), 404
        return jsonify(stock.to_json())
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def new_stock(stock_data):
    try:
        if Stock.query.filter_by(ticker=stock_data["ticker"]).first():
            return jsonify({"message": "Stock already exists"}), 400

        new_stock = Stock(**stock_data)
        new_stock.graham_formula = new_stock.get_graham_formula()
        new_stock.discount_to_graham = new_stock.get_discount_to_graham()

        db.session.add(new_stock)
        db.session.commit()
        return jsonify({"message": "Stock added successfully"}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def edit_stock(ticker, stock_data):
    try:
        stock = Stock.query.get(ticker)
        if not stock:
            return jsonify({"message": "Stock not found"}), 404

        for key, value in stock_data.items():
            setattr(stock, key, value)

        stock.graham_formula = stock.get_graham_formula()
        stock.discount_to_graham = stock.get_discount_to_graham()

        db.session.commit()
        return jsonify({"message": "Stock edited successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def delete_stock(ticker):
    try:
        stock = Stock.query.get(ticker)
        if not stock:
            return jsonify({"message": "Stock not found"}), 404

        db.session.delete(stock)
        db.session.commit()
        return jsonify({"message": "Stock deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500


def get_all_stocks_from_statusinvest():
    try:
        url = "https://statusinvest.com.br/category/advancedsearchresultpaginated"
        search_params = {
            "Sector": "",
            "SubSector": "",
            "Segment": "",
            "my_range": "-20;100",
            "forecast": {
                "upsidedownside": {"Item1": None, "Item2": None},
                "estimatesnumber": {"Item1": None, "Item2": None},
                "revisedup": True,
                "reviseddown": True,
                "consensus": [],
            },
            "dy": {"Item1": None, "Item2": None},
            "p_l": {"Item1": None, "Item2": None},
            "peg_ratio": {"Item1": None, "Item2": None},
            "p_vp": {"Item1": None, "Item2": None},
            "p_ativo": {"Item1": None, "Item2": None},
            "margembruta": {"Item1": None, "Item2": None},
            "margemebit": {"Item1": None, "Item2": None},
            "margemliquida": {"Item1": None, "Item2": None},
            "p_ebit": {"Item1": None, "Item2": None},
            "ev_ebit": {"Item1": None, "Item2": None},
            "dividaliquidaebit": {"Item1": None, "Item2": None},
            "dividaliquidapatrimonioliquido": {"Item1": None, "Item2": None},
            "p_sr": {"Item1": None, "Item2": None},
            "p_capitalgiro": {"Item1": None, "Item2": None},
            "p_ativocirculante": {"Item1": None, "Item2": None},
            "roe": {"Item1": None, "Item2": None},
            "roic": {"Item1": None, "Item2": None},
            "roa": {"Item1": None, "Item2": None},
            "liquidezcorrente": {"Item1": None, "Item2": None},
            "pl_ativo": {"Item1": None, "Item2": None},
            "passivo_ativo": {"Item1": None, "Item2": None},
            "giroativos": {"Item1": None, "Item2": None},
            "receitas_cagr5": {"Item1": None, "Item2": None},
            "lucros_cagr5": {"Item1": None, "Item2": None},
            "liquidezmediadiaria": {"Item1": None, "Item2": None},
            "vpa": {"Item1": None, "Item2": None},
            "lpa": {"Item1": None, "Item2": None},
            "valormercado": {"Item1": None, "Item2": None},
        }
        params = {
            "search": json.dumps(search_params),
            "orderColumn": "",
            "isAsc": "",
            "page": 0,
            "take": 1000,
            "CategoryType": 1,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }

        response = requests.get(url, params=params, headers=headers)

        if response.status_code != 200:
            logging.error(f"HTTP error occurred: {response.status_code}")
            return None

        return response.json()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None


def calculate_ey(stock_data):
    earnings = stock_data.get("lpa", 0)
    price = stock_data.get("price", 0)
    ey = earnings / price if price != 0 else 0
    return ey


def update_all_stocks():
    try:
        stocks_data = get_all_stocks_from_statusinvest()
        if not stocks_data or "list" not in stocks_data:
            return (
                jsonify({"error": "Error fetching stock data from StatusInvest."}),
                500,
            )

        cached_stocks = stocks_data["list"]
        tickers = {stock["ticker"] for stock in cached_stocks}

        existing_stocks = Stock.query.filter(Stock.ticker.in_(tickers)).all()
        existing_tickers = {stock.ticker for stock in existing_stocks}

        numeric_fields = [
            "price",
            "p_l",
            "dy",
            "p_vp",
            "p_ebit",
            "p_ativo",
            "ev_ebit",
            "margembruta",
            "margemebit",
            "margemliquida",
            "p_sr",
            "p_capitalgiro",
            "p_ativocirculante",
            "giroativos",
            "roe",
            "roa",
            "roic",
            "dividaliquidapatrimonioliquido",
            "dividaliquidaebit",
            "pl_ativo",
            "passivo_ativo",
            "liquidezcorrente",
            "peg_ratio",
            "receitas_cagr5",
            "vpa",
            "lpa",
            "valormercado",
        ]

        for stock_data in cached_stocks:
            stock_data["ey"] = calculate_ey(stock_data)
            for field in numeric_fields:
                stock_data.setdefault(field, 0.0)

        ey_ranks = {
            stock["ticker"]: rank + 1
            for rank, stock in enumerate(
                sorted(cached_stocks, key=lambda x: x["ey"], reverse=True)
            )
        }

        roic_ranks = {
            stock["ticker"]: rank + 1
            for rank, stock in enumerate(
                sorted(cached_stocks, key=lambda x: x["roic"], reverse=True)
            )
        }

        new_stocks = []
        for stock_data in cached_stocks:
            stock_data["roic_rank"] = roic_ranks[stock_data["ticker"]]
            stock_data["ey_rank"] = ey_ranks[stock_data["ticker"]]
            stock_data["magic_formula_rank"] = (
                stock_data["roic_rank"] + stock_data["ey_rank"]
            )

            if stock_data["ticker"] in existing_tickers:
                stock = next(
                    stock
                    for stock in existing_stocks
                    if stock.ticker == stock_data["ticker"]
                )
                for key, value in stock_data.items():
                    setattr(stock, key, value)
                stock.graham_formula = stock.get_graham_formula()
                stock.discount_to_graham = stock.get_discount_to_graham()
                stock.roic_rank = stock_data["roic_rank"]
                stock.ey_rank = stock_data["ey_rank"]
                stock.magic_formula_rank = stock_data["magic_formula_rank"]
            else:
                new_stocks.append(Stock(**{**stock_data}))

        db.session.add_all(new_stocks)
        db.session.commit()

        return jsonify({"message": "Stocks updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return jsonify({"message": "An error occurred, please try again later"}), 500
