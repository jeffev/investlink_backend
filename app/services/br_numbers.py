import re

"""
Número no formato brasileiro, como as fontes publicam.

"545.803.000,00", "30,93%" e "0,000" convivem na mesma tabela. O conversor
vivia só dentro de `fii_services`; quando a coleta de ações passou a ler a
mesma fonte, copiar as três linhas teria criado duas regras para o mesmo
formato — e uma delas envelheceria sozinha.
"""

_NAO_NUMERICO = re.compile(r"[^\d,.\-]")


def parse_br_float(value, default=0.0):
    """
    Devolve float a partir do texto publicado, ou `default` quando não dá.

    `default` é 0.0 e não None de propósito: é o que o resto do carregamento
    espera, e o score trata zero como "sem dado" justamente porque a fonte
    publica ausência como zero.
    """
    if value is None:
        return default

    texto = _NAO_NUMERICO.sub("", str(value)).strip()
    if not texto or texto in ("-", ","):
        return default

    # Milhar com ponto, decimal com vírgula.
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return default
