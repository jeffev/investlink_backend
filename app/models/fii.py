from config import db


class Fii(db.Model):
    __tablename__ = "fiis"

    ticker = db.Column(db.String(10), primary_key=True)
    companyid = db.Column(db.String(80))
    companyname = db.Column(db.String(255))
    price = db.Column(db.Float)
    sectorid = db.Column(db.Integer)
    sectorname = db.Column(db.String(255))
    subsectorid = db.Column(db.Integer)
    subsectorname = db.Column(db.String(255))
    segment = db.Column(db.String(255))
    segmentid = db.Column(db.Integer)
    gestao = db.Column(db.Integer)
    gestao_f = db.Column(db.String(255))
    dy = db.Column(db.Float)
    p_vp = db.Column(db.Float)
    valorpatrimonialcota = db.Column(db.Float)
    liquidezmediadiaria = db.Column(db.Float)
    percentualcaixa = db.Column(db.Float)
    dividend_cagr = db.Column(db.Float)
    cota_cagr = db.Column(db.Float)
    numerocotistas = db.Column(db.Float)
    numerocotas = db.Column(db.Float)
    patrimonio = db.Column(db.Float)
    lastdividend = db.Column(db.Float)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<Fii(companyname={self.companyname}, ticker={self.ticker}, price={self.price})>"

    def to_json(self):
        return {
            "ticker": self.ticker,
            "companyid": self.companyid,
            "companyname": self.companyname,
            "price": self.price,
            "sectorid": self.sectorid,
            "sectorname": self.sectorname,
            "subsectorid": self.subsectorid,
            "subsectorname": self.subsectorname,
            "segment": self.segment,
            "segmentid": self.segmentid,
            "gestao": self.gestao,
            "gestao_f": self.gestao_f,
            "dy": self.dy,
            "p_vp": self.p_vp,
            "valorpatrimonialcota": self.valorpatrimonialcota,
            "liquidezmediadiaria": self.liquidezmediadiaria,
            "percentualcaixa": self.percentualcaixa,
            "dividend_cagr": self.dividend_cagr,
            "cota_cagr": self.cota_cagr,
            "numerocotistas": self.numerocotistas,
            "numerocotas": self.numerocotas,
            "patrimonio": self.patrimonio,
            "lastdividend": self.lastdividend,
        }
