"""kosi -> OpenAPI: a VALID document that loses no kosi endpoint.

atom-tools#92: every Spring endpoint arrived with an empty path, the
converter dropped them, and `convert -t kotlin` exited 0 with `paths: {}`.
These pin the converter's half of the contract: every HTTP route lands in
`paths`, everything else lands in a named `x-kosi-*` list, and the document
passes the OpenAPI validator.
"""

import json
from pathlib import Path

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


def test_declared_verb_wins_over_any_method_in_either_order(tmp_path):
    for order in (0, 1):
        records = [
            _endpoint("/items", [], "demo.Items.any", anyMethod=True),
            _endpoint("/items", ["GET"], "demo.Items.get"),
        ]
        doc = _document(tmp_path, records[::-1] if order else records)
        validate(doc)
        assert "x-kosi-any-method" not in doc["paths"]["/items"]["get"]
        assert doc["paths"]["/items"]["post"]["x-kosi-any-method"] is True


def test_path_unresolved_survives_a_merge_in_either_order(tmp_path):
    for order in (0, 1):
        records = [
            _endpoint("/stock", ["GET"], "demo.A.get"),
            _endpoint("/stock", ["GET"], "demo.B.get", pathUnresolved="base path unproven"),
        ]
        doc = _document(tmp_path, records[::-1] if order else records)
        assert doc["paths"]["/stock"]["get"]["x-kosi-path-unresolved"] == "base path unproven"


def test_handler_list_never_holds_a_missing_name(tmp_path):
    doc = _document(tmp_path, [_endpoint("/x", ["GET"], ""), _endpoint("/x", ["GET"], "demo.X.get")])
    assert None not in doc["paths"]["/x"]["get"].get("x-kosi-handlers", [])


def test_path_unresolved_dsl_route_is_its_own_list(tmp_path):
    """atom-tools#95: a Ktor route whose path is computed at run time is a
    real registration with an unknown URL, not an unmounted handler. It is
    listed under ``x-kosi-path-unresolved-routes`` with kosi's reason, and
    never lands in ``paths`` under an invented template."""
    doc = _document(
        tmp_path,
        [
            _endpoint("/control", ["GET"], "demo.module$lambda0", framework="ktor", foundBy="dsl"),
            _endpoint(
                "",
                ["GET"],
                "demo.dynamic$lambda1",
                framework="ktor",
                foundBy="dsl",
                pathUnresolved="the route's own path argument is computed at run time and did not fold to a constant",
            ),
            _endpoint("", [], "demo.Search.handle", framework="ratpack", pathUnresolved="declares no route"),
        ],
    )
    validate(doc)
    assert list(doc["paths"]) == ["/control"]
    [route] = doc["x-kosi-path-unresolved-routes"]
    assert route["handler"] == "demo.dynamic$lambda1"
    assert route["methods"] == ["GET"] and route["reason"].startswith("the route's own path argument")
    # The Ratpack handler kosi never saw registered stays an unmounted handler.
    assert [e["handler"] for e in doc["x-kosi-unmounted-handlers"]] == ["demo.Search.handle"]


def test_loop_registered_routes_from_a_real_kosi_report(tmp_path):
    """The kosi dsl-loop-paths fixture, as kosi 4.0.2 reports it: literal
    loops expand to one operation per element, and no loop variable's name
    is ever a path."""
    source = Path(__file__).parent / "data" / "ecosystem" / "kotlin-dsl-loop-paths-kosi.json"
    doc = OpenAPI("openapi3.1.0", "kotlin", str(source)).endpoints_to_openapi()
    validate(doc)
    assert sorted(doc["paths"]) == [
        "/api/p", "/api/q", "/control", "/each/a", "/each/b", "/m", "/on", "/one", "/two", "/x", "/y",
    ]
    assert not {"/vroute", "/vq", "/vit", "/vp"} & set(doc["paths"])
    unresolved = doc["x-kosi-path-unresolved-routes"]
    assert sorted(e["handler"].split(".")[-1].split("$")[0] for e in unresolved) == [
        "computed", "dynamic", "grown", "indexed",
    ]
    assert "x-kosi-unmounted-handlers" not in doc


def test_anonymous_regex_placeholder_is_a_valid_wildcard(tmp_path):
    """JAX-RS `@Path("/{.*}")` and http4k `"/{.*}" bind GET` name no
    parameter. Substituting the catch-all `*` inside the braces produced
    `/{.{path}}`, and the whole http4k document failed validation."""
    doc = _document(
        tmp_path,
        [
            _endpoint("/{.*}", ["GET"], "demo.Bridge.get", framework="quarkus"),
            _endpoint("/prefix/{.*}", ["GET"], "demo.Routes.any", framework="http4k", foundBy="dsl"),
            _endpoint("/x/{id:[0-9]+}/{.+}", ["GET"], "demo.Mixed.get"),
        ],
    )
    validate(doc)
    assert set(doc["paths"]) == {"/{path}", "/prefix/{path}", "/x/{id}/{path}"}


def test_a_non_name_path_parameter_is_not_declared(tmp_path):
    """An older kosi listed http4k's `{$}` end anchor as a parameter `$`."""
    doc = _document(tmp_path, [_endpoint("/a", ["GET"], "demo.Routes.a", framework="http4k", pathParameters=["$"])])
    validate(doc)
    assert "parameters" not in doc["paths"]["/a"]["get"]


def test_hyphenated_and_dotted_parameter_names_stay_names(tmp_path):
    """Javalin `{user-id}` (kosi reports the name as written) and a dotted
    `{a.b}` are names. Reading them as wildcards renamed the placeholder to
    `{path}` while the parameter kept its name, and one such route made the
    WHOLE document invalid."""
    doc = _document(
        tmp_path,
        [
            _endpoint("/users/{user-id}", ["GET"], "demo.H.user", framework="javalin", foundBy="dsl", pathParameters=["user-id"]),
            _endpoint("/c/{a.b}", ["GET"], "demo.H.dotted", pathParameters=["a.b"]),
        ],
    )
    validate(doc)
    assert set(doc["paths"]) == {"/users/{user-id}", "/c/{a.b}"}
    assert [p["name"] for p in doc["paths"]["/users/{user-id}"]["get"]["parameters"]] == ["user-id"]


def test_a_regex_placeholder_with_nested_braces_is_one_parameter(tmp_path):
    """`{id:\\d{3}}` nests a brace: the first `}` left a stray one behind."""
    doc = _document(tmp_path, [_endpoint("/x/{id:\\d{3}}/y", ["GET"], "demo.H.regex", pathParameters=["id"])])
    validate(doc)
    assert list(doc["paths"]) == ["/x/{id}/y"]


def test_a_parameter_the_template_does_not_carry_is_never_declared(tmp_path):
    """A declared path parameter missing from the template invalidates the
    document: `{name?}` normalises to a wildcard, so kosi's `name` names
    nothing the template carries."""
    doc = _document(tmp_path, [_endpoint("/opt/{name?}", ["GET"], "demo.H.opt", framework="ktor", foundBy="dsl", pathParameters=["name"])])
    validate(doc)
    assert [p["name"] for p in doc["paths"]["/opt/{path}"]["get"]["parameters"]] == ["path"]


def test_a_mapping_whose_path_constant_did_not_fold_is_a_path_unresolved_route(tmp_path):
    """`@GetMapping(ExternalPaths.USERS)` is a REGISTERED route whose URL is
    unknown, not an unmounted handler: the mapping names its verb (or serves
    every one). A Handler implementation kosi never saw mounted names none."""
    reason = "the mapping's path is the constant ExternalPaths.USERS, which neither the classpath nor the analysed sources fold to one value"
    doc = _document(
        tmp_path,
        [
            _endpoint("", ["GET"], "demo.C.users", pathUnresolved=reason),
            _endpoint("", [], "demo.C.any", anyMethod=True, pathUnresolved=reason),
            _endpoint("", [], "demo.Search.handle", framework="ratpack", pathUnresolved="declares no route"),
        ],
    )
    validate(doc)
    assert sorted(e["handler"] for e in doc["x-kosi-path-unresolved-routes"]) == ["demo.C.any", "demo.C.users"]
    assert [e["handler"] for e in doc["x-kosi-unmounted-handlers"]] == ["demo.Search.handle"]


def test_constant_paths_from_a_real_kosi_report(tmp_path):
    """The kosi spring-const-scoping-unresolved fixture: constants, templates
    and concatenations fold into full paths (kuvasz's `"${API}/monitors"`
    prefix included), and a mapping over a constant kosi could not fold is a
    registered route with an unknown URL — never an unmounted handler, never
    the identifier as a path."""
    source = Path(__file__).parent / "data" / "ecosystem" / "kotlin-const-scoping-kosi.json"
    doc = OpenAPI("openapi3.1.0", "kotlin", str(source)).endpoints_to_openapi()
    validate(doc)
    assert {"/api/v2/monitors", "/api/v2/monitors/{id}", "/own-k1", "/own-k2", "/java-iface", "/local-users/m"} <= set(doc["paths"])
    # Spring property placeholders resolve from the fixture's application.yml.
    assert {"/v1/users/x", "/gen/y"} <= set(doc["paths"])
    assert not {p for p in doc["paths"] if "LibPaths" in p or "IMPORTED" in p or p == "/{id}"}
    unresolved = sorted(e["handler"].split(".")[-1] for e in doc["x-kosi-path-unresolved-routes"])
    assert unresolved == ["e", "ext", "imp", "mixed", "z"]
    assert "x-kosi-unmounted-handlers" not in doc
