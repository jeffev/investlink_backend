"""
A rotina que roda sozinha.

Até existir, o dado só mudava quando alguém lembrava de clicar em "Atualizar
Ações" — e na primeira execução automática descobrimos que a fonte de ações
devolvia 403 havia semanas, sem ninguém notar, porque nada rodava e nada
registrava.

O que estes testes protegem é justamente o comportamento sob falha: uma etapa
quebrada não pode derrubar as outras, e o resultado precisa ficar gravado
mesmo quando tudo dá errado — é aí que o registro serve.
"""

from unittest.mock import MagicMock, patch

# Importado pelo efeito colateral: `utils` traz os imports que registram todos
# os mappers. Sem ele, instanciar qualquer model aqui quebra em
# `Favorite -> User`, que é uma pegadinha conhecida deste projeto.
import utils  # noqa: F401

from jobs.daily_refresh import (
    STATUS_ERRO,
    STATUS_OK,
    STATUS_PARCIAL,
    run_daily_refresh,
)


def _executar(acoes, fiis, snapshot=None):
    """Roda o ciclo com cada etapa dublada e devolve a linha gravada."""
    gravadas = []

    with (
        patch("jobs.daily_refresh.update_all_stocks", side_effect=acoes) as mock_acoes,
        patch("jobs.daily_refresh.update_all_fiis", side_effect=fiis) as mock_fiis,
        patch(
            "jobs.daily_refresh.record_snapshots",
            side_effect=snapshot or (lambda: 10),
        ) as mock_snapshot,
        patch("jobs.daily_refresh.prune_snapshots", return_value=0),
        patch("jobs.daily_refresh.record_closing_prices", return_value=900),
        patch("jobs.daily_refresh.db") as mock_db,
    ):
        mock_db.session = MagicMock()
        mock_db.session.add.side_effect = gravadas.append
        execucao = run_daily_refresh()

    return execucao, gravadas, (mock_acoes, mock_fiis, mock_snapshot)


def _ok():
    return (MagicMock(), 200)


def _falha():
    return (MagicMock(), 500)


def test_ciclo_completo_fica_ok(app):
    with app.app_context():
        execucao, gravadas, _ = _executar(acoes=[_ok()], fiis=[_ok()])

        assert execucao.status == STATUS_OK
        assert gravadas == [execucao]


def test_uma_etapa_quebrada_nao_derruba_as_outras(app):
    # Se o FII caiu e a ação passou, o usuário tem preço novo de ação —
    # esconder isso por causa do FII trocaria um dado velho por dois.
    with app.app_context():
        execucao, _, (mock_acoes, mock_fiis, _) = _executar(
            acoes=[_ok()], fiis=[_falha()]
        )

        assert execucao.status == STATUS_PARCIAL
        assert mock_acoes.called and mock_fiis.called


def test_excecao_na_fonte_nao_escapa_da_rotina(app):
    # A fonte caindo não pode matar o processo do agendador: amanhã ele
    # precisa disparar de novo.
    with app.app_context():
        execucao, _, _ = _executar(
            acoes=[ConnectionError("fonte fora do ar")], fiis=[_ok()]
        )

        assert execucao.status == STATUS_PARCIAL
        assert "ConnectionError" in execucao.detail


def test_tudo_falhando_vira_erro_e_mesmo_assim_fica_registrado(app):
    # É exatamente o caso em que o registro serve: o sintoma visível seria
    # "os dados congelaram", sem nada a que recorrer.
    with app.app_context():
        execucao, gravadas, _ = _executar(acoes=[_falha()], fiis=[_falha()])

        assert execucao.status == STATUS_ERRO
        assert gravadas == [execucao]


def test_sem_nenhuma_coleta_o_retrato_do_dia_nao_e_gravado(app):
    # Guardar um retrato sem nota nova inventaria "nenhuma mudança" num dia
    # em que, na verdade, nada foi medido.
    with app.app_context():
        _, _, (_, _, mock_snapshot) = _executar(acoes=[_falha()], fiis=[_falha()])

        mock_snapshot.assert_not_called()


def test_o_detalhe_nomeia_a_etapa_que_falhou(app):
    with app.app_context():
        execucao, _, _ = _executar(acoes=[_falha()], fiis=[_ok()])

        assert "acoes: HTTP 500" in execucao.detail
        assert "fiis: HTTP 200" in execucao.detail
