from config import db


class StockIndicatorHistory(db.Model):
    """
    Yearly fundamental indicators per ticker, written by the data science
    pipeline (see data_science_pipeline/database/models.py).

    Mirrored here so the backend can read it. The table is created by the
    pipeline's own migration, not by `flask db upgrade` — the backend has not
    run `db.create_all()` since the move to Alembic, and creating it from a
    partial mapping would leave the pipeline unable to write.
    """

    __tablename__ = "stock_indicators_history"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(
        db.String(10), db.ForeignKey("stocks.ticker"), nullable=False, index=True
    )
    year = db.Column(db.Integer, nullable=False)

    # Valuation
    dy = db.Column(db.Float)
    p_l = db.Column(db.Float)
    peg_ratio = db.Column(db.Float)
    p_vp = db.Column(db.Float)
    ev_ebitda = db.Column(db.Float)
    ev_ebit = db.Column(db.Float)
    p_ebitda = db.Column(db.Float)
    p_ebit = db.Column(db.Float)
    vpa = db.Column(db.Float)
    p_ativo = db.Column(db.Float)
    lpa = db.Column(db.Float)
    p_sr = db.Column(db.Float)
    p_cap_giro = db.Column(db.Float)
    p_ativo_circ_liq = db.Column(db.Float)

    # Leverage
    div_liq_pl = db.Column(db.Float)
    div_liq_ebitda = db.Column(db.Float)
    div_liq_ebit = db.Column(db.Float)
    pl_ativos = db.Column(db.Float)
    passivos_ativos = db.Column(db.Float)

    # Profitability
    m_bruta = db.Column(db.Float)
    m_ebitda = db.Column(db.Float)
    m_ebit = db.Column(db.Float)
    m_liquida = db.Column(db.Float)
    roe = db.Column(db.Float)
    roa = db.Column(db.Float)
    roic = db.Column(db.Float)

    # Efficiency and liquidity
    giro_ativos = db.Column(db.Float)
    liq_corrente = db.Column(db.Float)

    # Growth
    cagr_receitas_5 = db.Column(db.Float)
    cagr_lucros_5 = db.Column(db.Float)

    # Derived
    graham_formula = db.Column(db.Float)

    scraped_at = db.Column(db.DateTime)

    def to_json(self):
        return {
            "ticker": self.ticker,
            "year": self.year,
            "dy": self.dy,
            "p_l": self.p_l,
            "p_vp": self.p_vp,
            "ev_ebit": self.ev_ebit,
            "roe": self.roe,
            "roic": self.roic,
            "m_liquida": self.m_liquida,
        }
