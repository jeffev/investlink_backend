from types import SimpleNamespace
from unittest.mock import patch

from services.scoring_service import (
    DEFAULT_PROFILE,
    IMPLAUSIBLE_DIVIDEND_YIELD,
    MAX_NET_DEBT_TO_EBIT,
    MIN_DAILY_LIQUIDITY,
    PROFILES,
    build_reasons,
    build_red_flags,
    build_scores,
    check_eligibility,
    compute_metric_percentiles,
    compute_pillars,
    percentile_ranks,
    scoring_value,
    weighted_score,
)


def _stock(ticker="PETR4", **overrides):
    values = {
        "ticker": ticker,
        "sectorname": "Petróleo",
        "liquidezmediadiaria": 50_000_000.0,
        "vpa": 37.39,
        "lpa": 10.35,
        "p_l": 4.67,
        "p_vp": 1.29,
        "ev_ebit": 3.2,
        "roic": 17.28,
        "roe": 27.68,
        "margemliquida": 24.4,
        "margembruta": 45.0,
        "dividaliquidaebit": 1.68,
        "liquidezcorrente": 1.2,
        "receitas_cagr5": 12.83,
        "lucros_cagr5": 79.75,
        "dy": 8.0,
        "fundamentals_source": "CVM",
        "active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# ── Guard rails ──────────────────────────────────────────────────────────────


def test_a_healthy_company_passes_every_guard_rail():
    assert check_eligibility(_stock(), {"PETR": 5}) == []


def test_illiquid_company_is_excluded():
    reasons = check_eligibility(
        _stock(liquidezmediadiaria=MIN_DAILY_LIQUIDITY - 1), {"PETR": 5}
    )
    assert [reason["code"] for reason in reasons] == ["LIQUIDEZ_BAIXA"]


def test_unknown_liquidity_is_treated_as_illiquid():
    # Não dá para afirmar que o investidor consegue sair de uma posição cuja
    # negociação não se conhece.
    reasons = check_eligibility(_stock(liquidezmediadiaria=None), {"PETR": 5})
    assert [reason["code"] for reason in reasons] == ["LIQUIDEZ_BAIXA"]


def test_negative_equity_is_excluded():
    reasons = check_eligibility(_stock(vpa=-2.0), {"PETR": 5})
    assert "PATRIMONIO_NEGATIVO" in [reason["code"] for reason in reasons]


def test_inconsistent_profit_history_is_excluded():
    reasons = check_eligibility(_stock(), {"PETR": 2})
    assert "LUCRO_INCONSISTENTE" in [reason["code"] for reason in reasons]


def test_missing_profit_history_does_not_exclude():
    # Ausência de histórico é dado faltando, não prejuízo comprovado.
    assert check_eligibility(_stock(), {}) == []


def test_high_leverage_is_excluded():
    reasons = check_eligibility(
        _stock(dividaliquidaebit=MAX_NET_DEBT_TO_EBIT + 0.1), {"PETR": 5}
    )
    assert "ALAVANCAGEM_ALTA" in [reason["code"] for reason in reasons]


def test_every_exclusion_reason_carries_a_stable_code():
    reasons = check_eligibility(
        _stock(liquidezmediadiaria=0, vpa=-1, dividaliquidaebit=9), {"PETR": 1}
    )
    assert len(reasons) == 4
    assert all(reason["code"] and reason["message"] for reason in reasons)


# ── Percentis ────────────────────────────────────────────────────────────────


def test_percentile_puts_the_best_at_one_hundred():
    ranks = percentile_ranks({"A": 10, "B": 20, "C": 30}, lower_is_better=False)
    assert ranks["C"] == 100.0
    assert ranks["A"] == 0.0


def test_percentile_inverts_when_lower_is_better():
    ranks = percentile_ranks({"A": 10, "B": 20, "C": 30}, lower_is_better=True)
    assert ranks["A"] == 100.0
    assert ranks["C"] == 0.0


def test_a_lone_company_is_average_not_best():
    assert percentile_ranks({"A": 10}, lower_is_better=False) == {"A": 50.0}


def test_percentile_of_nothing_is_nothing():
    assert percentile_ranks({}, lower_is_better=False) == {}


def test_ranking_happens_inside_the_sector():
    # O P/L 12 da elétrica não pode competir com o P/L 12 da empresa de software.
    stocks = [
        _stock("ELET3", sectorname="Utilidade", p_l=12),
        _stock("ELET6", sectorname="Utilidade", p_l=20),
        _stock("CMIG4", sectorname="Utilidade", p_l=25),
        _stock("EGIE3", sectorname="Utilidade", p_l=30),
        _stock("TAEE4", sectorname="Utilidade", p_l=35),
        _stock("TOTS3", sectorname="Tecnologia", p_l=12),
        _stock("LWSA3", sectorname="Tecnologia", p_l=8),
        _stock("CASH3", sectorname="Tecnologia", p_l=6),
        _stock("INTB3", sectorname="Tecnologia", p_l=5),
        _stock("POSI3", sectorname="Tecnologia", p_l=4),
    ]
    percentiles = compute_metric_percentiles(stocks)
    # Mesmo P/L, percentis opostos: barato na elétrica, caro na tecnologia.
    assert percentiles["ELET3"]["p_l"] == 100.0
    assert percentiles["TOTS3"]["p_l"] == 0.0


def test_a_missing_metric_is_absent_rather_than_worst():
    stocks = [_stock(f"AAA{i}", p_l=None if i == 0 else i + 1) for i in range(6)]
    percentiles = compute_metric_percentiles(stocks)
    assert "p_l" not in percentiles["AAA0"]


def test_a_zero_metric_counts_as_missing():
    # O StatusInvest devolve indicador ausente como 0.0.
    stocks = [_stock(f"AAA{i}", roic=0 if i == 0 else i + 1) for i in range(6)]
    percentiles = compute_metric_percentiles(stocks)
    assert "roic" not in percentiles["AAA0"]


# ── Pilares e score ──────────────────────────────────────────────────────────


def test_a_pillar_averages_the_metrics_it_has():
    pillars = compute_pillars({"p_l": 80.0, "p_vp": 60.0, "roic": 100.0})
    assert pillars["valuation"] == 70.0
    assert pillars["qualidade"] == 100.0


def test_a_pillar_without_data_is_none_not_zero():
    assert compute_pillars({})["valuation"] is None


def test_score_renormalizes_around_a_missing_pillar():
    # Um banco não tem alavancagem sobre EBIT; zerar a saúde financeira o
    # expulsaria da lista por um fato contábil.
    complete = weighted_score(
        {
            "valuation": 80.0,
            "qualidade": 80.0,
            "saude": 80.0,
            "crescimento": 80.0,
            "dividendos": 80.0,
        },
        DEFAULT_PROFILE,
    )
    without_health = weighted_score(
        {
            "valuation": 80.0,
            "qualidade": 80.0,
            "saude": None,
            "crescimento": 80.0,
            "dividendos": 80.0,
        },
        DEFAULT_PROFILE,
    )
    assert complete == 80.0
    assert without_health == 80.0


def test_score_is_none_when_no_pillar_survives():
    assert (
        weighted_score({key: None for key in PROFILES[DEFAULT_PROFILE]}, "VALOR")
        is None
    )


def test_profiles_shift_the_ranking_not_the_percentiles():
    pillars = {
        "valuation": 90.0,
        "qualidade": 40.0,
        "saude": 40.0,
        "crescimento": 40.0,
        "dividendos": 40.0,
    }
    assert weighted_score(pillars, "VALOR") > weighted_score(pillars, "CRESCIMENTO")


def test_every_profile_weights_sum_to_one():
    for profile, weights in PROFILES.items():
        assert round(sum(weights.values()), 6) == 1.0, profile


def test_an_unknown_profile_falls_back_to_the_default():
    pillars = {
        "valuation": 80.0,
        "qualidade": None,
        "saude": None,
        "crescimento": None,
        "dividendos": None,
    }
    assert weighted_score(pillars, "INEXISTENTE") == 80.0


# ── DY implausível ───────────────────────────────────────────────────────────


def test_an_implausible_dividend_yield_is_capped_for_scoring():
    # O alerta diz que 34% não se repete; o pilar não pode premiá-lo como se
    # fosse quatro vezes melhor que um DY sólido de 8%.
    assert scoring_value(_stock(dy=34.4), "dy") == IMPLAUSIBLE_DIVIDEND_YIELD
    assert scoring_value(_stock(dy=8.0), "dy") == 8.0


def test_capping_only_applies_to_the_dividend_yield():
    assert scoring_value(_stock(roic=90.0), "roic") == 90.0


# ── Motivos e alertas ────────────────────────────────────────────────────────


def test_reasons_lead_with_the_strongest_pillar():
    reasons = build_reasons(
        _stock(),
        {
            "valuation": 61.0,
            "qualidade": 92.0,
            "saude": 40.0,
            "crescimento": 89.0,
            "dividendos": None,
        },
    )
    assert reasons[0]["code"] == "PILAR_QUALIDADE"
    assert reasons[1]["code"] == "PILAR_CRESCIMENTO"


def test_an_average_pillar_is_not_a_reason():
    reasons = build_reasons(
        _stock(roic=0, dy=0),
        {
            "valuation": 50.0,
            "qualidade": 55.0,
            "saude": 50.0,
            "crescimento": 50.0,
            "dividendos": 50.0,
        },
    )
    assert reasons == []


def test_red_flags_name_what_could_go_wrong():
    flags = build_red_flags(_stock(lpa=-1.0, margemliquida=-5.0))
    codes = [flag["code"] for flag in flags]
    assert "PREJUIZO" in codes
    assert "MARGEM_NEGATIVA" in codes


def test_stale_fundamentals_are_flagged():
    flags = build_red_flags(_stock(fundamentals_source="STATUSINVEST"))
    assert "FUNDAMENTO_DEFASADO" in [flag["code"] for flag in flags]


def test_audited_fundamentals_raise_no_flag():
    flags = build_red_flags(_stock())
    assert "FUNDAMENTO_DEFASADO" not in [flag["code"] for flag in flags]


def test_an_implausible_yield_is_flagged_even_though_it_scores_well():
    flags = build_red_flags(_stock(dy=34.4))
    assert "DY_IMPLAUSIVEL" in [flag["code"] for flag in flags]


# ── build_scores ─────────────────────────────────────────────────────────────


def test_every_ticker_gets_a_row_for_every_profile(app):
    with app.app_context():
        stocks = [_stock(f"AAA{i}") for i in range(6)]
        with patch("services.scoring_service.get_profitable_years") as mock_years:
            mock_years.return_value = {"AAA0": 5}

            rows = build_scores(stocks)

        assert len(rows) == len(stocks) * len(PROFILES)


def test_an_ineligible_company_is_stored_with_its_reason(app):
    with app.app_context():
        stocks = [_stock("AAA1", liquidezmediadiaria=0)]
        with patch("services.scoring_service.get_profitable_years") as mock_years:
            mock_years.return_value = {}

            rows = build_scores(stocks, profiles=[DEFAULT_PROFILE])

        assert rows[0]["eligible"] is False
        assert rows[0]["score_total"] is None
        assert "LIQUIDEZ_BAIXA" in rows[0]["exclusion_reasons"]


# ── Leitura para a tabela (K5) ───────────────────────────────────────────────


def test_score_fields_are_attached_flat_for_the_table(app):
    from types import SimpleNamespace as NS

    from services.scoring_service import attach_score_fields

    score = NS(
        to_json=lambda: {
            "score_total": 64.9,
            "profile": "EQUILIBRADO",
            "eligible": True,
            "pillars": [{"key": "valuation", "label": "Valuation", "value": 46.0}],
        }
    )
    with app.app_context():
        row = attach_score_fields({"ticker": "POMO4"}, score)

    # Chaves planas: a tabela ordena e renderiza por accessor de coluna.
    assert row["score_total"] == 64.9
    assert row["score_profile"] == "EQUILIBRADO"
    assert row["score_eligible"] is True
    assert row["score_pillars"][0]["key"] == "valuation"


def test_a_stock_without_a_score_still_gets_the_keys(app):
    from services.scoring_service import attach_score_fields

    with app.app_context():
        row = attach_score_fields({"ticker": "ZZZZ4"}, None)

    assert row["score_total"] is None
    assert row["score_pillars"] == []


def test_no_query_runs_for_an_empty_page(app):
    from services.scoring_service import get_score_map

    with app.app_context():
        assert get_score_map([], "EQUILIBRADO") == {}


# ── Deslistagem (E6) ─────────────────────────────────────────────────────────


def test_a_delisted_company_is_excluded():
    reasons = check_eligibility(_stock(active=False), {"PETR": 5})
    assert "DESLISTADA" in [reason["code"] for reason in reasons]


def test_an_active_company_raises_no_delisting_reason():
    reasons = check_eligibility(_stock(active=True), {"PETR": 5})
    assert "DESLISTADA" not in [reason["code"] for reason in reasons]


def test_unknown_listing_status_does_not_exclude():
    # Ausência de informação não é prova de deslistagem.
    stock = _stock()
    del stock.active
    stock.active = None
    assert "DESLISTADA" not in [
        reason["code"] for reason in check_eligibility(stock, {"PETR": 5})
    ]
