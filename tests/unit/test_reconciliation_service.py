from types import SimpleNamespace
from unittest.mock import patch

from services.reconciliation_service import (
    DIVERGENCE_THRESHOLD_PERCENT,
    MIN_COMPARABLE_VALUE,
    _build_report,
    _compare_ticker,
    _divergence_percent,
    reconcile_fundamentals,
)


def _cvm(lpa=10.0, vpa=30.0, roe=20.0):
    return {"lpa": lpa, "vpa": vpa, "roe": roe}


def _statusinvest(ticker="PETR4", lpa=10.0, vpa=30.0, roe=20.0):
    return {"ticker": ticker, "lpa": lpa, "vpa": vpa, "roe": roe}


# ── Divergência ──────────────────────────────────────────────────────────────


def test_divergence_is_measured_against_the_audited_figure():
    # A pergunta é quanto o StatusInvest se afasta do que foi entregue à CVM.
    assert _divergence_percent(10.0, 11.0) == 10.0
    assert _divergence_percent(10.0, 9.0) == -10.0


def test_divergence_is_none_when_a_side_is_missing():
    assert _divergence_percent(None, 10.0) is None
    assert _divergence_percent(10.0, None) is None


def test_a_near_zero_base_is_not_compared():
    # Um centavo de arredondamento sobre um LPA de R$0,01 acusaria 200%.
    assert _divergence_percent(MIN_COMPARABLE_VALUE / 2, 0.5) is None


def test_a_negative_base_still_compares_by_magnitude():
    # Prejuízo é comparável; o sinal do denominador não pode inverter a leitura.
    assert _divergence_percent(-10.0, -11.0) == -10.0


# ── Comparação por ticker ────────────────────────────────────────────────────


def test_agreement_produces_no_finding():
    assert _compare_ticker("PETR4", _statusinvest(), _cvm()) is None


def test_a_small_difference_stays_below_the_threshold():
    # As duas fontes discordam legitimamente por critério; só o que passa do
    # limite merece olho humano.
    pequeno = _statusinvest(lpa=10.0 * (1 + (DIVERGENCE_THRESHOLD_PERCENT - 1) / 100))
    assert _compare_ticker("PETR4", pequeno, _cvm()) is None


def test_a_large_difference_is_reported_with_both_values():
    resultado = _compare_ticker("PETR4", _statusinvest(lpa=20.0), _cvm(lpa=10.0))

    assert resultado["ticker"] == "PETR4"
    assert resultado["fields"]["lpa"]["cvm"] == 10.0
    assert resultado["fields"]["lpa"]["statusinvest"] == 20.0
    assert resultado["fields"]["lpa"]["divergence_percent"] == 100.0


def test_only_the_diverging_fields_appear():
    resultado = _compare_ticker("PETR4", _statusinvest(vpa=60.0), _cvm())
    assert set(resultado["fields"]) == {"vpa"}


# ── Relatório ────────────────────────────────────────────────────────────────


def test_the_report_counts_what_was_actually_compared():
    fontes = [_statusinvest("PETR4"), _statusinvest("ZZZZ4")]
    relatorio = _build_report(fontes, {"PETR": _cvm()}, 2025)

    assert relatorio["compared"] == 1
    assert relatorio["without_cvm_data"] == 1
    assert relatorio["diverging"] == 0


def test_the_worst_divergence_comes_first():
    fontes = [
        _statusinvest("AAAA3", lpa=12.0),
        _statusinvest("BBBB3", lpa=30.0),
    ]
    cvm = {"AAAA": _cvm(), "BBBB": _cvm()}

    relatorio = _build_report(fontes, cvm, 2025)

    assert [d["ticker"] for d in relatorio["divergences"]] == ["BBBB3", "AAAA3"]


def test_the_report_carries_the_basis_it_used():
    # Sem o ano e o limite, o número de divergências não quer dizer nada.
    relatorio = _build_report([], {}, 2025)
    assert relatorio["reference_year"] == 2025
    assert relatorio["threshold_percent"] == DIVERGENCE_THRESHOLD_PERCENT


def test_a_row_without_ticker_is_ignored():
    relatorio = _build_report([{"lpa": 10.0}], {"PETR": _cvm()}, 2025)
    assert relatorio["compared"] == 0
    assert relatorio["without_cvm_data"] == 0


# ── Serviço ──────────────────────────────────────────────────────────────────


def _run(payload, cvm_by_root, year=None):
    with (
        patch(
            "services.reconciliation_service.get_all_stocks_from_statusinvest"
        ) as mock_source,
        patch("services.reconciliation_service._annual_fundamentals") as mock_cvm,
    ):
        mock_source.return_value = payload
        mock_cvm.return_value = cvm_by_root
        return reconcile_fundamentals(year)


def test_the_service_reports_the_divergences(app):
    with app.app_context():
        result, status = _run(
            {"list": [_statusinvest("PETR4", lpa=20.0)]}, {"PETR": _cvm(lpa=10.0)}
        )

        assert status == 200
        assert result.get_json()["diverging"] == 1


def test_an_unreachable_source_is_not_a_silent_pass(app):
    # Fonte fora do ar não pode virar "zero divergências".
    with app.app_context():
        _, status = _run(None, {"PETR": _cvm()})
        assert status == 502


def test_reconciling_without_cvm_data_says_so(app):
    with app.app_context():
        result, status = _run({"list": [_statusinvest()]}, {})
        assert status == 409
        assert "ingestão" in result.get_json()["message"]


def test_an_unexpected_failure_returns_500(app):
    with app.app_context():
        with patch(
            "services.reconciliation_service.get_all_stocks_from_statusinvest"
        ) as mock_source:
            mock_source.side_effect = Exception("boom")

            _, status = reconcile_fundamentals()

        assert status == 500


def test_annual_fundamentals_skips_a_company_without_share_count(app):
    from services.reconciliation_service import _annual_fundamentals

    linha = SimpleNamespace(
        acoes_circulacao=None,
        patrimonio_liquido=500.0,
        lucro_controladores=90.0,
        lucro_liquido=100.0,
    )
    with app.app_context():
        with patch("services.reconciliation_service.db") as mock_db:
            query = mock_db.session.query.return_value.join.return_value
            query.filter.return_value.all.return_value = [("PETR", linha)]

            assert _annual_fundamentals(2025) == {}
