"""kosi -> OpenAPI: a VALID document that loses no kosi endpoint.

atom-tools#92: every Spring endpoint arrived with an empty path, the
converter dropped them, and `convert -t kotlin` exited 0 with `paths: {}`.
These pin the converter's half of the contract: every HTTP route lands in
`paths`, everything else lands in a named `x-kosi-*` list, and the document
passes the OpenAPI validator.
"""

import json

from openapi_spec_validator import validate

from atom_tools.lib.converter import OpenAPI


def _endpoint(path, methods, handler, **extra):
    return {
        "framework": extra.pop("framework", "spring-mvc"),
        "httpMethod": methods,
        "pathTemplate": path,
        "pathParameters": [],
        "queryParameters": [],
        "handlerCanonicalName": handler,
        "handlerSymbol": handler,
        "position": {"filename": "src/main/kotlin/Api.kt", "line": 3, "column": 1},
        "foundBy": extra.pop("foundBy", "annotation"),
        **extra,
    }


def _document(tmp_path, endpoints):
    report = {"schemaVersion": "kosi/1", "tool": {"name": "kosi"}, "apiEndpoints": endpoints}
    source = tmp_path / "kosi.json"
    source.write_text(json.dumps(report), encoding="utf-8")
    return OpenAPI("openapi3.1.0", "kotlin", str(source)).endpoints_to_openapi()


def test_repository_resource_fans_out_with_unique_operation_ids(tmp_path):
    doc = _document(
        tmp_path,
        [
            _endpoint("/orders", ["GET", "HEAD", "POST"], "demo.OrderRepository", foundBy="implicit"),
            _endpoint("/orders/{id}", ["GET", "PUT", "PATCH"], "demo.OrderRepository", foundBy="implicit"),
        ],
    )
    validate(doc)
    ids = [op["operationId"] for item in doc["paths"].values() for op in item.values()]
    assert len(ids) == 6 and len(set(ids)) == 6
    # The handler stays readable on every renamed operation.
    renamed = [op for item in doc["paths"].values() for op in item.values() if op["operationId"] != "demo.OrderRepository"]
    assert renamed and all(op["x-kosi-handler"] == "demo.OrderRepository" for op in renamed)


def test_any_method_route_is_every_verb_and_says_so(tmp_path):
    doc = _document(tmp_path, [_endpoint("/reports", [], "demo.Reports.all", anyMethod=True)])
    validate(doc)
    item = doc["paths"]["/reports"]
    assert set(item) == {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    assert all(op["x-kosi-any-method"] is True for op in item.values())


def test_nothing_is_dropped_silently(tmp_path):
    doc = _document(
        tmp_path,
        [
            _endpoint("/api/ok", ["GET"], "demo.Api.ok"),
            _endpoint("", [], "demo.OnKafka.listen", framework="spring-messaging", transport="messaging"),
            _endpoint("", [], "demo.Search.handle", framework="ratpack", pathUnresolved="declares no route"),
            _endpoint("/metrics", [], "demo.routes$lambda0", framework="unattributed", foundBy="dsl-unattributed"),
        ],
    )
    validate(doc)
    assert list(doc["paths"]) == ["/api/ok"]
    assert [e["handler"] for e in doc["x-kosi-non-http-endpoints"]] == ["demo.OnKafka.listen"]
    assert doc["x-kosi-unmounted-handlers"][0]["reason"] == "declares no route"
    assert doc["x-kosi-method-unresolved"][0]["path"] == "/metrics"


def test_unresolved_base_path_travels_on_the_operation(tmp_path):
    doc = _document(
        tmp_path,
        [_endpoint("/stock", ["GET"], "demo.Stock.get", pathUnresolved="spring.data.rest.base-path: config files disagree")],
    )
    validate(doc)
    assert doc["paths"]["/stock"]["get"]["x-kosi-path-unresolved"].startswith("spring.data.rest.base-path")


def test_one_route_many_handlers_keeps_them_all(tmp_path):
    # Every GraphQL operation is served at POST /graphql.
    doc = _document(
        tmp_path,
        [
            _endpoint("/graphql", ["POST"], "demo.Graph.book", framework="graphql"),
            _endpoint("/graphql", ["POST"], "demo.Graph.author", framework="graphql"),
        ],
    )
    validate(doc)
    assert doc["paths"]["/graphql"]["post"]["x-kosi-handlers"] == ["demo.Graph.book", "demo.Graph.author"]


def test_verbs_openapi_cannot_carry_are_kept_named(tmp_path):
    # CONNECT has no OpenAPI operation field; LOCK is Micronaut's
    # @CustomHttpMethod. Neither may vanish from the document.
    doc = _document(
        tmp_path,
        [
            _endpoint("/tunnel", ["CONNECT"], "demo.Tunnel.connect", framework="vertx"),
            _endpoint("/files", ["LOCK", "GET"], "demo.Files.lock", framework="micronaut"),
        ],
    )
    validate(doc)
    assert list(doc["paths"]) == ["/files"] and list(doc["paths"]["/files"]) == ["get"]
    reasons = {e["handler"]: e["reason"] for e in doc["x-kosi-unsupported-methods"]}
    assert "CONNECT" in reasons["demo.Tunnel.connect"] and "LOCK" in reasons["demo.Files.lock"]
