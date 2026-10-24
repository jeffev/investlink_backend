from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from services.cvm_fundamentals_service import (
    SOURCE_CVM,
    SOURCE_STATUSINVEST,
    apply_cvm_fundamentals,
    enrich_with_cvm,
    get_fundamentals_by_ticker,
    ticker_root,
)


def _fundamentals(**overrides):
    values = {
        "lpa_ltm": 10.35,
        "vpa": 37.39,
        "roe_ltm": 27.68,
        "roic_ltm": 17.28,
        "m_bruta_ltm": 45.0,
        "m_ebit_ltm": 33.8,
        "m_liquida_ltm": 24.4,
        "div_liq_ebit": 1.68,
        "div_liq_pl": 0.68,
        "liq_corrente": 0.85,
        "ltm_end": date(2026, 6, 30),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# ── ticker_root ──────────────────────────────────────────────────────────────


def test_ticker_root_extracts_the_issuer_code():
    assert ticker_root("PETR4") == "PETR"
    assert ticker_root("petr3") == "PETR"
    assert ticker_root("BPAT33") == "BPAT"


def test_ticker_root_accepts_a_digit_inside_the_root():
    # B3SA3 é a própria B3 — regra só de letras a perderia.
    assert ticker_root("B3SA3") == "B3SA"


def test_ticker_root_rejects_what_is_not_a_symbol():
    assert ticker_root("PETR") is None
    assert ticker_root("") is None
    assert ticker_root(None) is None


# ── apply_cvm_fundamentals ───────────────────────────────────────────────────


def test_audited_figures_replace_the_scraped_ones():
    stock_data = {"price": 40.89, "lpa": 8.35, "vpa": 34.54, "roe": 24.17}

    replaced = apply_cvm_fundamentals(stock_data, _fundamentals())

    assert replaced > 0
    assert stock_data["lpa"] == 10.35
    assert stock_data["vpa"] == 37.39
    assert stock_data["roe"] == 27.68
    assert stock_data["fundamentals_source"] == SOURCE_CVM
    assert stock_data["fundamentals_date"] == date(2026, 6, 30)


def test_price_multiples_are_recalculated_from_the_new_earnings():
    # Deixar o P/L do StatusInvest ao lado de um LPA de doze meses mostraria
    # 4,90 numa linha cujo próprio preço e LPA dão 3,95.
    stock_data = {"price": 40.89, "p_l": 4.90, "p_vp": 1.18}

    apply_cvm_fundamentals(stock_data, _fundamentals())

    assert stock_data["p_l"] == round(40.89 / 10.35, 4)
    assert stock_data["p_vp"] == round(40.89 / 37.39, 4)


def test_a_null_never_overwrites_a_value_that_exists():
    # Um banco não tem EBIT nem liquidez corrente; nulo ali é "não se aplica",
    # não "zero", e não pode apagar o que o StatusInvest trouxe.
    stock_data = {"price": 38.83, "dividaliquidaebit": 2.1, "liquidezcorrente": 1.4}

    apply_cvm_fundamentals(
        stock_data, _fundamentals(div_liq_ebit=None, liq_corrente=None)
    )

    assert stock_data["dividaliquidaebit"] == 2.1
    assert stock_data["liquidezcorrente"] == 1.4


def test_multiples_are_left_alone_without_a_usable_price():
    stock_data = {"price": 0, "p_l": 4.90}

    apply_cvm_fundamentals(stock_data, _fundamentals())

    assert stock_data["p_l"] == 4.90


def test_negative_earnings_do_not_produce_a_price_multiple():
    stock_data = {"price": 40.89, "p_l": 4.90}

    apply_cvm_fundamentals(stock_data, _fundamentals(lpa_ltm=-2.0))

    assert stock_data["p_l"] == 4.90


def test_a_ticker_without_cvm_data_is_marked_as_scraped():
    stock_data = {"price": 40.89, "lpa": 8.35}

    replaced = apply_cvm_fundamentals(stock_data, None)

    assert replaced == 0
    assert stock_data["lpa"] == 8.35
    assert stock_data["fundamentals_source"] == SOURCE_STATUSINVEST


def test_fundamentals_with_nothing_usable_are_reported_as_scraped():
    stock_data = {"price": 40.89, "lpa": 8.35}
    empty = _fundamentals(
        **{
            field: None
            for field in (
                "lpa_ltm",
                "vpa",
                "roe_ltm",
                "roic_ltm",
                "m_bruta_ltm",
                "m_ebit_ltm",
                "m_liquida_ltm",
                "div_liq_ebit",
                "div_liq_pl",
                "liq_corrente",
            )
        }
    )

    assert apply_cvm_fundamentals(stock_data, empty) == 0
    assert stock_data["fundamentals_source"] == SOURCE_STATUSINVEST


# ── get_fundamentals_by_ticker ───────────────────────────────────────────────


def _run_resolution(tickers, bridge_rows, fundamentals_rows):
    with (
        patch("services.cvm_fundamentals_service.TickerCvmMap.query") as mock_bridge,
        patch(
            "services.cvm_fundamentals_service.CvmFundamentalsLtm.query"
        ) as mock_fundamentals,
    ):
        mock_bridge.filter.return_value.all.return_value = bridge_rows
        mock_fundamentals.filter.return_value.all.return_value = fundamentals_rows
        return get_fundamentals_by_ticker(tickers)


def test_both_share_classes_resolve_to_the_same_company(app):
    with app.app_context():
        bridge = [SimpleNamespace(ticker_root="PETR", cd_cvm="9512")]
        row = SimpleNamespace(cd_cvm="9512")

        resolved = _run_resolution(["PETR3", "PETR4"], bridge, [row])

        assert resolved["PETR3"] is row
        assert resolved["PETR4"] is row


def test_unknown_ticker_is_absent_from_the_result(app):
    with app.app_context():
        bridge = [SimpleNamespace(ticker_root="PETR", cd_cvm="9512")]
        resolved = _run_resolution(
            ["PETR4", "ZZZZ4"], bridge, [SimpleNamespace(cd_cvm="9512")]
        )
        assert "ZZZZ4" not in resolved


def test_no_query_runs_without_a_valid_ticker(app):
    with app.app_context():
        assert get_fundamentals_by_ticker(["not-a-ticker", ""]) == {}


def test_empty_bridge_returns_nothing(app):
    with app.app_context():
        assert _run_resolution(["PETR4"], [], []) == {}


# ── enrich_with_cvm ──────────────────────────────────────────────────────────


def test_enrichment_reports_how_many_tickers_ran_on_audited_data(app):
    with app.app_context():
        cached = [
            {"ticker": "PETR4", "price": 40.89, "lpa": 8.35},
            {"ticker": "ZZZZ4", "price": 10.0, "lpa": 1.0},
        ]
        with patch(
            "services.cvm_fundamentals_service.get_fundamentals_by_ticker"
        ) as mock_resolve:
            mock_resolve.return_value = {"PETR4": _fundamentals()}

            assert enrich_with_cvm(cached) == 1

        assert cached[0]["fundamentals_source"] == SOURCE_CVM
        assert cached[1]["fundamentals_source"] == SOURCE_STATUSINVEST
        assert cached[1]["lpa"] == 1.0


def test_enrichment_keeps_the_scraped_snapshot_when_the_pipeline_is_empty(app):
    with app.app_context():
        cached = [{"ticker": "PETR4", "price": 40.89, "lpa": 8.35}]
        with patch(
            "services.cvm_fundamentals_service.get_fundamentals_by_ticker"
        ) as mock_resolve:
            mock_resolve.return_value = {}

            assert enrich_with_cvm(cached) == 0

        assert cached[0]["lpa"] == 8.35
        assert cached[0]["fundamentals_source"] == SOURCE_STATUSINVEST


def test_enrichment_never_breaks_the_refresh(app):
    # O snapshot do StatusInvest tem de ser entregue mesmo assim: o dado
    # auditado é uma melhoria sobre ele, não uma pré-condição.
    with app.app_context():
        cached = [{"ticker": "PETR4", "price": 40.89, "lpa": 8.35}]
        with patch(
            "services.cvm_fundamentals_service.get_fundamentals_by_ticker"
        ) as mock_resolve:
            mock_resolve.side_effect = Exception("banco fora do ar")

            assert enrich_with_cvm(cached) == 0

        assert cached[0]["lpa"] == 8.35


# ── Trava de plausibilidade do número auditado ───────────────────────────────
#
# A quantidade de ações em circulação vem errada da CVM para algumas empresas:
# o Santander aparece com 7,4 **milhões** de ações em vez de 7,4 bilhões. O LPA
# sai mil vezes maior, o P/L mil vezes menor, e a empresa vira "a mais barata
# do setor" — com o selo de auditada, que é o que torna o erro perigoso.


class _FundamentoFalso:
    def __init__(self, lpa_ltm=None, vpa=None, ltm_end=None):
        self.lpa_ltm = lpa_ltm
        self.vpa = vpa
        self.ltm_end = ltm_end
        for campo in (
            "roe_ltm",
            "roic_ltm",
            "m_bruta_ltm",
            "m_ebit_ltm",
            "m_liquida_ltm",
            "div_liq_ebit",
            "div_liq_pl",
            "liq_corrente",
        ):
            setattr(self, campo, None)


def test_escala_errada_de_acoes_nao_sobrescreve_o_publicado():
    # Caso real do SANB11: preço 27,53 e P/L publicado 6,66; com o LPA da CVM
    # o P/L sairia 0,015.
    stock = {"ticker": "SANB11", "price": 27.53, "p_l": 6.66, "p_vp": 1.05}

    trocados = apply_cvm_fundamentals(
        stock, _FundamentoFalso(lpa_ltm=1848.53, vpa=17241.08)
    )

    assert trocados == 0
    assert stock["p_l"] == 6.66
    assert stock["p_vp"] == 1.05
    assert stock["fundamentals_source"] != "CVM"


def test_divergencia_normal_continua_prevalecendo_a_cvm():
    # A CVM substituir a fonte pública é o objetivo; discordar por 30% é o
    # esperado entre LTM e exercício fechado.
    stock = {"ticker": "PETR4", "price": 58.68, "p_l": 7.40, "p_vp": 1.32}

    trocados = apply_cvm_fundamentals(stock, _FundamentoFalso(lpa_ltm=10.35, vpa=37.39))

    assert trocados > 0
    assert stock["p_l"] == round(58.68 / 10.35, 4)
    assert stock["fundamentals_source"] == "CVM"


def test_sem_multiplo_publicado_a_trava_nao_bloqueia():
    # Papel novo chega sem referência; bloquear aqui seria descartar o
    # auditado por falta do não auditado.
    stock = {"ticker": "NOVO3", "price": 10.0, "p_l": 0.0, "p_vp": 0.0}

    trocados = apply_cvm_fundamentals(stock, _FundamentoFalso(lpa_ltm=2.0, vpa=5.0))

    assert trocados > 0
    assert stock["p_l"] == 5.0
