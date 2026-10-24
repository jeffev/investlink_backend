"""
Onde o ativo está no próprio ciclo.

O score responde "é bom?" comparando a empresa com as do setor. Ele não
responde **"é hora?"** — e uma ação excelente no topo histórico e a mesma ação
40% abaixo do pico recebem exatamente a mesma nota, sendo decisões
completamente diferentes.

A armadilha, que este projeto já provou na prática:
    Na primeira execução real do score de FII, o topo dos três perfis era
    formado pelos quatro fundos de crédito mais descontados da bolsa — eram
    os mais caídos *e* os mais quebrados. **Queda grande, sozinha, seleciona
    deterioração, não pechincha.**

    O que separa os dois é o fundamento enquanto o preço cai. Caiu e o lucro
    segue crescendo é oportunidade de ciclo; caiu e o lucro caiu junto é
    armadilha. Por isso a queda só pontua quando o fundamento está de pé — e
    quando não está, vira alerta em vez de nota.

Os limiares saem da distribuição real, não de gosto: entre as 204 ações
líquidas da base, a mediana está 10% abaixo do topo de 12 meses e o primeiro
quartil, 25% abaixo.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError

from config import db
from models.stock import Stock
from models.stock_indicator_history import StockIndicatorHistory
from models.stock_price_history import StockPriceHistory

# Doze meses é a janela do "está em alta ou caiu": o topo histórico responde
# outra pergunta — pode ser de 2008 e não diz nada sobre o momento.
WINDOW_WEEKS = 52

# Medidos sobre as ações líquidas da base: p75 ≈ 0% (coladas no topo),
# mediana −10%, p25 −25%.
NEAR_PEAK = -5.0
RELEVANT_DROP = -25.0

# Abaixo de três exercícios fechados a mediana do próprio histórico é ruído.
MIN_YEARS = 3
WINDOW_YEARS = 5

# Estados possíveis.
OPORTUNIDADE = "OPORTUNIDADE_DE_CICLO"
TOPO = "PERTO_DO_TOPO"
DETERIORACAO = "QUEDA_COM_DETERIORACAO"
NEUTRO = "NEUTRO"

CRESCENDO = "CRESCENDO"
CAINDO = "CAINDO"
ESTAVEL = "ESTAVEL"


# Abaixo disto a janela não é uma janela: com um ou dois fechamentos, o "topo
# de 12 meses" é o preço de hoje, e o papel era classificado como colado na
# máxima sem que nada tivesse sido observado. Nove ações estavam nessa
# situação, e 637 têm só o fechamento desta semana.
MIN_PRICE_POINTS = 20


def get_drawdown_map(tickers):
    """
    {ticker: queda percentual desde o topo de 12 meses}, sempre <= 0.

    O topo considera a cotação de hoje: um papel fazendo máxima nova tem queda
    zero, não queda positiva — "subiu 3% acima do topo" não é uma frase que
    descreva alguma coisa.
    """
    if not tickers:
        return {}

    desde = date.today() - timedelta(weeks=WINDOW_WEEKS)
    try:
        picos = {
            ticker: pico
            for ticker, pico, _ in db.session.query(
                StockPriceHistory.ticker,
                func.max(StockPriceHistory.high),
                func.count(StockPriceHistory.id),
            )
            .filter(
                StockPriceHistory.ticker.in_(tickers),
                StockPriceHistory.date >= desde,
            )
            .group_by(StockPriceHistory.ticker)
            .having(func.count(StockPriceHistory.id) >= MIN_PRICE_POINTS)
            .all()
        }
        precos = dict(
            db.session.query(Stock.ticker, Stock.price)
            .filter(Stock.ticker.in_(tickers))
            .all()
        )
    except SQLAlchemyError as error:
        db.session.rollback()
        logging.error(f"Histórico de preço indisponível para o ciclo: {error}")
        return {}

    quedas = {}
    for ticker, preco in precos.items():
        pico = picos.get(ticker)
        if not preco or not pico:
            continue
        topo = max(pico, preco)
        quedas[ticker] = round((preco - topo) / topo * 100, 1)
    return quedas


def get_valuation_ratio_map(tickers, indicator="p_l"):
    """
    {ticker: múltiplo de hoje ÷ mediana do próprio histórico}.

    Abaixo de 1 o ativo está mais barato do que costuma ser. É a metade
    temporal do valuation — a outra, contra os vizinhos de setor, o score já
    tinha.
    """
    if not tickers:
        return {}

    ultimo_fechado = date.today().year - 1
    primeiro = ultimo_fechado - WINDOW_YEARS + 1
    coluna = getattr(StockIndicatorHistory, indicator)

    try:
        linhas = (
            db.session.query(StockIndicatorHistory.ticker, coluna)
            .filter(
                StockIndicatorHistory.ticker.in_(tickers),
                StockIndicatorHistory.year >= primeiro,
                StockIndicatorHistory.year <= ultimo_fechado,
                coluna.isnot(None),
                coluna > 0,
            )
            .all()
        )
        atuais = dict(
            db.session.query(Stock.ticker, getattr(Stock, indicator))
            .filter(Stock.ticker.in_(tickers))
            .all()
        )
    except SQLAlchemyError as error:
        db.session.rollback()
        logging.error(f"Histórico de múltiplo indisponível: {error}")
        return {}

    por_ticker = {}
    for ticker, valor in linhas:
        por_ticker.setdefault(ticker, []).append(valor)

    razoes = {}
    for ticker, valores in por_ticker.items():
        if len(valores) < MIN_YEARS:
            continue
        atual = atuais.get(ticker)
        if not atual or atual <= 0:
            continue
        mediana = sorted(valores)[len(valores) // 2]
        if mediana <= 0:
            continue
        razoes[ticker] = round(atual / mediana, 3)
    return razoes


def get_profit_trend_map(tickers):
    """
    {raiz do ticker: CRESCENDO | ESTAVEL | CAINDO} pelo lucro anual da CVM.

    É o discriminador: o mesmo preço caindo significa coisas opostas conforme
    o lucro esteja subindo ou afundando junto.
    """
    from services.cvm_fundamentals_service import ticker_root

    raizes = {raiz for raiz in map(ticker_root, tickers) if raiz}
    if not raizes:
        return {}

    primeiro_ano = date.today().year - WINDOW_YEARS
    try:
        linhas = db.session.execute(
            text("""
                SELECT m.ticker_root,
                       EXTRACT(YEAR FROM f.period_end) AS ano,
                       f.lucro_liquido
                  FROM ticker_cvm_map m
                  JOIN cvm_financials f ON f.cd_cvm = m.cd_cvm
                 WHERE m.ticker_root = ANY(:raizes)
                   AND f.period_months = 12
                   AND f.lucro_liquido IS NOT NULL
                   AND EXTRACT(YEAR FROM f.period_end) >= :primeiro
                """),
            {"raizes": list(raizes), "primeiro": primeiro_ano},
        ).all()
    except SQLAlchemyError as error:
        db.session.rollback()
        # As tabelas da CVM pertencem ao pipeline e podem não existir num
        # servidor onde ele ainda não rodou. Sem o discriminador, a queda não
        # pontua — conservador de propósito.
        logging.error(f"Histórico de lucro indisponível para o ciclo: {error}")
        return {}

    por_raiz = {}
    for raiz, ano, lucro in linhas:
        por_raiz.setdefault(raiz, {})[int(ano)] = float(lucro)

    tendencias = {}
    for raiz, por_ano in por_raiz.items():
        if len(por_ano) < MIN_YEARS:
            continue
        anos = sorted(por_ano)
        recente = por_ano[anos[-1]]
        anteriores = [por_ano[ano] for ano in anos[:-1]]
        referencia = sorted(anteriores)[len(anteriores) // 2]

        if referencia == 0:
            continue
        variacao = (recente - referencia) / abs(referencia)
        if recente < 0 or variacao <= -0.20:
            tendencias[raiz] = CAINDO
        elif variacao >= 0.10:
            tendencias[raiz] = CRESCENDO
        else:
            tendencias[raiz] = ESTAVEL
    return tendencias


def classify(drawdown, profit_trend, valuation_ratio):
    """
    O estado do ciclo, em uma palavra.

    `None` quando não há queda medida: sem histórico de preço não dá para
    afirmar nada, e inventar "neutro" seria dizer que foi verificado.
    """
    if drawdown is None:
        return None

    if drawdown >= NEAR_PEAK:
        caro_para_si = valuation_ratio is not None and valuation_ratio > 1.1
        return TOPO if caro_para_si or drawdown >= 0 else NEUTRO

    if drawdown <= RELEVANT_DROP:
        if profit_trend == CAINDO:
            return DETERIORACAO
        if profit_trend in (CRESCENDO, ESTAVEL):
            return OPORTUNIDADE

    return NEUTRO


def describe(state, drawdown, profit_trend):
    """A frase que vai para o card, com o número que a sustenta."""
    if state == OPORTUNIDADE:
        lucro = (
            "o lucro segue crescendo"
            if profit_trend == CRESCENDO
            else "o lucro se manteve"
        )
        return f"Caiu {abs(drawdown):.0f}% do topo de 12 meses e {lucro}"
    if state == DETERIORACAO:
        return (
            f"Caiu {abs(drawdown):.0f}% do topo de 12 meses, mas o lucro caiu "
            "junto — queda com deterioração, não desconto"
        )
    if state == TOPO:
        return "Perto da máxima de 12 meses — comprando no topo do próprio ciclo"
    return None


def _valor_pontuavel(queda, estado):
    """
    A queda como razão `preço / topo`, quando ela pode entrar no ranking.

    Razão, e não porcentagem, porque a convenção do projeto trata zero como
    "sem dado" — e queda zero é justamente o papel colado no topo, o pior
    ponto de entrada, que sumia do ranking em vez de pesar contra.

    **Queda profunda só pontua quando se sabe que o fundamento resistiu.**
    Antes, a exclusão valia só para a deterioração comprovada, e a queda com
    tendência de lucro *desconhecida* recebia nota cheia: a AZTE3, que tem
    prejuízo e nenhum histórico de lucro na CVM, tirou **100** no pilar de
    ciclo. Ausência de dado virava elogio.

    Queda rasa e papel no topo continuam no ranking — ali a nota é penalidade
    ou neutralidade, e não depende de afirmar nada sobre o fundamento.
    """
    if queda is None:
        return None
    if queda <= RELEVANT_DROP and estado != OPORTUNIDADE:
        return None
    return round(1 + queda / 100, 4)


def attach_cycle_signals(stocks):
    """
    Pendura ciclo, razão histórica e tendência de lucro nos objetos em memória.

    Em memória, e não no banco, pelo mesmo motivo dos sinais de FII: mudam a
    cada cotação e só servem ao percentil desta execução.
    """
    from services.cvm_fundamentals_service import ticker_root

    tickers = [stock.ticker for stock in stocks]
    quedas = get_drawdown_map(tickers)
    razoes = get_valuation_ratio_map(tickers)
    tendencias = get_profit_trend_map(tickers)

    for stock in stocks:
        queda = quedas.get(stock.ticker)
        razao = razoes.get(stock.ticker)
        tendencia = tendencias.get(ticker_root(stock.ticker))
        estado = classify(queda, tendencia, razao)

        stock.queda_12m = queda
        stock.valuation_vs_historico = razao
        stock.lucro_tendencia = tendencia
        stock.cycle_state = estado
        stock.cycle_message = describe(estado, queda, tendencia)

        # Razão, e não a queda em porcentagem, por um motivo bem concreto:
        # a convenção do projeto trata zero como "sem dado" (as fontes
        # publicam ausência como zero), e queda zero é justamente o papel
        # colado no topo — o pior ponto de entrada, que sumia do ranking em
        # vez de pesar contra. Como razão, o topo vale 1,0 e participa.
        #
        # Menor é melhor: 0,6 é um papel 40% abaixo do topo.
        #
        # A exceção é a queda com deterioração: ali o número é bom pelo motivo
        # errado, e deixá-lo pontuar foi o que pôs os quatro fundos de crédito
        # em aflição no topo da vitrine de FII.
        stock.preco_sobre_topo = _valor_pontuavel(queda, estado)
