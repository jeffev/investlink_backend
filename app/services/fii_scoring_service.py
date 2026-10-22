"""
Ranqueia fundos imobiliários em quatro pilares, dentro do próprio segmento.

Por que não reaproveitar os pilares de ação:
    Graham, ROE e CAGR de lucro não existem num FII. O fundo não tem lucro por
    ação nem patrimônio operacional no mesmo sentido — tem cota, provento e
    vacância. Forçar os dois ativos na mesma fórmula produziria pilares sempre
    nulos de um lado.

Por que dentro do segmento:
    P/VP de 0,85 é barato num fundo de tijolo e rotineiro num fundo de papel,
    que marca os CRI a mercado. Ranquear tudo junto devolveria uma lista de
    fundos de papel e chamaria isso de descoberta.

Por que os limiares são estes:
    Foram medidos sobre os 570 fundos publicados pelo Fundamentus, não
    escolhidos por gosto. A mediana de liquidez do universo é R$ 15 mil/dia —
    a maior parte dos FIIs listados é intransacionável — e apenas 178 fundos
    giram R$ 200 mil/dia ou mais.
"""

import json
import logging
import statistics
from datetime import date, datetime, timedelta

from config import db
from models.fii import Fii
from models.fii_indicator_history import FiiIndicatorHistory
from models.fii_score import FiiScore
from services.scoring_service import (
    _entry,
    _is_usable,
    compute_pillars,
    percentile_ranks,
    weighted_score,
)

# Cada métrica é (atributo do fundo, menor_é_melhor).
FII_PILLAR_METRICS = {
    # As duas metades do valuation: barato frente aos vizinhos de segmento e
    # barato frente ao próprio passado. Só a primeira não distingue um fundo
    # descontado de um segmento inteiro fora de moda.
    "valuation": [("p_vp", True), ("p_vp_vs_historico", True)],
    "renda": [("dy", False), ("ffo_yield", False), ("dividend_cagr", False)],
    "liquidez": [("liquidezmediadiaria", False), ("numerocotistas", False)],
    # A tendência do patrimônio por cota é o único sinal aqui que distingue
    # fundo barato de fundo encolhendo.
    "estrutura": [
        ("vp_cota_tendencia", False),
        ("cota_cagr", False),
        ("qtd_imoveis", False),
    ],
}

# `percentualcaixa` ficou de fora de propósito: caixa demais é capital parado
# derrubando o rendimento, caixa de menos é fundo sem folga. A métrica não é
# monotônica, e percentil só sabe ordenar o que é monotônico.
#
# `vacancia_media` também: entre os 289 fundos com imóvel, 145 declaram
# exatamente 0,00%, o que mistura "totalmente ocupado" com "não informado".
# Ela entra como alerta quando está alta, onde o zero ambíguo não atrapalha.

FII_PROFILES = {
    "EQUILIBRADO": {
        "valuation": 0.30,
        "renda": 0.30,
        "liquidez": 0.20,
        "estrutura": 0.20,
    },
    "RENDA": {
        "valuation": 0.20,
        "renda": 0.50,
        "liquidez": 0.20,
        "estrutura": 0.10,
    },
    "VALOR": {
        "valuation": 0.50,
        "renda": 0.20,
        "liquidez": 0.20,
        "estrutura": 0.10,
    },
}

DEFAULT_FII_PROFILE = "EQUILIBRADO"

MIN_SEGMENT_SIZE = 5

# Janela do "barato para ele mesmo". Três anos cobrem um ciclo de juros
# inteiro, que é o que move o P/VP de fundo imobiliário.
HISTORY_WINDOW_MONTHS = 36
# Abaixo disto a mediana é ruído: fundo recém-listado ainda não tem "próprio
# histórico" contra o qual comparar.
MIN_HISTORY_MONTHS = 12

# Guard rails, todos medidos sobre o universo publicado.
# R$ 200 mil/dia deixa 178 dos 570 fundos — bem mais permissivo que o piso de
# R$ 1 milhão das ações, porque FII é mercado menor e o corte de ação zeraria
# a lista.
MIN_DAILY_LIQUIDITY = 200_000.0
# Acima disto o P/VP é erro de dado, não oportunidade: o p90 do universo é
# 1,16 e o topo da tabela traz fundos com P/VP na casa dos milhares.
MAX_PLAUSIBLE_P_VP = 5.0
# Mediana de DY do universo: 8,4%; p90: 17,1%. Acima de 20% quase sempre é
# provento extraordinário ou amortização de cota contada como rendimento.
IMPLAUSIBLE_DIVIDEND_YIELD = 20.0
# Piso do desconto, medido: entre os 177 fundos que passam pela liquidez, o
# p5 de P/VP é 0,44 e só quatro ficam abaixo de 0,30. Cota a 0,12× o
# patrimônio não é pechincha — é o mercado dizendo que não acredita no
# patrimônio declarado. Sem o piso, os quatro fundos de crédito mais
# descontados do mercado lideravam os três perfis da vitrine.
DISTRESS_P_VP = 0.45

# Abaixo disto o patrimônio por cota está encolhendo de verdade, não
# oscilando: na janela de 32 meses carregada, os fundos saudáveis ficam entre
# -4% e +6% e os de crédito em aflição entre -7% e -13%.
SHRINKING_BOOK_VALUE = -5.0

HIGH_VACANCY = 20.0
HEALTHY_DIVIDEND_YIELD = 8.0
CHEAP_P_VP = 0.90
STRONG_PILLAR = 60.0

MAX_REASONS = 3
MAX_RED_FLAGS = 3


def scoring_value(fii, attribute):
    """
    O valor que a métrica leva para o pilar, que nem sempre é o publicado.

    Um DY de 129% — existe um na tabela — não é quinze vezes melhor que um de
    9%: é amortização contada como rendimento. Acima do limiar de
    plausibilidade o yield é aparado, então o pagamento extraordinário empata
    com os melhores sustentáveis em vez de ficar acima deles.

    O P/VP faz o contrário abaixo do piso de aflição: some. Cota a 0,12× o
    patrimônio não é doze vezes mais barata que uma a 1,0× — é o mercado
    dizendo que não acredita no patrimônio declarado, e a diferença entre as
    duas leituras não está nos dados que este score tem. O fundo continua na
    lista, com o alerta, ranqueado pelos pilares que dá para avaliar.
    """
    value = getattr(fii, attribute, None)
    if attribute == "dy" and _is_usable(value):
        return min(value, IMPLAUSIBLE_DIVIDEND_YIELD)
    if attribute == "p_vp" and _is_usable(value) and value < DISTRESS_P_VP:
        # Nem aparado nem premiado: sem valor. Aparar empatava o fundo a
        # 0,18× com o melhor da faixa saudável, e era isso que mantinha os
        # fundos de crédito em aflição no topo dos três perfis.
        return None
    return value


# ── Histórico do próprio fundo ───────────────────────────────────────────────


def _history_rows(tickers, first_month):
    return (
        db.session.query(
            FiiIndicatorHistory.ticker,
            FiiIndicatorHistory.reference_date,
            FiiIndicatorHistory.p_vp,
            FiiIndicatorHistory.close_price,
        )
        .filter(
            FiiIndicatorHistory.ticker.in_(tickers),
            FiiIndicatorHistory.p_vp.isnot(None),
            FiiIndicatorHistory.reference_date >= first_month,
        )
        .order_by(FiiIndicatorHistory.reference_date)
        .all()
    )


def get_history_signals(tickers):
    """
    O que o histórico do próprio fundo diz, em dois números.

    `p_vp_mediano`: contra o que o P/VP de hoje é comparado. Mediana, e não
    média, porque uma emissão de cotas ou um mês de marcação atípica desloca a
    média e deixa a mediana onde está.

    `vp_tendencia`: quanto o patrimônio por cota variou na janela, em
    porcentagem. É o que separa um fundo barato de um fundo quebrado — os dois
    têm P/VP baixo e DY alto, e só o segundo está encolhendo o patrimônio que
    distribui.

    O patrimônio por cota sai de `close_price / p_vp`, e não da coluna
    `valor_patrimonial_cota`: a coluna é o que a CVM publicou na data, sem
    ajuste de desdobramento, e num fundo que desdobrou 1:10 a série cai 90%
    de um mês para o outro. O ALZR11 aparecia com -89,9% de "erosão" que era
    só o desdobramento; pela razão ajustada ele aparece com +0,6%.
    """
    if not tickers:
        return {}

    first_month = date.today() - timedelta(days=HISTORY_WINDOW_MONTHS * 31)
    por_fundo = {}
    for ticker, _, p_vp, close_price in _history_rows(tickers, first_month):
        if not p_vp or not 0 < p_vp <= MAX_PLAUSIBLE_P_VP:
            continue
        por_fundo.setdefault(ticker, []).append((p_vp, close_price))

    sinais = {}
    for ticker, linhas in por_fundo.items():
        if len(linhas) < MIN_HISTORY_MONTHS:
            continue

        patrimoniais = [close / p_vp for p_vp, close in linhas if close and p_vp]
        sinais[ticker] = {
            "p_vp_mediano": statistics.median(p_vp for p_vp, _ in linhas),
            "vp_tendencia": _variacao(patrimoniais),
            "meses": len(linhas),
        }
    return sinais


def _variacao(serie):
    """Variação percentual entre a primeira e a última observação."""
    if len(serie) < 2 or not serie[0]:
        return None
    return round((serie[-1] / serie[0] - 1) * 100, 1)


def attach_history_signals(fiis, sinais):
    """
    Pendura os sinais no objeto em memória, sem coluna no banco.

    Eles mudam a cada cotação e só existem para alimentar o percentil desta
    execução; gravá-los criaria uma segunda verdade para envelhecer sozinha.
    """
    for fii in fiis:
        do_fundo = sinais.get(fii.ticker) or {}
        mediana = do_fundo.get("p_vp_mediano")

        # Passa pelo `scoring_value` de propósito: quem decide que um P/VP
        # não é interpretável é um lugar só. Sem isto, o fundo em aflição
        # perdia a nota de valuation pelo P/VP absoluto e a recuperava pela
        # comparação com o próprio passado — que é ainda mais favorável
        # justamente porque ele está desabando. O HCTR11 seguia em quarto no
        # perfil VALOR por esse caminho.
        p_vp = scoring_value(fii, "p_vp")
        fii.p_vp_vs_historico = (
            round(p_vp / mediana, 4) if mediana and _is_usable(p_vp) else None
        )
        fii.vp_cota_tendencia = do_fundo.get("vp_tendencia")
        fii.meses_de_historico = do_fundo.get("meses")


# ── Guard rails ──────────────────────────────────────────────────────────────


def check_eligibility(fii):
    """Motivos para o fundo não ser ranqueado. Lista vazia significa que passa."""
    reasons = []

    if not _is_usable(fii.price):
        reasons.append(_entry("SEM_PRECO", "Fundo sem cotação na fonte de dados"))

    liquidity = fii.liquidezmediadiaria
    if liquidity is None or liquidity < MIN_DAILY_LIQUIDITY:
        reasons.append(
            _entry(
                "LIQUIDEZ_BAIXA",
                "Liquidez diária abaixo de R$ 200 mil — sair da posição pode "
                "levar dias e derrubar o preço",
            )
        )

    if not _is_usable(fii.dy):
        # Fundo imobiliário existe para distribuir. Sem rendimento declarado,
        # o pilar de renda fica vazio e o `weighted_score` renormaliza os
        # pesos em cima dos outros três — foi assim que um fundo com DY de
        # 0,00% liderou o perfil equilibrado. A regra de renormalizar nasceu
        # para o banco que não tem EBIT, onde o pilar ausente é fato contábil;
        # aqui o pilar ausente é o motivo de se comprar o ativo.
        reasons.append(
            _entry(
                "SEM_RENDIMENTO",
                "Nenhum rendimento declarado na fonte — sem isso não dá para "
                "avaliar um fundo cuja razão de existir é distribuir",
            )
        )

    p_vp = fii.p_vp
    if not _is_usable(p_vp):
        reasons.append(_entry("SEM_P_VP", "Fundo sem P/VP publicado"))
    elif p_vp < 0 or p_vp > MAX_PLAUSIBLE_P_VP:
        reasons.append(
            _entry(
                "DADO_INCONSISTENTE",
                f"P/VP de {p_vp:,.2f} está fora de qualquer faixa plausível — "
                "o dado da fonte está errado",
            )
        )

    return reasons


# ── Percentis ────────────────────────────────────────────────────────────────


def _peer_group(fii):
    """
    Com quem este fundo é comparável.

    Segmento sozinho não serve: "Multicategoria" e "Outros" somam 126 dos 177
    fundos líquidos, e dentro deles convivem fundo de tijolo e fundo de papel.
    P/VP de fundo de papel é CRI marcado a mercado; de fundo de tijolo é
    imóvel avaliado. Comparar os dois num balde só faz o desconto de crédito
    parecer imóvel barato.

    `qtd_imoveis` é o que separa os dois com o dado que já existe.
    """
    tem_imovel = bool(fii.qtd_imoveis)
    return f"{fii.segment or 'SEM SEGMENTO'} · {'tijolo' if tem_imovel else 'papel'}"


def _group_by_segment(fiis):
    """Baldes de comparáveis, com os pequenos jogados num balde de mercado."""
    by_segment = {}
    for fii in fiis:
        by_segment.setdefault(_peer_group(fii), []).append(fii)

    groups = []
    market = []
    for segment, members in by_segment.items():
        if len(members) >= MIN_SEGMENT_SIZE:
            groups.append((segment, members))
        else:
            market.extend(members)
    if market:
        groups.append(("MERCADO", market))
    return groups


def compute_metric_percentiles(fiis):
    """
    {ticker: {métrica: percentil}}, ranqueado dentro de cada segmento.

    Fundo sem a métrica fica de fora do ranking daquela métrica — um branco
    nunca compete como se fosse valor.
    """
    percentiles = {fii.ticker: {} for fii in fiis}

    for _, members in _group_by_segment(fiis):
        for metrics in FII_PILLAR_METRICS.values():
            for attribute, lower_is_better in metrics:
                # Filtra pelo valor de pontuação, não pelo bruto: o P/VP em
                # faixa de aflição vira None, e comparar None com float na
                # ordenação derruba o refresh inteiro.
                values = {}
                for fii in members:
                    value = scoring_value(fii, attribute)
                    if _is_usable(value):
                        values[fii.ticker] = value
                for ticker, rank in percentile_ranks(values, lower_is_better).items():
                    percentiles[ticker][attribute] = rank
    return percentiles


# ── Motivos e alertas ────────────────────────────────────────────────────────


def build_reasons(fii, pillars):
    """Por que o fundo está na lista, pilar mais forte primeiro."""
    labels = {
        "valuation": "Negociado barato frente ao próprio segmento",
        "renda": "Renda acima da média do segmento",
        "liquidez": "Mais líquido que a média do segmento",
        "estrutura": "Estrutura melhor que a do segmento",
    }
    ranked = sorted(
        ((pillar, value) for pillar, value in pillars.items() if value is not None),
        key=lambda item: item[1],
        reverse=True,
    )

    reasons = [
        _entry(f"PILAR_{pillar.upper()}", f"{labels[pillar]} ({value:.0f}/100)")
        for pillar, value in ranked
        if value >= STRONG_PILLAR
    ]

    if _is_usable(fii.p_vp) and 0 < fii.p_vp <= CHEAP_P_VP:
        reasons.append(
            _entry(
                "P_VP_DESCONTO",
                f"Cota a {fii.p_vp:.2f}× o valor patrimonial — "
                f"desconto de {(1 - fii.p_vp) * 100:.0f}% sobre o patrimônio",
            )
        )
    if (
        _is_usable(fii.dy)
        and HEALTHY_DIVIDEND_YIELD <= fii.dy < IMPLAUSIBLE_DIVIDEND_YIELD
    ):
        reasons.append(_entry("DY_SAUDAVEL", f"Dividend Yield de {fii.dy:.1f}%"))

    return reasons[:MAX_REASONS]


def build_red_flags(fii):
    """
    O que pode dar errado. Ao lado dos motivos de propósito: lista que só
    argumenta a favor do ativo é propaganda, não análise.
    """
    flags = []

    if _is_usable(fii.dy) and fii.dy >= IMPLAUSIBLE_DIVIDEND_YIELD:
        flags.append(
            _entry(
                "DY_IMPLAUSIVEL",
                f"DY de {fii.dy:.1f}% dificilmente se repete — confira se não "
                "é amortização de cota contada como rendimento",
            )
        )
    # Só faz sentido em fundo com imóvel: no fundo de papel a vacância é zero
    # por não existir imóvel, não por estar tudo alugado.
    if (
        _is_usable(fii.qtd_imoveis)
        and _is_usable(fii.vacancia_media)
        and fii.vacancia_media >= HIGH_VACANCY
    ):
        flags.append(
            _entry(
                "VACANCIA_ALTA",
                f"Vacância média de {fii.vacancia_media:.1f}% — parte do "
                "patrimônio não está gerando aluguel",
            )
        )
    tendencia = getattr(fii, "vp_cota_tendencia", None)
    if tendencia is not None and tendencia <= SHRINKING_BOOK_VALUE:
        flags.append(
            _entry(
                "PATRIMONIO_ENCOLHENDO",
                f"O patrimônio por cota encolheu {abs(tendencia):.1f}% em "
                f"{getattr(fii, 'meses_de_historico', 0)} meses — parte do que "
                "o fundo distribui é devolução do seu próprio capital",
            )
        )
    if _is_usable(fii.p_vp) and 0 < fii.p_vp < DISTRESS_P_VP:
        flags.append(
            _entry(
                "DESCONTO_DE_AFLICAO",
                f"Cota a {fii.p_vp:.2f}× o patrimônio, desconto de "
                f"{(1 - fii.p_vp) * 100:.0f}% — nesse tamanho o mercado costuma "
                "estar precificando perda do patrimônio, não pechincha",
            )
        )
    if _is_usable(fii.p_vp) and fii.p_vp > 1:
        flags.append(
            _entry(
                "AGIO",
                f"Cota a {fii.p_vp:.2f}× o valor patrimonial — "
                "está pagando ágio sobre o patrimônio",
            )
        )
    if _is_usable(fii.qtd_imoveis) and fii.qtd_imoveis == 1:
        flags.append(
            _entry(
                "IMOVEL_UNICO",
                "Fundo de um imóvel só — a saída de um inquilino zera a receita",
            )
        )

    return flags[:MAX_RED_FLAGS]


# ── Orquestração ─────────────────────────────────────────────────────────────


def leading_pillars(profile):
    """Os pilares que mais pesam no perfil — o que o perfil quer dizer."""
    weights = FII_PROFILES.get(profile) or FII_PROFILES[DEFAULT_FII_PROFILE]
    maior = max(weights.values())
    return {pillar for pillar, peso in weights.items() if peso == maior}


def _ranks_in_profile(pillars, profile):
    """
    Sem o pilar que define o perfil, o fundo não entra naquela vitrine.

    O `weighted_score` renormaliza os pesos quando um pilar falta. A regra
    nasceu para as ações, onde o pilar ausente é fato contábil — um banco não
    tem EBIT e não deve ser punido por isso. Num FII ela se volta contra o
    usuário: o HCTR11, com P/VP de 0,12 e por isso sem nota de valuation,
    aparecia em quarto no perfil **VALOR**, ranqueado pelos 20% de renda que
    a distribuição de capital inflava. O perfil que existe para achar barato
    não pode ranquear pelo que não conseguiu avaliar.

    Empate entre pilares (o EQUILIBRADO pesa valuation e renda em 30% cada)
    exige os dois: nenhum dos dois sozinho descreve o perfil.
    """
    return all(pillars.get(pillar) is not None for pillar in leading_pillars(profile))


def _score_row(fii, pillars, profile, exclusion_reasons, run_date):
    eligible = not exclusion_reasons
    ranked = eligible and _ranks_in_profile(pillars, profile)
    return {
        "ticker": fii.ticker,
        "profile": profile,
        "run_date": run_date,
        "score_total": (
            weighted_score(pillars, profile, FII_PROFILES, DEFAULT_FII_PROFILE)
            if ranked
            else None
        ),
        "score_valuation": pillars.get("valuation"),
        "score_renda": pillars.get("renda"),
        "score_liquidez": pillars.get("liquidez"),
        "score_estrutura": pillars.get("estrutura"),
        "eligible": eligible,
        "exclusion_reasons": json.dumps(exclusion_reasons, ensure_ascii=False),
        "reasons": json.dumps(build_reasons(fii, pillars), ensure_ascii=False),
        "red_flags": json.dumps(build_red_flags(fii), ensure_ascii=False),
    }


def _apply_pillar_requirements(fii, pillars):
    """
    Renda é o que o fundo distribui, não o que ele apura.

    Sem esta regra o pilar de renda podia sair inteiro do FFO yield, e um
    fundo com DY de 0,00% e FFO de 23,8% aparecia em segundo lugar na vitrine
    — apurando caixa e não repassando. O FFO continua no pilar: ele diz se o
    dividendo cabe no resultado. Mas sozinho não é renda.
    """
    if not _is_usable(fii.dy):
        pillars = dict(pillars)
        pillars["renda"] = None
    return pillars


def build_scores(fiis, profiles=None):
    """
    Pontua o universo inteiro em cada perfil.

    Os percentis saem uma vez só e são reaproveitados: o perfil muda os pesos,
    nunca a posição do fundo diante dos pares.
    """
    profiles = profiles or list(FII_PROFILES)
    attach_history_signals(fiis, get_history_signals([f.ticker for f in fiis]))
    percentiles = compute_metric_percentiles(fiis)
    run_date = datetime.utcnow()

    rows = []
    for fii in fiis:
        pillars = compute_pillars(percentiles.get(fii.ticker, {}), FII_PILLAR_METRICS)
        pillars = _apply_pillar_requirements(fii, pillars)
        exclusion_reasons = check_eligibility(fii)
        for profile in profiles:
            rows.append(_score_row(fii, pillars, profile, exclusion_reasons, run_date))
    return rows


def refresh_fii_scores():
    """
    Recalcula e grava o score de todo fundo e perfil.

    Chamado no fim da atualização de FIIs, pelo mesmo motivo do score de ação:
    o score não pode descrever um retrato que já não existe, e um pipeline
    separado é exatamente o que deixou a tela de oportunidades vazia.
    """
    try:
        fiis = Fii.query.all()
        if not fiis:
            return 0

        rows = build_scores(fiis)
        FiiScore.query.delete()
        db.session.bulk_insert_mappings(FiiScore, rows)
        db.session.commit()

        eligible = sum(1 for row in rows if row["eligible"]) // len(FII_PROFILES)
        logging.info(
            f"FII scores refreshed: {len(fiis)} fundos, {eligible} elegíveis, "
            f"{len(FII_PROFILES)} perfis"
        )
        return len(rows)
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred: {e}")
        return 0


# ── Leitura para a tabela ────────────────────────────────────────────────────


def get_score_map(tickers, profile):
    """{ticker: FiiScore} de um perfil, para as linhas em tela."""
    if not tickers:
        return {}

    scores = FiiScore.query.filter(
        FiiScore.ticker.in_(tickers),
        FiiScore.profile == profile,
    ).all()
    return {score.ticker: score for score in scores}


def attach_score_fields(fii_json, score):
    """Anexa o score à linha do fundo, espelhando o que a ação já faz."""
    if score is None:
        fii_json["score_total"] = None
        fii_json["score_profile"] = None
        fii_json["score_eligible"] = None
        fii_json["score_pillars"] = []
        return fii_json

    payload = score.to_json()
    fii_json["score_total"] = payload["score_total"]
    fii_json["score_profile"] = payload["profile"]
    fii_json["score_eligible"] = payload["eligible"]
    fii_json["score_pillars"] = payload["pillars"]
    return fii_json
