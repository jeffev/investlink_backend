"""
Guards the API documentation against drift.

Catching up by hand does not hold: the Swagger file had fallen fourteen routes
behind, including three added in the same week. This compares what the app
actually serves against what the file claims, so the gap fails a test instead
of being discovered by whoever tried to use the docs.
"""

import json
import os
import re

import pytest

SWAGGER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "app", "static", "swagger.json"
)

# Served by the app but deliberately outside the public API contract.
UNDOCUMENTED_BY_DESIGN = {
    "/static/<path:filename>",
    "/swagger",
}

# Flask writes /v1/stock/<string:ticker>; Swagger writes /stock/{ticker}.
_CONVERTER = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")


@pytest.fixture(scope="module")
def swagger():
    with open(SWAGGER_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def routed_app():
    """
    An app with every route registered.

    The shared `app` fixture is a bare Flask instance for mocking services, so
    its url_map is empty — comparing the documentation against it would pass
    for the wrong reason.
    """
    from config import create_app
    from utils import setup_routes

    application = create_app()
    setup_routes(application)
    return application


def _to_swagger_path(rule, base_path):
    path = _CONVERTER.sub(r"{\1}", rule)
    if base_path and path.startswith(base_path):
        path = path[len(base_path) :]
    return path or "/"


def _served_routes(app, base_path):
    """{swagger path: set of methods} for everything the app exposes."""
    routes = {}
    for rule in app.url_map.iter_rules():
        if rule.rule in UNDOCUMENTED_BY_DESIGN or rule.endpoint == "static":
            continue
        if not rule.rule.startswith(base_path):
            continue
        methods = {
            method.lower()
            for method in rule.methods
            if method not in ("HEAD", "OPTIONS")
        }
        routes.setdefault(_to_swagger_path(rule.rule, base_path), set()).update(methods)
    return routes


def test_every_served_route_is_documented(routed_app, swagger):
    base_path = swagger.get("basePath", "")
    served = _served_routes(routed_app, base_path)
    documented = set(swagger["paths"])

    missing = sorted(set(served) - documented)
    assert (
        not missing
    ), "Rotas servidas pela API e ausentes do swagger.json: " + ", ".join(missing)


def test_no_documented_route_has_disappeared(routed_app, swagger):
    # Documentação que descreve rota inexistente engana tanto quanto a ausente.
    base_path = swagger.get("basePath", "")
    served = set(_served_routes(routed_app, base_path))

    stale = sorted(set(swagger["paths"]) - served)
    assert not stale, "Rotas no swagger.json que a API não serve mais: " + ", ".join(
        stale
    )


def test_documented_methods_match_what_is_served(routed_app, swagger):
    base_path = swagger.get("basePath", "")
    served = _served_routes(routed_app, base_path)

    divergent = []
    for path, methods in served.items():
        documented = {
            method
            for method in swagger["paths"].get(path, {})
            if method in ("get", "post", "put", "delete", "patch")
        }
        if documented and not methods.issubset(documented):
            divergent.append(f"{path}: serve {sorted(methods - documented)}")

    assert not divergent, "Métodos servidos e não documentados: " + "; ".join(divergent)


def test_every_documented_operation_has_a_summary(swagger):
    # Uma rota listada sem explicação não é documentação, é inventário.
    without_summary = [
        f"{path} {method}"
        for path, operations in swagger["paths"].items()
        for method, operation in operations.items()
        if method in ("get", "post", "put", "delete", "patch")
        and not operation.get("summary")
    ]
    assert not without_summary, "Operações sem summary: " + ", ".join(without_summary)
