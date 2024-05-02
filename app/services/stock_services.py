import requests
from flask import jsonify

from models.stock import Stock
from config import db

def list_stocks():
    all_stocks = Stock.query.all()
    stocks_json = [stock.to_json() for stock in all_stocks]
    return jsonify(stocks_json)

def view_stock(ticker):
    stock = Stock.query.get(ticker)
    if stock is None:
        return jsonify({'message': 'Stock not found'}), 404
    return jsonify(stock.to_json())

def new_stock(stock_data):
    existing_stock = Stock.query.filter_by(ticker=stock_data['ticker']).first()
    if existing_stock:
        return jsonify({'message': 'Stock already exists'}), 400

    new_stock = Stock(**stock_data)
    db.session.add(new_stock)
    db.session.commit()
    return jsonify({'message': 'Stock added successfully'}), 201

def edit_stock(ticker, stock_data):
    stock = Stock.query.get(ticker)
    if stock is None:
        return jsonify({'message': 'Stock not found'}), 404
    
    for key, value in stock_data.items():
        setattr(stock, key, value)
    db.session.commit()
    return jsonify({'message': 'Stock edited successfully'}), 200

def delete_stock(ticker):
    stock = Stock.query.get(ticker)
    if stock is None:
        return jsonify({'message': 'Stock not found'}), 404
    
    db.session.delete(stock)
    db.session.commit()
    return jsonify({'message': 'Stock deleted successfully'}), 200

def get_all_stocks_from_statusinvest():
    url = "https://statusinvest.com.br/category/advancedsearchresultpaginated"
    params = {
        "search": "{\"Sector\":\"\",\"SubSector\":\"\",\"Segment\":\"\",\"my_range\":\"-20;100\",\"forecast\":{\"upsidedownside\":{\"Item1\":null,\"Item2\":null},\"estimatesnumber\":{\"Item1\":null,\"Item2\":null},\"revisedup\":true,\"reviseddown\":true,\"consensus\":[]},\"dy\":{\"Item1\":null,\"Item2\":null},\"p_l\":{\"Item1\":null,\"Item2\":null},\"peg_ratio\":{\"Item1\":null,\"Item2\":null},\"p_vp\":{\"Item1\":null,\"Item2\":null},\"p_ativo\":{\"Item1\":null,\"Item2\":null},\"margembruta\":{\"Item1\":null,\"Item2\":null},\"margemebit\":{\"Item1\":null,\"Item2\":null},\"margemliquida\":{\"Item1\":null,\"Item2\":null},\"p_ebit\":{\"Item1\":null,\"Item2\":null},\"ev_ebit\":{\"Item1\":null,\"Item2\":null},\"dividaliquidaebit\":{\"Item1\":null,\"Item2\":null},\"dividaliquidapatrimonioliquido\":{\"Item1\":null,\"Item2\":null},\"p_sr\":{\"Item1\":null,\"Item2\":null},\"p_capitalgiro\":{\"Item1\":null,\"Item2\":null},\"p_ativocirculante\":{\"Item1\":null,\"Item2\":null},\"roe\":{\"Item1\":null,\"Item2\":null},\"roic\":{\"Item1\":null,\"Item2\":null},\"roa\":{\"Item1\":null,\"Item2\":null},\"liquidezcorrente\":{\"Item1\":null,\"Item2\":null},\"pl_ativo\":{\"Item1\":null,\"Item2\":null},\"passivo_ativo\":{\"Item1\":null,\"Item2\":null},\"giroativos\":{\"Item1\":null,\"Item2\":null},\"receitas_cagr5\":{\"Item1\":null,\"Item2\":null},\"lucros_cagr5\":{\"Item1\":null,\"Item2\":null},\"liquidezmediadiaria\":{\"Item1\":null,\"Item2\":null},\"vpa\":{\"Item1\":null,\"Item2\":null},\"lpa\":{\"Item1\":null,\"Item2\":null},\"valormercado\":{\"Item1\":null,\"Item2\":null}}",
        "orderColumn": "",
        "isAsc": "",
        "page": 0,
        "take": 1000,
        "CategoryType": 1
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            print("Failed to parse JSON.")
    else:
        print(f"Error making request: {response.status_code}")

def update_all_stocks():
    stocks_data = get_all_stocks_from_statusinvest()
    
    if stocks_data:
        for stock_data in stocks_data['list']:
            ticker = stock_data['ticker']
            if Stock.query.filter_by(ticker=ticker).first():
                edit_stock(ticker, stock_data)
            else:
                new_stock(stock_data)
        
        return jsonify({'message': 'Stocks updated successfully.'}), 200
    else:
        return jsonify({'error': 'Error fetching stock data from StatusInvest.'}), 500
