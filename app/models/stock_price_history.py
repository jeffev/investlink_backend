from config import db


class StockPriceHistory(db.Model):
    __tablename__ = "stock_prices_history"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(
        db.String(10), db.ForeignKey("stocks.ticker"), nullable=False, index=True
    )
    date = db.Column(db.Date, nullable=False)
    open_price = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close_price = db.Column(db.Float)
    volume = db.Column(db.Float)
