import math

from config import db


class Stock(db.Model):
    __tablename__ = "stocks"

    ticker = db.Column(db.String(10), primary_key=True)
    companyid = db.Column(db.String(80))
    companyname = db.Column(db.String(255))
    price = db.Column(db.Float)
    p_l = db.Column(db.Float)
    dy = db.Column(db.Float)
    p_vp = db.Column(db.Float)
    p_ebit = db.Column(db.Float)
    p_ativo = db.Column(db.Float)
    ev_ebit = db.Column(db.Float)
    margembruta = db.Column(db.Float)
    margemebit = db.Column(db.Float)
    margemliquida = db.Column(db.Float)
    p_sr = db.Column(db.Float)
    p_capitalgiro = db.Column(db.Float)
    p_ativocirculante = db.Column(db.Float)
    giroativos = db.Column(db.Float)
    roe = db.Column(db.Float)
    roa = db.Column(db.Float)
    roic = db.Column(db.Float)
    dividaliquidapatrimonioliquido = db.Column(db.Float)
    dividaliquidaebit = db.Column(db.Float)
    pl_ativo = db.Column(db.Float)
    passivo_ativo = db.Column(db.Float)
    liquidezcorrente = db.Column(db.Float)
    peg_ratio = db.Column(db.Float)
    receitas_cagr5 = db.Column(db.Float)
    # Both arrive in every StatusInvest payload and had nowhere to land.
    # Traded liquidity is what tells an opportunity apart from a listing
    # the investor could not actually get out of.
    lucros_cagr5 = db.Column(db.Float)
    liquidezmediadiaria = db.Column(db.Float)
    vpa = db.Column(db.Float)
    lpa = db.Column(db.Float)
    valormercado = db.Column(db.Float)
    segmentid = db.Column(db.Integer)
    sectorid = db.Column(db.Integer)
    subsectorid = db.Column(db.Integer)
    subsectorname = db.Column(db.String(255))
    segmentname = db.Column(db.String(255))
    sectorname = db.Column(db.String(255))
    graham_formula = db.Column(db.Float)
    discount_to_graham = db.Column(db.Float)
    roic_rank = db.Column(db.Integer)
    ey_rank = db.Column(db.Integer)
    magic_formula_rank = db.Column(db.Integer)

    # Where the accounting figures above came from, and how recent they are.
    # CVM means audited trailing twelve months; STATUSINVEST means the last
    # closed fiscal year as a third party reported it.
    fundamentals_source = db.Column(db.String(20))
    fundamentals_date = db.Column(db.Date)

    # A ticker the source stopped returning is delisted, not unchanged. Marked
    # rather than deleted: a user may still hold it in their portfolio.
    active = db.Column(db.Boolean, nullable=False, default=True)
    delisted_at = db.Column(db.Date)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.graham_formula = self.get_graham_formula()
        self.discount_to_graham = self.get_discount_to_graham()

    def __repr__(self):
        return (
            f"<Stock(companyname={self.companyname}, ticker={self.ticker}, "
            f"price={self.price}, graham={self.graham_formula}, "
            f"dcto={self.discount_to_graham})>"
        )

    def get_discount_to_graham(self):
        """
        Calculate the percentage premium over the Graham Formula:
        ((Price - Graham Formula) / Price) * 100

        Negative means the price sits below the Graham value (cheap);
        positive means it trades at a premium.

        Returns None whenever the Graham value does not apply — see
        get_graham_formula. Returning 0.0 there would make a loss-making
        company indistinguishable from one priced exactly at fair value.
        """
        graham_formula_value = self.get_graham_formula()
        if not self.price or not graham_formula_value:
            return None
        discount = ((self.price - graham_formula_value) / self.price) * 100
        return round(discount, 2)

    def get_graham_formula(self):
        """
        Calculate the Graham Formula: Intrinsic Value = √ (22.5 x LPA x VPA).
        LPA is Earnings Per Share and VPA is Book Value Per Share.

        Returns None when the formula does not apply: a company with no data,
        with a loss (negative LPA) or with negative equity (negative VPA) has
        no meaningful Graham value.
        """
        if self.lpa is None or self.vpa is None:
            return None
        if self.lpa < 0 or self.vpa < 0:
            return None
        return round(math.sqrt(22.5 * self.lpa * self.vpa), 2)

    def to_json(self):
        return {
            "ticker": self.ticker,
            "companyid": self.companyid,
            "companyname": self.companyname,
            "price": self.price,
            "p_l": self.p_l,
            "dy": self.dy,
            "p_vp": self.p_vp,
            "p_ebit": self.p_ebit,
            "p_ativo": self.p_ativo,
            "ev_ebit": self.ev_ebit,
            "margembruta": self.margembruta,
            "margemebit": self.margemebit,
            "margemliquida": self.margemliquida,
            "p_sr": self.p_sr,
            "p_capitalgiro": self.p_capitalgiro,
            "p_ativocirculante": self.p_ativocirculante,
            "giroativos": self.giroativos,
            "roe": self.roe,
            "roa": self.roa,
            "roic": self.roic,
            "dividaliquidapatrimonioliquido": self.dividaliquidapatrimonioliquido,
            "dividaliquidaebit": self.dividaliquidaebit,
            "pl_ativo": self.pl_ativo,
            "passivo_ativo": self.passivo_ativo,
            "liquidezcorrente": self.liquidezcorrente,
            "peg_ratio": self.peg_ratio,
            "receitas_cagr5": self.receitas_cagr5,
            "lucros_cagr5": self.lucros_cagr5,
            "liquidezmediadiaria": self.liquidezmediadiaria,
            "vpa": self.vpa,
            "lpa": self.lpa,
            "valormercado": self.valormercado,
            "segmentid": self.segmentid,
            "sectorid": self.sectorid,
            "subsectorid": self.subsectorid,
            "subsectorname": self.subsectorname,
            "segmentname": self.segmentname,
            "sectorname": self.sectorname,
            "graham_formula": self.graham_formula,
            "discount_to_graham": self.discount_to_graham,
            "roic_rank": self.roic_rank,
            "ey_rank": self.ey_rank,
            "magic_formula_rank": self.magic_formula_rank,
            "active": self.active,
            "delisted_at": (self.delisted_at.isoformat() if self.delisted_at else None),
            "fundamentals_source": self.fundamentals_source,
            "fundamentals_date": (
                self.fundamentals_date.isoformat() if self.fundamentals_date else None
            ),
        }
