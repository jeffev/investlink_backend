from config import db


class TickerCvmMap(db.Model):
    """
    Bridge from a B3 ticker root to a CVM company code, written by the data
    science pipeline (data_sources/ticker_cvm_map.py).

    Read-only from the backend's point of view. Keyed by the four-character
    issuer root because PETR3 and PETR4 are the same company and share one set
    of financial statements.
    """

    __tablename__ = "ticker_cvm_map"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    ticker_root = db.Column(db.String(4), nullable=False, unique=True, index=True)
    cd_cvm = db.Column(db.String(10), nullable=False, index=True)
    cnpj = db.Column(db.String(20))
    company_name = db.Column(db.String(255))
    trading_name = db.Column(db.String(255))
    refreshed_at = db.Column(db.DateTime)


class CvmFundamentalsLtm(db.Model):
    """
    Trailing-twelve-month fundamentals derived from audited CVM filings.

    Read-only from the backend. One row per company, keyed by CD_CVM — join
    through TickerCvmMap to reach a ticker.

    Null means "does not apply", not "zero": a bank has no EBIT, no current
    ratio and no net debt, because its chart of accounts has neither a
    liquidity split nor an operating/financial result split.
    """

    __tablename__ = "cvm_fundamentals_ltm"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    cd_cvm = db.Column(db.String(10), nullable=False, unique=True, index=True)
    company_name = db.Column(db.String(255))

    ltm_start = db.Column(db.Date)
    ltm_end = db.Column(db.Date)
    balance_date = db.Column(db.Date)

    receita_ltm = db.Column(db.Float)
    lucro_bruto_ltm = db.Column(db.Float)
    ebit_ltm = db.Column(db.Float)
    ebitda_ltm = db.Column(db.Float)
    lucro_liquido_ltm = db.Column(db.Float)
    lucro_controladores_ltm = db.Column(db.Float)
    depreciacao_ltm = db.Column(db.Float)

    patrimonio_liquido = db.Column(db.Float)
    ativo_total = db.Column(db.Float)
    divida_liquida = db.Column(db.Float)
    acoes_circulacao = db.Column(db.Float)

    lpa_ltm = db.Column(db.Float)
    vpa = db.Column(db.Float)
    roe_ltm = db.Column(db.Float)
    roic_ltm = db.Column(db.Float)
    m_bruta_ltm = db.Column(db.Float)
    m_ebit_ltm = db.Column(db.Float)
    m_liquida_ltm = db.Column(db.Float)
    div_liq_ebit = db.Column(db.Float)
    div_liq_ebitda = db.Column(db.Float)
    div_liq_pl = db.Column(db.Float)
    liq_corrente = db.Column(db.Float)
    graham_formula = db.Column(db.Float)

    computed_at = db.Column(db.DateTime)

    def to_json(self):
        return {
            "cd_cvm": self.cd_cvm,
            "company_name": self.company_name,
            "ltm_start": self.ltm_start.isoformat() if self.ltm_start else None,
            "ltm_end": self.ltm_end.isoformat() if self.ltm_end else None,
            "receita_ltm": self.receita_ltm,
            "ebit_ltm": self.ebit_ltm,
            "ebitda_ltm": self.ebitda_ltm,
            "lucro_liquido_ltm": self.lucro_liquido_ltm,
            "lpa_ltm": self.lpa_ltm,
            "vpa": self.vpa,
            "roe_ltm": self.roe_ltm,
            "roic_ltm": self.roic_ltm,
            "m_bruta_ltm": self.m_bruta_ltm,
            "m_ebit_ltm": self.m_ebit_ltm,
            "m_liquida_ltm": self.m_liquida_ltm,
            "div_liq_ebit": self.div_liq_ebit,
            "div_liq_ebitda": self.div_liq_ebitda,
            "liq_corrente": self.liq_corrente,
            "patrimonio_liquido": self.patrimonio_liquido,
            "divida_liquida": self.divida_liquida,
            "acoes_circulacao": self.acoes_circulacao,
        }


class CvmFinancials(db.Model):
    """
    Raw CVM statement rows, one per company per reporting window.

    Read-only from the backend, which needs only the annual rows
    (period_months = 12) to tell how many of the last years a company actually
    made money.
    """

    __tablename__ = "cvm_financials"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    cd_cvm = db.Column(db.String(10), nullable=False, index=True)
    company_name = db.Column(db.String(255))
    doc_type = db.Column(db.String(3), nullable=False)
    period_type = db.Column(db.String(5), nullable=False)
    scope = db.Column(db.String(3))
    period_end = db.Column(db.Date, nullable=False)
    period_months = db.Column(db.Integer)
    receita = db.Column(db.Float)
    ebit = db.Column(db.Float)
    lucro_liquido = db.Column(db.Float)
    patrimonio_liquido = db.Column(db.Float)
    divida_liquida = db.Column(db.Float)
