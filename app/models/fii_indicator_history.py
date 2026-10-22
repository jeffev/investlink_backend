from config import db


class FiiIndicatorHistory(db.Model):
    """
    Histórico mensal de fundo imobiliário, escrito pelo pipeline de dados
    (ver data_science_pipeline/database/models.py).

    Esta, diferente das tabelas da CVM, é criada pela migração do backend
    (`c9d0e1f2a3b4`) e o espelho aqui é completo — o pipeline escreve nas
    mesmas colunas. O backend não roda `db.create_all()` desde a mudança para
    o Alembic.

    Sem foreign key para `fiis`, como no pipeline: a CVM recebe informe de mais
    fundos do que o Fundamentus lista, e amarrar as pontas descartaria em
    silêncio o histórico de um fundo que ainda não entrou na tabela.
    """

    __tablename__ = "fii_indicators_history"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False, index=True)
    reference_date = db.Column(db.Date, nullable=False)

    # O Fundamentus não publica o nome do fundo; o informe mensal publica.
    fund_name = db.Column(db.String(255))

    patrimonio_liquido = db.Column(db.Float)
    cotas_emitidas = db.Column(db.Float)
    valor_patrimonial_cota = db.Column(db.Float)
    numero_cotistas = db.Column(db.Float)

    close_price = db.Column(db.Float)
    p_vp = db.Column(db.Float)

    computed_at = db.Column(db.DateTime)

    def to_json(self):
        return {
            "ticker": self.ticker,
            "fund_name": self.fund_name,
            "reference_date": (
                self.reference_date.isoformat() if self.reference_date else None
            ),
            "patrimonio_liquido": self.patrimonio_liquido,
            "valor_patrimonial_cota": self.valor_patrimonial_cota,
            "numero_cotistas": self.numero_cotistas,
            "close_price": self.close_price,
            "p_vp": self.p_vp,
        }
