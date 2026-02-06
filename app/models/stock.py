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
        Calculate the percentage discount to the Graham Formula:
        Discount = ((Market Value - Graham Formula) / Market Value) * 100
        """
        graham_formula_value = self.get_graham_formula()
        discount = (
            ((self.price - graham_formula_value) / self.price) * 100
            if self.price and graham_formula_value
            else 0.0
        )
        return round(discount, 2)

    def get_graham_formula(self):
        """
        Calculate the Graham Formula: Intrinsic Value = √ (22.5 x LPA x VPA).
        LPA is Earnings Per Share and VPA is Book Value Per Share.
        """
        if self.lpa and self.vpa and self.lpa >= 0 and self.vpa >= 0:
            formula = math.sqrt(22.5 * self.lpa * self.vpa)
            return round(formula, 2)
        else:
            return 0.0

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
        }
