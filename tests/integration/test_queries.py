"""
O que o SQLite dos testes unitários não sabe reproduzir.

Três comportamentos deste backend dependem do Postgres de verdade e nunca
tinham sido exercitados contra um:

    A ordenação com NULLS LAST. O Postgres põe NULL **primeiro** num
    `ORDER BY ... DESC`, e foi assim que a correção da fórmula de Graham
    abriu a lista de ações numa página de brancos.

    O `ON CONFLICT`, que precisa de uma restrição de unicidade existindo de
    fato — sem ela, todo upsert falha, que é o motivo de a tabela de preços
    ter ficado vazia a vida inteira do projeto.

    O score gravado e lido de volta por join, em vez de por dicionário mockado.
"""

from datetime import date, datetime, timedelta

import pytest

from .conftest import requer_docker

pytestmark = requer_docker


# ── Auxiliares ───────────────────────────────────────────────────────────────


def _stock(ticker, **overrides):
    from models.stock import Stock

    valores = {
        "ticker": ticker,
        "companyname": f"Empresa {ticker}",
        "sectorname": "Bens Industriais",
        "price": 10.0,
        "p_l": 5.0,
        "liquidezmediadiaria": 5_000_000.0,
        "active": True,
    }
    valores.update(overrides)
    return Stock(**valores)


def _fii(ticker, **overrides):
    from models.fii import Fii

    valores = {
        "ticker": ticker,
        "companyname": f"Fundo {ticker}",
        "segment": "Logística",
        "price": 100.0,
        "p_vp": 0.90,
        "dy": 9.0,
        "liquidezmediadiaria": 5_000_000.0,
        "ffo_yield": 8.0,
        "qtd_imoveis": 10,
        "cap_rate": 8.5,
        "vacancia_media": 3.0,
        "numerocotistas": 100_000.0,
        "dividend_cagr": 2.0,
        "cota_cagr": 1.5,
        "patrimonio": 1_000_000_000.0,
    }
    valores.update(overrides)
    return Fii(**valores)


def _usuario(db_session):
    from models.user import User

    user = User(
        user_name="integracao",
        name="Integração",
        email="integracao@exemplo.com",
        profile="USER",
        password="hash",
    )
    db_session.add(user)
    db_session.commit()
    return user


# ── NULLS LAST ───────────────────────────────────────────────────────────────


def test_o_postgres_poe_nulo_primeiro_sem_nulls_last(db_session):
    # Documenta a razão de a cláusula existir. Se o dia em que este teste
    # falhar chegar, a cláusula virou desnecessária — não o contrário.
    from models.stock import Stock

    db_session.add_all([_stock("AAAA3", p_l=None), _stock("BBBB3", p_l=9.0)])
    db_session.commit()

    sem_clausula = [
        linha.ticker for linha in Stock.query.order_by(Stock.p_l.desc()).all()
    ]
    assert sem_clausula[0] == "AAAA3"


def test_a_listagem_devolve_os_nulos_por_ultimo(db_session, app):
    # Foi o que a correção da fórmula de Graham quebrou: ela passou a devolver
    # None onde não se aplica, e a lista abriu numa página de brancos.
    from services.stock_services import list_stocks

    usuario = _usuario(db_session)
    db_session.add_all(
        [
            _stock("AAAA3", p_l=None),
            _stock("BBBB3", p_l=9.0),
            _stock("CCCC3", p_l=4.0),
        ]
    )
    db_session.commit()

    resposta, status = list_stocks(usuario.id, sort_by="p_l", sort_dir="desc")

    assert status == 200
    tickers = [linha["ticker"] for linha in resposta.get_json()["data"]]
    assert tickers == ["BBBB3", "CCCC3", "AAAA3"]


def test_a_listagem_de_fii_tambem_devolve_os_nulos_por_ultimo(db_session):
    from services.fii_services import list_fiis

    usuario = _usuario(db_session)
    db_session.add_all([_fii("AAAA11", dy=None), _fii("BBBB11", dy=9.0)])
    db_session.commit()

    resposta, _ = list_fiis(usuario.id, sort_by="dy", sort_dir="desc")

    tickers = [linha["ticker"] for linha in resposta.get_json()["data"]]
    assert tickers == ["BBBB11", "AAAA11"]


# ── O score de FII, de ponta a ponta ─────────────────────────────────────────


def test_o_refresh_grava_score_para_todo_fundo_e_perfil(db_session):
    from models.fii_score import FiiScore
    from services.fii_scoring_service import FII_PROFILES, refresh_fii_scores

    db_session.add_all([_fii(f"FUN{i}11", p_vp=0.7 + i * 0.05) for i in range(5)])
    db_session.commit()

    gravadas = refresh_fii_scores()

    assert gravadas == 5 * len(FII_PROFILES)
    assert FiiScore.query.count() == gravadas
    assert FiiScore.query.filter(FiiScore.score_total.isnot(None)).count() == gravadas


def test_o_refresh_e_idempotente(db_session):
    # Roda no fim de toda atualização de FIIs; se acumulasse, a segunda
    # execução do dia dobraria a tabela.
    from models.fii_score import FiiScore
    from services.fii_scoring_service import refresh_fii_scores

    db_session.add_all([_fii(f"FUN{i}11") for i in range(5)])
    db_session.commit()

    primeira = refresh_fii_scores()
    refresh_fii_scores()

    assert FiiScore.query.count() == primeira


def test_o_fundo_ilíquido_e_gravado_com_o_motivo_da_exclusao(db_session):
    from models.fii_score import FiiScore
    from services.fii_scoring_service import refresh_fii_scores

    db_session.add_all(
        [_fii(f"FUN{i}11") for i in range(4)]
        + [_fii("ILIQ11", liquidezmediadiaria=1_000.0)]
    )
    db_session.commit()
    refresh_fii_scores()

    excluido = FiiScore.query.filter_by(ticker="ILIQ11").first()
    assert excluido.eligible is False
    assert excluido.score_total is None
    assert "LIQUIDEZ_BAIXA" in excluido.exclusion_reasons


def test_a_tabela_de_fii_traz_o_score_pelo_join(db_session):
    from services.fii_scoring_service import refresh_fii_scores
    from services.fii_services import list_fiis

    usuario = _usuario(db_session)
    db_session.add_all([_fii(f"FUN{i}11", p_vp=0.7 + i * 0.05) for i in range(5)])
    db_session.commit()
    refresh_fii_scores()

    resposta, status = list_fiis(usuario.id, sort_by="score_total", sort_dir="desc")

    assert status == 200
    linhas = resposta.get_json()["data"]
    notas = [linha["score_total"] for linha in linhas]
    assert all(nota is not None for nota in notas)
    assert notas == sorted(notas, reverse=True)


def test_o_fundo_sem_score_continua_na_tabela(db_session):
    # Join à esquerda: sumir com o fundo esconderia o ativo, não a nota.
    from services.fii_services import list_fiis

    usuario = _usuario(db_session)
    db_session.add(_fii("SOZI11"))
    db_session.commit()

    resposta, _ = list_fiis(usuario.id)
    linha = resposta.get_json()["data"][0]

    assert linha["ticker"] == "SOZI11"
    assert linha["score_total"] is None


# ── Histórico mensal de FII ──────────────────────────────────────────────────


def _historico(ticker, meses, p_vp=1.0, fim=None):
    from models.fii_indicator_history import FiiIndicatorHistory

    fim = fim or date.today()
    return [
        FiiIndicatorHistory(
            ticker=ticker,
            reference_date=fim - timedelta(days=30 * i),
            valor_patrimonial_cota=100.0,
            close_price=100.0 * p_vp,
            p_vp=p_vp,
        )
        for i in range(meses)
    ]


def test_a_mediana_historica_sai_do_banco(db_session):
    from services.fii_scoring_service import get_history_signals

    db_session.add_all(_historico("HGLG11", meses=24, p_vp=1.0))
    db_session.commit()

    assert get_history_signals(["HGLG11"])["HGLG11"]["p_vp_mediano"] == 1.0


def test_a_janela_de_36_meses_corta_o_que_e_antigo_demais(db_session):
    from services.fii_scoring_service import get_history_signals

    db_session.add_all(_historico("HGLG11", meses=24, p_vp=1.0))
    # Cotações de cinco anos atrás, muito mais caras, que não podem pesar.
    db_session.add_all(
        _historico(
            "HGLG11", meses=12, p_vp=2.0, fim=date.today() - timedelta(days=5 * 365)
        )
    )
    db_session.commit()

    assert get_history_signals(["HGLG11"])["HGLG11"]["p_vp_mediano"] == 1.0


def test_fundo_recem_listado_fica_de_fora_da_comparacao(db_session):
    from services.fii_scoring_service import get_history_signals

    db_session.add_all(_historico("NOVO11", meses=6))
    db_session.commit()

    assert get_history_signals(["NOVO11"]) == {}


def test_a_tendencia_do_patrimonio_por_cota_sai_do_banco(db_session):
    # O sinal que separa fundo barato de fundo encolhendo, lido do histórico
    # de verdade em vez de mockado.
    from models.fii_indicator_history import FiiIndicatorHistory
    from services.fii_scoring_service import get_history_signals

    base = date.today()
    db_session.add_all(
        [
            FiiIndicatorHistory(
                ticker="CAIN11",
                reference_date=base - timedelta(days=30 * i),
                p_vp=1.0,
                # Patrimônio por cota caindo 1% ao mês, do mais antigo ao mais
                # recente: close/p_vp é o valor patrimonial ajustado.
                close_price=100.0 * (0.99 ** (23 - i)),
            )
            for i in range(24)
        ]
    )
    db_session.commit()

    tendencia = get_history_signals(["CAIN11"])["CAIN11"]["vp_tendencia"]
    assert tendencia < -20


def test_a_restricao_de_unicidade_do_historico_e_real(db_session):
    from sqlalchemy.exc import IntegrityError

    from models.fii_indicator_history import FiiIndicatorHistory

    db_session.add(
        FiiIndicatorHistory(ticker="HGLG11", reference_date=date(2025, 1, 31), p_vp=0.9)
    )
    db_session.commit()

    db_session.add(
        FiiIndicatorHistory(ticker="HGLG11", reference_date=date(2025, 1, 31), p_vp=0.8)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_o_upsert_atualiza_em_vez_de_duplicar(db_session):
    # A carga do histórico roda em duas passadas: a CVM grava o patrimônio e o
    # Yahoo volta depois para preencher o preço. A segunda passada não pode
    # apagar o que a primeira escreveu.
    from sqlalchemy.dialects.postgresql import insert

    from models.fii_indicator_history import FiiIndicatorHistory

    chave = {"ticker": "HGLG11", "reference_date": date(2025, 1, 31)}

    primeira = insert(FiiIndicatorHistory).values(
        [{**chave, "valor_patrimonial_cota": 166.67}]
    )
    db_session.execute(primeira)

    segunda = insert(FiiIndicatorHistory).values([{**chave, "close_price": 150.0}])
    db_session.execute(
        segunda.on_conflict_do_update(
            index_elements=["ticker", "reference_date"],
            set_={"close_price": segunda.excluded.close_price},
        )
    )
    db_session.commit()

    linhas = FiiIndicatorHistory.query.all()
    assert len(linhas) == 1
    assert linhas[0].close_price == 150.0
    assert linhas[0].valor_patrimonial_cota == 166.67


# ── Score de ação e sonda ────────────────────────────────────────────────────


def test_o_score_de_acao_sobrevive_a_ida_e_volta_ao_banco(db_session):
    from models.stock_score import StockScore
    from services.scoring_service import refresh_scores

    db_session.add_all(
        [_stock(f"AAA{i}3", p_l=4.0 + i, p_vp=1.0 + i * 0.1) for i in range(6)]
    )
    db_session.commit()

    refresh_scores()

    gravado = StockScore.query.filter_by(profile="EQUILIBRADO").first()
    payload = gravado.to_json()
    assert payload["pillars"]
    assert isinstance(payload["reasons"], list)


def test_a_sonda_de_saude_responde_com_o_banco_no_ar(client, db_session):
    resposta = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok", "database": "ok"}


def test_a_deslistagem_tira_a_acao_da_listagem(db_session):
    # `active` entrou com a migração de deslistagem e a listagem filtra por
    # ela; num banco de verdade isso é uma cláusula WHERE, não um mock.
    from services.stock_services import list_stocks

    usuario = _usuario(db_session)
    db_session.add_all(
        [_stock("VIVA3"), _stock("MORT3", active=False, delisted_at=datetime.utcnow())]
    )
    db_session.commit()

    resposta, _ = list_stocks(usuario.id)
    tickers = [linha["ticker"] for linha in resposta.get_json()["data"]]

    assert tickers == ["VIVA3"]


def test_o_score_sai_mesmo_sem_as_tabelas_da_cvm(db_session, caplog):
    """
    As tabelas da CVM pertencem ao pipeline e o `flask db upgrade` do backend
    não as cria. Antes, a consulta ao histórico de lucro subia e o
    `refresh_scores` devolvia **zero** — nenhuma ação pontuada, por causa de
    um guard rail entre cinco, e só uma linha de log para avisar.
    """
    from models.stock_score import StockScore
    from services.scoring_service import refresh_scores

    db_session.add_all([_stock(f"BBB{i}3", p_l=4.0 + i) for i in range(6)])
    db_session.commit()

    gravadas = refresh_scores()

    assert gravadas > 0
    assert StockScore.query.filter(StockScore.score_total.isnot(None)).count() > 0
    assert "Histórico de lucro indisponível" in caplog.text


def test_sem_historico_nenhuma_empresa_e_excluida_por_lucro(db_session):
    from models.stock_score import StockScore
    from services.scoring_service import refresh_scores

    db_session.add_all([_stock(f"CCC{i}3") for i in range(6)])
    db_session.commit()
    refresh_scores()

    motivos = " ".join(
        linha.exclusion_reasons or "" for linha in StockScore.query.all()
    )
    assert "LUCRO_INCONSISTENTE" not in motivos
