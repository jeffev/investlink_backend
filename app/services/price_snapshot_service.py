"""
A cotação de hoje entra na série histórica.

O histórico de preço é carregado pelo pipeline de dados, que roda sob
demanda — e estava parado havia um mês e meio quando o sinal de ciclo foi
construído em cima dele. Uma janela de "topo dos últimos 12 meses" que para de
andar envelhece em silêncio: o papel que fez máxima semana passada aparece
como se ainda estivesse longe dela.

A rotina diária já tem a cotação na mão depois de atualizar a base. Gravar uma
linha por papel por dia mantém a janela viva sem depender do pipeline.

A linha gravada tem `high` igual ao fechamento, e não à máxima do pregão, que
esta fonte não publica. Para o sinal de ciclo isso subestima o topo dentro do
dia e não muda a leitura de meses.
"""

import logging
from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from config import db
from models.stock import Stock
from models.stock_price_history import StockPriceHistory


def record_closing_prices(reference=None):
    """Grava o fechamento de hoje. Idempotente pela restrição (ticker, data)."""
    reference = reference or date.today()

    try:
        linhas = [
            {
                "ticker": ticker,
                "date": reference,
                "close_price": preco,
                "high": preco,
                "low": preco,
                "open_price": preco,
            }
            for ticker, preco in db.session.query(Stock.ticker, Stock.price)
            .filter(Stock.active.is_(True), Stock.price > 0)
            .all()
        ]
        if not linhas:
            return 0

        comando = insert(StockPriceHistory).values(linhas)
        comando = comando.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={"close_price": comando.excluded.close_price},
        )
        db.session.execute(comando)
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        logging.error(f"Não foi possível gravar o fechamento do dia: {error}")
        return 0

    logging.info(f"Fechamento gravado: {len(linhas)} papéis em {reference}")
    return len(linhas)
