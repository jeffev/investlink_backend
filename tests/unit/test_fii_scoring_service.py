"""
O score de FII, testado nos pontos em que ele difere do score de ação.

Os valores do fundo-base saem da tabela real do Fundamentus (HGLG11), e os
limiares testados são os medidos sobre os 570 fundos publicados — não números
redondos escolhidos para o teste passar.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.fii_scoring_service import (
    CHEAP_P_VP,
    DEFAULT_FII_PROFILE,
    FII_PROFILES,
    HIGH_VACANCY,
    IMPLAUSIBLE_DIVIDEND_YIELD,
    MAX_PLAUSIBLE_P_VP,
    MIN_DAILY_LIQUIDITY,
    build_reasons,
    build_red_flags,
    FII_PILLAR_METRICS,
    DISTRESS_P_VP,
    MIN_HISTORY_MONTHS,
    attach_history_signals,
    build_scores,
    check_eligibility,
    compute_metric_percentiles,
    get_history_signals,
    scoring_value,
)


def _fii(ticker="HGLG11", **overrides):
    values = {
        "ticker": ticker,
        "companyname": ticker,
        "segment": "Logística",
        "price": 147.60,
        "p_vp": 0.89,
        "dy": 8.97,
        "ffo_yield": 7.55,
        "cap_rate": 9.16,
        "vacancia_media": 2.41,
        "qtd_imoveis": 37,
        "liquidezmediadiaria": 22_213_500.0,
        "patrimonio": 7_559_573_034.0,
        "dividend_cagr": 3.0,
        "cota_cagr": 2.0,
        "numerocotistas": 300_000.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# ── Guard rails ──────────────────────────────────────────────────────────────


def test_um_fundo_saudavel_passa_por_todos_os_guard_rails():
    assert check_eligibility(_fii()) == []


def test_fundo_ilíquido_fica_de_fora():
    # A mediana de liquidez do universo é R$ 15 mil/dia: sem este corte a
    # vitrine recomendaria fundo que ninguém consegue vender.
    reasons = check_eligibility(_fii(liquidezmediadiaria=MIN_DAILY_LIQUIDITY - 1))
    assert [reason["code"] for reason in reasons] == ["LIQUIDEZ_BAIXA"]


def test_o_corte_de_liquidez_do_fii_e_mais_permissivo_que_o_da_acao():
    # FII é mercado menor; aplicar o piso de R$ 1 milhão das ações deixaria
    # 94 dos 570 fundos e transformaria a vitrine em lista de cinco nomes.
    from services.scoring_service import MIN_DAILY_LIQUIDITY as ACAO_MINIMO

    assert MIN_DAILY_LIQUIDITY < ACAO_MINIMO
    assert check_eligibility(_fii(liquidezmediadiaria=300_000.0)) == []


def test_p_vp_absurdo_e_tratado_como_erro_de_dado():
    # Existe fundo na tabela com P/VP na casa dos milhares. Isso não é
    # oportunidade histórica, é dado quebrado.
    reasons = check_eligibility(_fii(p_vp=MAX_PLAUSIBLE_P_VP + 1))
    assert [reason["code"] for reason in reasons] == ["DADO_INCONSISTENTE"]


def test_fundo_sem_p_vp_nao_e_ranqueado():
    reasons = check_eligibility(_fii(p_vp=0.0))
    assert [reason["code"] for reason in reasons] == ["SEM_P_VP"]


def test_fundo_sem_cotacao_fica_de_fora():
    reasons = check_eligibility(_fii(price=0.0))
    assert "SEM_PRECO" in [reason["code"] for reason in reasons]


# ── Valor usado no score ─────────────────────────────────────────────────────


def test_dy_implausivel_e_aparado_antes_de_pontuar():
    # Existe fundo com DY publicado de 129% — amortização de cota contada como
    # rendimento. Sem o corte ele venceria qualquer fundo sustentável.
    assert scoring_value(_fii(dy=129.9), "dy") == IMPLAUSIBLE_DIVIDEND_YIELD


def test_dy_normal_passa_intacto():
    assert scoring_value(_fii(dy=8.97), "dy") == 8.97


# ── Percentis dentro do segmento ─────────────────────────────────────────────


def test_o_ranking_acontece_dentro_do_segmento():
    # P/VP de 0,85 é barato em tijolo e rotineiro em papel, que marca os CRI a
    # mercado. Ranquear junto devolveria só fundos de papel.
    tijolo = [
        _fii(f"TIJO{i}1", segment="Logística", p_vp=0.70 + i * 0.05) for i in range(5)
    ]
    papel = [
        _fii(f"PAPE{i}1", segment="Papel", p_vp=0.98 + i * 0.005) for i in range(5)
    ]

    percentiles = compute_metric_percentiles(tijolo + papel)

    # O mais barato de cada segmento é o melhor do seu próprio segmento,
    # mesmo que em termos absolutos o de papel seja mais caro que todos os de
    # tijolo.
    assert percentiles["TIJO01"]["p_vp"] == 100.0
    assert percentiles["PAPE01"]["p_vp"] == 100.0


def test_segmento_pequeno_cai_no_balde_de_mercado():
    # Hotelaria e Agro têm poucos fundos listados: com dois ou três, a mediana
    # do segmento é ruído. Eles competem entre si no balde de mercado, não
    # contra a Logística inteira.
    hotel = _fii("HOTE11", segment="Hotelaria", p_vp=0.50)
    agro = _fii("AGRO11", segment="Agro", p_vp=1.10)
    logistica = [_fii(f"LOGI{i}1", segment="Logística") for i in range(5)]

    percentiles = compute_metric_percentiles([hotel, agro] + logistica)

    assert percentiles["HOTE11"]["p_vp"] == 100.0
    assert percentiles["AGRO11"]["p_vp"] == 0.0


def test_metrica_ausente_nao_compete_como_se_fosse_zero():
    fundos = [_fii(f"FUND{i}1", ffo_yield=0.0) for i in range(5)]
    percentiles = compute_metric_percentiles(fundos)
    assert all("ffo_yield" not in percentiles[f.ticker] for f in fundos)


# ── Motivos e alertas ────────────────────────────────────────────────────────


def test_desconto_sobre_o_patrimonio_vira_motivo():
    reasons = build_reasons(_fii(p_vp=CHEAP_P_VP - 0.1), {})
    codes = [reason["code"] for reason in reasons]
    assert "P_VP_DESCONTO" in codes


def test_agio_vira_alerta():
    flags = build_red_flags(_fii(p_vp=1.30))
    assert "AGIO" in [flag["code"] for flag in flags]


def test_vacancia_alta_vira_alerta_em_fundo_de_tijolo():
    flags = build_red_flags(_fii(vacancia_media=HIGH_VACANCY + 5, qtd_imoveis=10))
    assert "VACANCIA_ALTA" in [flag["code"] for flag in flags]


def test_vacancia_de_fundo_de_papel_nao_vira_alerta():
    # Num fundo sem imóvel a vacância é zero por não existir imóvel. Nem
    # elogio nem alerta: a métrica não se aplica.
    flags = build_red_flags(_fii(qtd_imoveis=0, vacancia_media=0.0))
    assert "VACANCIA_ALTA" not in [flag["code"] for flag in flags]


def test_fundo_mono_imovel_e_sinalizado():
    flags = build_red_flags(_fii(qtd_imoveis=1))
    assert "IMOVEL_UNICO" in [flag["code"] for flag in flags]


def test_dy_implausivel_aparece_como_alerta_e_nao_como_motivo():
    fundo = _fii(dy=25.0)
    assert "DY_IMPLAUSIVEL" in [flag["code"] for flag in build_red_flags(fundo)]
    assert "DY_SAUDAVEL" not in [reason["code"] for reason in build_reasons(fundo, {})]


# ── Perfis ───────────────────────────────────────────────────────────────────


def test_os_pesos_de_cada_perfil_somam_um():
    for profile, weights in FII_PROFILES.items():
        assert round(sum(weights.values()), 6) == 1.0, profile


def test_o_perfil_renda_privilegia_o_pilar_de_renda():
    assert FII_PROFILES["RENDA"]["renda"] > FII_PROFILES["EQUILIBRADO"]["renda"]
    assert FII_PROFILES["VALOR"]["valuation"] > FII_PROFILES["EQUILIBRADO"]["valuation"]


def test_o_perfil_padrao_existe_na_tabela_de_perfis():
    assert DEFAULT_FII_PROFILE in FII_PROFILES


# ── Orquestração ─────────────────────────────────────────────────────────────


def _build_scores(fiis, medians=None, sinais=None):
    """build_scores consulta o histórico no banco; aqui ele é fornecido."""
    sinais = sinais or {
        ticker: {"p_vp_mediano": mediana, "vp_tendencia": 0.0, "meses": 24}
        for ticker, mediana in (medians or {}).items()
    }
    with patch("services.fii_scoring_service.get_history_signals", return_value=sinais):
        return build_scores(fiis)


def test_build_scores_gera_uma_linha_por_fundo_e_perfil():
    fundos = [_fii(f"FUND{i}1") for i in range(3)]
    rows = _build_scores(fundos)
    assert len(rows) == 3 * len(FII_PROFILES)


def test_fundo_inelegivel_nao_recebe_nota_final():
    rows = _build_scores([_fii(liquidezmediadiaria=0.0)])
    assert all(row["score_total"] is None for row in rows)
    assert all(row["eligible"] is False for row in rows)


def test_fundo_elegivel_recebe_nota_final():
    fundos = [_fii(f"FUND{i}1", p_vp=0.7 + i * 0.05) for i in range(5)]
    rows = _build_scores(fundos)
    assert all(row["score_total"] is not None for row in rows)


def test_o_motivo_da_exclusao_viaja_junto_com_a_linha():
    # Uma lista que apenas omite o fundo não responde "por que XPML11 não
    # aparece aqui?", que é a pergunta que o investidor realmente faz.
    rows = _build_scores([_fii(liquidezmediadiaria=0.0)])
    assert "LIQUIDEZ_BAIXA" in rows[0]["exclusion_reasons"]


# ── Barato para ele mesmo ────────────────────────────────────────────────────


def _sinais(mediana=None, tendencia=None, meses=24):
    return {"p_vp_mediano": mediana, "vp_tendencia": tendencia, "meses": meses}


def test_a_razao_com_o_proprio_historico_e_calculada():
    fundos = [_fii("HGLG11", p_vp=0.80)]
    attach_history_signals(fundos, {"HGLG11": _sinais(mediana=1.00)})

    # Negociando a 80% do P/VP que costuma ter.
    assert fundos[0].p_vp_vs_historico == 0.8


def test_fundo_sem_historico_nao_recebe_a_razao():
    # Recém-listado não tem "próprio histórico"; puni-lo por isso seria
    # confundir dado faltando com fundo caro.
    fundos = [_fii("NOVO11")]
    attach_history_signals(fundos, {})

    assert fundos[0].p_vp_vs_historico is None


def test_o_desconto_historico_conta_no_pilar_de_valuation():
    # Dois fundos com o mesmo P/VP absoluto: vence o que está mais barato
    # frente ao próprio passado.
    caro_para_si = _fii("CARO11", p_vp=0.90)
    barato_para_si = _fii("BARA11", p_vp=0.90)
    outros = [_fii(f"FUND{i}1", p_vp=0.90) for i in range(4)]
    fundos = [caro_para_si, barato_para_si] + outros

    attach_history_signals(
        fundos,
        {"CARO11": _sinais(mediana=0.60), "BARA11": _sinais(mediana=1.40)},
    )
    percentiles = compute_metric_percentiles(fundos)

    assert (
        percentiles["BARA11"]["p_vp_vs_historico"]
        > percentiles["CARO11"]["p_vp_vs_historico"]
    )


def test_a_razao_entra_na_definicao_do_pilar_de_valuation():
    metricas = [metric for metric, _ in FII_PILLAR_METRICS["valuation"]]
    assert metricas == ["p_vp", "p_vp_vs_historico"]


def _historico(p_vps):
    """Executa get_history_signals sobre uma série de P/VP."""
    from datetime import date as _date

    linhas = [("HGLG11", _date(2025, 1, 1), p_vp, 100.0 * p_vp) for p_vp in p_vps]
    with patch("services.fii_scoring_service.db") as mock_db:
        chain = MagicMock()
        chain.filter.return_value.order_by.return_value.all.return_value = linhas
        mock_db.session.query.return_value = chain
        sinais = get_history_signals(["HGLG11"])
    return {ticker: sinal["p_vp_mediano"] for ticker, sinal in sinais.items()}


def test_a_mediana_ignora_o_mes_atipico():
    # Mediana e não média: uma emissão de cotas ou um mês de marcação
    # esquisita desloca a média e deixa a mediana onde está.
    series = [0.90] * (MIN_HISTORY_MONTHS - 1) + [5.0]
    assert _historico(series)["HGLG11"] == 0.90


def test_fundo_com_janela_curta_fica_de_fora():
    assert _historico([0.90] * (MIN_HISTORY_MONTHS - 1)) == {}


def test_p_vp_historico_absurdo_e_descartado():
    # O mesmo dado quebrado que exclui o fundo hoje não pode entrar na
    # mediana de ontem.
    series = [0.90] * MIN_HISTORY_MONTHS + [9000.0] * 20
    assert _historico(series)["HGLG11"] == 0.90


def test_sem_tickers_nao_consulta_o_banco():
    with patch("services.fii_scoring_service.db") as mock_db:
        assert get_history_signals([]) == {}
        mock_db.session.query.assert_not_called()


# ── Separar fundo barato de fundo quebrado ───────────────────────────────────
#
# Rodar o score contra o mercado real, pela primeira vez, devolveu os quatro
# fundos de crédito mais descontados da bolsa nos três perfis. Todos os pilares
# premiavam aflição ao mesmo tempo: P/VP baixo, DY alto e FFO alto são o perfil
# de um fundo quebrado tanto quanto o de uma pechincha.


def test_desconto_de_aflicao_nao_pontua_valuation():
    # Nem aparado nem premiado: sem valor. Aparar empatava o fundo a 0,18×
    # com o melhor da faixa saudável, que é o que os mantinha no topo.
    assert scoring_value(_fii(p_vp=0.12), "p_vp") is None
    assert scoring_value(_fii(p_vp=DISTRESS_P_VP + 0.01), "p_vp") is not None


def test_desconto_de_aflicao_vira_alerta():
    flags = build_red_flags(_fii(p_vp=0.12))
    assert "DESCONTO_DE_AFLICAO" in [flag["code"] for flag in flags]


def test_o_fundo_em_aflicao_continua_na_lista_ranqueado_pelo_resto():
    # Esconder o ativo seria esconder a pergunta; o projeto mostra o motivo.
    fundos = [_fii(f"FUN{i}11") for i in range(4)] + [_fii("AFLI11", p_vp=0.12)]
    percentis = compute_metric_percentiles(fundos)

    assert "p_vp" not in percentis["AFLI11"]
    assert "dy" in percentis["AFLI11"]


def test_fundo_sem_rendimento_declarado_nao_e_ranqueado():
    # FII existe para distribuir. Sem DY o pilar de renda fica vazio, o
    # `weighted_score` renormaliza em cima dos outros três e um fundo que não
    # distribui nada liderava o perfil equilibrado.
    reasons = check_eligibility(_fii(dy=0.0))
    assert "SEM_RENDIMENTO" in [reason["code"] for reason in reasons]


def test_o_pilar_de_renda_exige_o_que_o_fundo_distribui():
    # O FFO diz se o dividendo cabe no resultado; sozinho não é renda.
    from services.fii_scoring_service import _apply_pillar_requirements

    pilares = _apply_pillar_requirements(
        _fii(dy=0.0, ffo_yield=23.8), {"renda": 95.0, "valuation": 50.0}
    )
    assert pilares["renda"] is None
    assert pilares["valuation"] == 50.0


def test_patrimonio_encolhendo_vira_alerta():
    fundo = _fii()
    fundo.vp_cota_tendencia = -12.1
    fundo.meses_de_historico = 32

    flags = build_red_flags(fundo)
    alerta = next(f for f in flags if f["code"] == "PATRIMONIO_ENCOLHENDO")
    assert "12.1%" in alerta["message"]
    assert "32 meses" in alerta["message"]


def test_patrimonio_estavel_nao_vira_alerta():
    fundo = _fii()
    fundo.vp_cota_tendencia = -1.0
    assert "PATRIMONIO_ENCOLHENDO" not in [f["code"] for f in build_red_flags(fundo)]


def test_a_tendencia_do_patrimonio_e_ajustada_por_desdobramento():
    # A coluna `valor_patrimonial_cota` da CVM não é ajustada: num fundo que
    # desdobrou 1:10 a série cai 90% de um mês para o outro, e o ALZR11
    # aparecia com -89,9% de "erosão" que era só o desdobramento. A razão
    # `close_price / p_vp` é consistente entre as duas bases por construção.
    from datetime import date as _date

    linhas = [
        # Mesmo P/VP e preço na base de hoje; só o patrimônio declarado muda
        # de escala, como acontece num desdobramento.
        ("ALZR11", _date(2025, m, 1), 1.0, 10.0)
        for m in range(1, 13)
    ] * 2

    with patch("services.fii_scoring_service.db") as mock_db:
        chain = MagicMock()
        chain.filter.return_value.order_by.return_value.all.return_value = linhas
        mock_db.session.query.return_value = chain
        sinais = get_history_signals(["ALZR11"])

    assert sinais["ALZR11"]["vp_tendencia"] == 0.0


# ── O perfil precisa do pilar que o define ───────────────────────────────────


def test_o_pilar_que_define_cada_perfil():
    from services.fii_scoring_service import leading_pillars

    assert leading_pillars("VALOR") == {"valuation"}
    assert leading_pillars("RENDA") == {"renda"}
    # No equilibrado, valuation e renda pesam 30% cada: nenhum sozinho
    # descreve o perfil, então os dois são exigidos.
    assert leading_pillars("EQUILIBRADO") == {"valuation", "renda"}


def test_sem_nota_de_valuation_o_fundo_nao_entra_na_vitrine_de_valor():
    # O `weighted_score` renormaliza os pesos quando um pilar falta — regra
    # que nasceu para o banco sem EBIT. Num FII ela punha o HCTR11, com P/VP
    # de 0,12 e por isso sem valuation, em quarto no perfil VALOR, ranqueado
    # pelos 20% de renda que a devolução de capital inflava.
    from services.fii_scoring_service import _ranks_in_profile

    pilares = {"valuation": None, "renda": 95.0, "liquidez": 80.0, "estrutura": 40.0}

    assert _ranks_in_profile(pilares, "VALOR") is False
    assert _ranks_in_profile(pilares, "EQUILIBRADO") is False
    assert _ranks_in_profile(pilares, "RENDA") is True


def test_a_comparacao_com_o_proprio_historico_respeita_a_faixa_de_aflicao():
    # Sem isto o fundo perdia a nota pelo P/VP absoluto e a recuperava pela
    # comparação com o próprio passado — que é ainda mais favorável
    # justamente porque ele está desabando.
    fundos = [_fii("AFLI11", p_vp=0.12), _fii("SADI11", p_vp=0.80)]
    attach_history_signals(
        fundos,
        {
            "AFLI11": _sinais(mediana=0.60),
            "SADI11": _sinais(mediana=1.00),
        },
    )

    assert fundos[0].p_vp_vs_historico is None
    assert fundos[1].p_vp_vs_historico == 0.8


def test_o_fundo_em_aflicao_ainda_responde_por_que_nao_esta_na_lista():
    # Não ranqueado não é escondido: a linha existe, elegível, com os alertas.
    fundo = _fii("AFLI11", p_vp=0.12)
    rows = _build_scores(
        [fundo] + [_fii(f"FUN{i}11") for i in range(4)],
        sinais={"AFLI11": _sinais(mediana=0.60, tendencia=-7.2, meses=32)},
    )

    linha = next(r for r in rows if r["ticker"] == "AFLI11" and r["profile"] == "VALOR")
    assert linha["score_total"] is None
    assert linha["eligible"] is True
    assert "DESCONTO_DE_AFLICAO" in linha["red_flags"]
    assert "PATRIMONIO_ENCOLHENDO" in linha["red_flags"]
