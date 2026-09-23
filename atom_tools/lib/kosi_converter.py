"""
Kotlin converter helper.

Consumes a kosi report (produced by the ``kosi`` analyzer shipped in
``cdxgen/cdxgen-plugins-bin`` v4.0.0+) and produces an OpenAPI paths dict
in the same shape that the JVM-style processing in
``atom_tools.lib.converter`` does for other languages.

kosi's ``apiEndpoints`` array carries the framework, the served HTTP
methods (a list on a single record, unlike every other engine's single
method), the path template, handler canonical name, path/query parameter
names, and the consumed/produced media types. This module translates
those records into the OpenAPI shape atom-tools' callers expect.

Two honesty rules carried over from the adapter that reads the same
records (``atom_tools.lib.adapters.kosi``):

- An endpoint whose ``httpMethod`` list is empty has NO resolved method
  at a site kosi models — it is not "any method". OpenAPI cannot express
  a route without asserting a method, so such endpoints are skipped with
  a logged note (they stay visible through ingest/attack-surface, which
  render the method-less shape).
- ``substantiated: false`` means kosi read none of the code behind the
  declared route. The operation carries ``x-kosi-substantiated: false``
  so a generated document does not silently present an unexamined route
  as an examined clean one — including when a route was discovered
  twice and only one of the two records was substantiated.

kosi's endpoint records carry parameter NAMES, not types, and no request
body type. Parameters are emitted with string schemas and a body is only
indicated through the ``consumes`` media types (empty schema = any), so
the document never asserts a type the engine did not state.
"""

import logging
import re
from copy import deepcopy
from typing import Dict, List, Tuple

from atom_tools.lib.slices import AtomSlice

logger = logging.getLogger(__name__)

# Path placeholder normalisation. Spring/Kotlin routes already use
# ``{id}``; a ``{id:regex}`` pattern (JAX-RS/servlet style) drops the
# regex, a ``:id`` segment-start placeholder becomes ``{id}``, and
# catch-all wildcards become named wildcard parameters.
# The colon rule anchors to a segment start so a literal segment like
# ``/v1/users:batchGet`` is left alone — a mid-segment colon is not a
# placeholder, and converting one would invent a required path
# parameter out of nothing.
_PLACEHOLDER_COLON = re.compile(r"(?<=/):([A-Za-z_][A-Za-z0-9_]*)")
_PLACEHOLDER_REGEX_BRACE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*):[^}]+\}")
# A run of one or more ``*`` — one wildcard, whether servlet-style
# single-segment (``/legacy/*``) or Spring ant-style multi-segment
# (``/legacy/**``). Each run becomes its own placeholder and the names
# are numbered left to right so a path with several wildcards never
# emits a duplicate placeholder name (invalid OpenAPI, and one declared
# parameter standing in for two segments). ``**`` collapses to a single
# placeholder too: OpenAPI path templates cannot express a
# multi-segment wildcard, so its multi-segment reach is approximated,
# never silently widened to "matches everything".
_CATCH_ALL = re.compile(r"\*+")


def normalize_path(path: str) -> str:
    """Convert framework-native path placeholders to OpenAPI ``{name}``.

    Idempotent on Spring-style paths (which already use ``{name}``).
    Repeated wildcards are numbered (``{path}``, ``{path1}``, ...) so
    every placeholder in the result is unique.
    """
    if not path:
        return ""
    path = _PLACEHOLDER_REGEX_BRACE.sub(r"{\1}", path)
    path = _PLACEHOLDER_COLON.sub(r"{\1}", path)
    counter = 0

    def wildcard(_match: re.Match) -> str:
        nonlocal counter
        name = "path" if counter == 0 else f"path{counter}"
        counter += 1
        return "{" + name + "}"

    return _CATCH_ALL.sub(wildcard, path)


def _path_param_names(path: str) -> List[str]:
    """The placeholder names a normalized path template declares."""
    return re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", path)


def _build_operation(endpoint: Dict, path: str) -> Dict:
    """Build one OpenAPI operation object from a kosi endpoint record."""
    handler = endpoint.get("handlerCanonicalName") or endpoint.get("handlerSymbol") or ""
    position = endpoint.get("position") or {}
    file_path = position.get("filename", "") or ""

    operation: Dict = {
        "responses": {"200": {"description": ""}},
    }
    if handler:
        operation["operationId"] = handler

    # Line-number tracking mirrors the golem/rusi converters so callers
    # that inspect x-atom-usages (query-endpoints, visualize) keep
    # working.
    line_number = position.get("line")
    if file_path and isinstance(line_number, int):
        operation["x-atom-usages"] = {"call": {file_path: [line_number]}}

    if framework := endpoint.get("framework"):
        operation["x-kosi-framework"] = framework

    # kosi's declared authentication requirements, verbatim. An empty
    # list is a silence, not an anonymity statement, so it is dropped
    # here rather than rendered as "no auth".
    auth = [a for a in (endpoint.get("authentication") or []) if a]
    if auth:
        operation["x-kosi-authentication"] = auth

    # Path and query parameters. kosi reports names only, so the schema
    # is the honest "string" rather than an invented type. Path
    # parameters come from the template itself (OpenAPI requires every
    # placeholder to have one); kosi's pathParameters are merged in when
    # they name something the template does not.
    known = set(_path_param_names(path))
    parameters = [
        {
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
        for name in known
    ]
    for name in endpoint.get("pathParameters") or []:
        if name and name not in known:
            known.add(name)
            parameters.append(
                {
                    "name": name,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            )
    parameters.extend(
        {
            "name": name,
            "in": "query",
            "schema": {"type": "string"},
        }
        for name in endpoint.get("queryParameters") or []
        if name
    )
    if parameters:
        operation["parameters"] = parameters

    # Consumed media types indicate a request body; kosi carries no body
    # type, so each media type maps to an empty (any) schema.
    consumes = [c for c in (endpoint.get("consumes") or []) if c]
    if consumes:
        operation["requestBody"] = {
            "content": {mt: {"schema": {}} for mt in consumes},
        }

    # Produced media types shape the default 200 response.
    produces = [p for p in (endpoint.get("produces") or []) if p]
    if produces:
        operation["responses"]["200"]["content"] = {mt: {"schema": {}} for mt in produces}

    return operation


# Every HTTP method an OpenAPI path item can carry. A route kosi reports as
# serving ANY method (``anyMethod``: ``@RequestMapping`` without ``method``,
# a servlet filter, Vert.x ``route()``) is expanded to all of them, each
# operation marked so the expansion is never mistaken for eight declarations.
_ALL_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _http_methods(endpoint: Dict) -> List[str]:
    methods = [m.lower() for m in (endpoint.get("httpMethod") or []) if isinstance(m, str) and m]
    if not methods and endpoint.get("anyMethod") is True:
        return list(_ALL_METHODS)
    return [m for m in methods if m in _ALL_METHODS]


def _handler_ref(endpoint: Dict, reason: str) -> Dict:
    """A kosi endpoint that has no place in ``paths``, kept with why."""
    position = endpoint.get("position") or {}
    ref = {
        "handler": endpoint.get("handlerCanonicalName") or endpoint.get("handlerSymbol") or "",
        "framework": endpoint.get("framework") or "",
        "reason": reason,
    }
    for key, value in (
        ("path", endpoint.get("pathTemplate") or ""),
        ("methods", endpoint.get("httpMethod") or []),
        ("transport", endpoint.get("transport") or ""),
        ("file", position.get("filename") or ""),
        ("line", position.get("line")),
        ("pathUnresolved", endpoint.get("pathUnresolved") or ""),
    ):
        if value not in ("", [], None):
            ref[key] = value
    return ref


def classify(usages: AtomSlice) -> Tuple[List[Tuple[Dict, str, List[str]]], Dict[str, List[Dict]]]:
    """Split kosi's endpoints into OpenAPI operations and everything else.

    Returns ``(routes, extensions)``: ``routes`` are ``(endpoint, path,
    methods)`` triples that belong in ``paths``; ``extensions`` holds the
    endpoints that cannot, each under the document-level key that says why,
    so a converted document never loses one silently:

    - ``x-kosi-non-http-endpoints`` — kosi says the transport is not HTTP
      (``transport``: messaging listeners, gRPC, Android components,
      event-triggered cloud functions).
    - ``x-kosi-unmounted-handlers`` — a handler with no path (a Ratpack
      ``Handler`` or Lambda ``RequestHandler`` whose route is bound where
      kosi did not link it; ``pathUnresolved`` says so).
    - ``x-kosi-method-unresolved`` — an HTTP route whose method kosi could
      not resolve and does not report as serving any method.
    - ``x-kosi-unsupported-methods`` — verbs an OpenAPI path item cannot
      carry (``CONNECT``; a custom verb such as WebDAV's ``LOCK``).
    """
    routes: List[Tuple[Dict, str, List[str]]] = []
    extensions: Dict[str, List[Dict]] = {
        "x-kosi-non-http-endpoints": [],
        "x-kosi-unmounted-handlers": [],
        "x-kosi-method-unresolved": [],
        "x-kosi-unsupported-methods": [],
    }
    if not usages or not usages.content:
        return routes, extensions
    for endpoint in usages.content.get("apiEndpoints", []) or []:
        transport = endpoint.get("transport") or ""
        # Android manifest components are not HTTP routes even in reports
        # that predate the transport field: their pathTemplate is an intent
        # action or component name, never a URL path.
        if transport or endpoint.get("foundBy") == "manifest":
            extensions["x-kosi-non-http-endpoints"].append(
                _handler_ref(endpoint, f"served over {transport or 'android'}, not HTTP")
            )
            continue
        raw_path = endpoint.get("pathTemplate", "") or ""
        if not raw_path.startswith("/"):
            extensions["x-kosi-unmounted-handlers"].append(
                _handler_ref(endpoint, endpoint.get("pathUnresolved") or "kosi reported no URL path")
            )
            continue
        path = normalize_path(raw_path)
        methods = _http_methods(endpoint)
        # Verbs an OpenAPI path item has no field for (CONNECT, WebDAV's
        # LOCK via Micronaut's @CustomHttpMethod) are kept, named.
        unsupported = [
            m for m in (endpoint.get("httpMethod") or []) if isinstance(m, str) and m.lower() not in _ALL_METHODS
        ]
        if unsupported:
            extensions["x-kosi-unsupported-methods"].append(
                _handler_ref(endpoint, "OpenAPI has no operation field for " + ", ".join(sorted(unsupported)))
            )
        if not methods and unsupported:
            continue
        if not methods:
            extensions["x-kosi-method-unresolved"].append(
                _handler_ref(endpoint, "kosi resolved no HTTP method at this route")
            )
            continue
        routes.append((endpoint, path, methods))
    return routes, extensions


def convert(usages: AtomSlice) -> Dict[str, Dict]:
    """Convert a kosi report into an OpenAPI ``paths`` dict.

    Mirrors the contract of :func:`atom_tools.lib.go_converter.convert`
    and :func:`atom_tools.lib.rust_converter.convert`: returns a
    ``{path: {method: operation}}`` mapping. The caller (the
    :class:`atom_tools.lib.converter.OpenAPI` class) wraps this into
    the full OpenAPI document and adds :func:`extensions`.
    """
    result: Dict[str, Dict] = {}
    if not usages or not usages.content:
        return result
    if not usages.content.get("apiEndpoints"):
        # Kotlin is the one language where two kinds of input are
        # plausible: a kosi report here, but an ATOM usages slice
        # elsewhere in the same pipeline. An atom slice converted as
        # kotlin yields nothing, and an empty document with no word of
        # why would read as "the app has no endpoints" — so say what
        # happened.
        if usages.content.get("objectSlices"):
            logger.warning(
                "The input carries atom objectSlices, not a kosi apiEndpoints table; "
                "converting it as kotlin produces no endpoints. Pass -t java for "
                "atom slices of Kotlin projects."
            )
        return result

    routes, _ = classify(usages)
    for endpoint, path, methods in routes:
        path_item = result.setdefault(path, {})
        unsubstantiated = endpoint.get("substantiated") is False
        for method in methods:
            operation = _build_operation(endpoint, path)
            # kosi read none of the code behind this declared route, so
            # its silence on flows here means "not looked at", not
            # "clean". Carried per operation, where the record it
            # belongs to is visible.
            if unsubstantiated:
                operation["x-kosi-substantiated"] = False
            if endpoint.get("anyMethod") is True and not endpoint.get("httpMethod"):
                operation["x-kosi-any-method"] = True
            if unresolved := endpoint.get("pathUnresolved"):
                operation["x-kosi-path-unresolved"] = unresolved
            existing = path_item.get(method)
            if existing:
                path_item[method] = _merge_operations(existing, operation)
            else:
                path_item[method] = operation

    return _unique_operation_ids(result)


def extensions(usages: AtomSlice) -> Dict[str, List[Dict]]:
    """The document-level ``x-kosi-*`` lists, only the non-empty ones."""
    _, ext = classify(usages)
    return {key: value for key, value in ext.items() if value}


def _unique_operation_ids(paths: Dict[str, Dict]) -> Dict[str, Dict]:
    """Make every ``operationId`` unique, as OpenAPI requires.

    One kosi handler routinely backs several operations: a method list fans
    out per verb, a repository resource serves GET/POST/PUT/..., a mapping
    names several paths. The first operation (in path, then method order)
    keeps the handler's name; every later one gets ``<handler>_<method>_<path
    slug>``, numbered if that still collides, and the handler stays readable
    in ``x-kosi-handler``.
    """
    seen: set = set()
    for path in sorted(paths):
        for method in sorted(paths[path]):
            operation = paths[path][method]
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            handler = operation["operationId"]
            candidate = handler
            if candidate in seen:
                slug = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_") or "root"
                candidate = f"{handler}_{method}_{slug}"
                counter = 2
                while candidate in seen:
                    candidate = f"{handler}_{method}_{slug}_{counter}"
                    counter += 1
                operation["x-kosi-handler"] = handler
            operation["operationId"] = candidate
            seen.add(candidate)
    return paths


def _merge_operations(existing: Dict, new: Dict) -> Dict:
    """Merge two operations registered against the same path+method.

    Only the ``x-atom-usages.call`` line-number lists concatenate; every
    other field prefers the existing entry, since the records describe
    the same route discovered twice.

    The substantiation verdict is the one exception to
    prefer-the-existing: two records for one route where only one was
    substantiated must not lose the "never read" verdict with the loser,
    so the merged operation carries the flag when EITHER record does.
    The flag is monotonic — merge never clears it.
    """
    merged = deepcopy(existing)
    # Two HANDLERS at one path+method (every GraphQL operation is served at
    # POST /graphql; one route declared in two app modules) keep both names.
    if new.get("operationId") and new.get("operationId") != existing.get("operationId"):
        handlers = merged.setdefault("x-kosi-handlers", [h for h in [existing.get("operationId")] if h])
        if new["operationId"] not in handlers:
            handlers.append(new["operationId"])
    unsubstantiated = (
        new.get("x-kosi-substantiated") is False or existing.get("x-kosi-substantiated") is False
    )
    if unsubstantiated:
        merged["x-kosi-substantiated"] = False
    # A verb one record DECLARES is not an any-method expansion, whichever
    # record arrived first; an unproven base path is never cleared by a
    # record that happens to lack the note.
    if not (existing.get("x-kosi-any-method") and new.get("x-kosi-any-method")):
        merged.pop("x-kosi-any-method", None)
    if not merged.get("x-kosi-path-unresolved") and new.get("x-kosi-path-unresolved"):
        merged["x-kosi-path-unresolved"] = new["x-kosi-path-unresolved"]
    new_calls = new.get("x-atom-usages", {}).get("call", {})
    if new_calls:
        existing_calls = merged.setdefault("x-atom-usages", {}).setdefault("call", {})
        for file_path, line_numbers in new_calls.items():
            bucket = existing_calls.setdefault(file_path, [])
            for line_number in line_numbers:
                if line_number not in bucket:
                    bucket.append(line_number)
    return merged
