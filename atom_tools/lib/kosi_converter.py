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
  declared route. The path item carries ``x-kosi-substantiated: false``
  so a generated document does not silently present an unexamined route
  as an examined clean one.

kosi's endpoint records carry parameter NAMES, not types, and no request
body type. Parameters are emitted with string schemas and a body is only
indicated through the ``consumes`` media types (empty schema = any), so
the document never asserts a type the engine did not state.
"""

import logging
import re
from typing import Dict, List

from atom_tools.lib.slices import AtomSlice

logger = logging.getLogger(__name__)

# Path placeholder normalisation. Spring/Kotlin routes already use
# ``{id}``; a ``{id:regex}`` pattern (JAX-RS/servlet style) drops the
# regex, a ``:id`` segment becomes ``{id}``, and a servlet catch-all
# ``*`` segment becomes a named single-segment-wildcard parameter.
_PLACEHOLDER_COLON = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_PLACEHOLDER_REGEX_BRACE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*):[^}]+\}")
_CATCH_ALL = re.compile(r"\*")


def normalize_path(path: str) -> str:
    """Convert framework-native path placeholders to OpenAPI ``{name}``.

    Idempotent on Spring-style paths (which already use ``{name}``).
    """
    if not path:
        return ""
    path = _PLACEHOLDER_REGEX_BRACE.sub(r"{\1}", path)
    path = _PLACEHOLDER_COLON.sub(r"{\1}", path)
    return _CATCH_ALL.sub("{path}", path)


def _path_param_names(path: str) -> List[str]:
    """The placeholder names a normalized path template declares."""
    return re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", path)


def _build_operation(endpoint: Dict, http_method: str, path: str) -> Dict:
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


def convert(usages: AtomSlice) -> Dict[str, Dict]:
    """Convert a kosi report into an OpenAPI ``paths`` dict.

    Mirrors the contract of :func:`atom_tools.lib.go_converter.convert`
    and :func:`atom_tools.lib.rust_converter.convert`: returns a
    ``{path: {method: operation}}`` mapping. The caller (the
    :class:`atom_tools.lib.converter.OpenAPI` class) wraps this into
    the full OpenAPI document.
    """
    result: Dict[str, Dict] = {}
    if not usages or not usages.content:
        return result
    endpoints = usages.content.get("apiEndpoints", [])
    if not endpoints:
        return result

    for endpoint in endpoints:
        # Android manifest components are not HTTP routes: their
        # pathTemplate is an intent action or component name, never a
        # URL path.
        if endpoint.get("foundBy") == "manifest":
            continue
        raw_path = endpoint.get("pathTemplate", "") or ""
        if not raw_path.startswith("/"):
            continue
        path = normalize_path(raw_path)
        if not path:
            continue

        methods = [
            m.lower() for m in (endpoint.get("httpMethod") or []) if isinstance(m, str) and m
        ]
        if not methods:
            # Method unresolved at a site kosi models. OpenAPI cannot
            # carry a route without asserting a method, so say so and
            # move on rather than inventing one.
            logger.debug(
                "kosi endpoint %s (%s) has no resolved HTTP method; "
                "skipped in the OpenAPI document",
                endpoint.get("id"),
                raw_path,
            )
            continue

        path_item = result.setdefault(path, {})
        unsubstantiated = endpoint.get("substantiated") is False
        for method in methods:
            operation = _build_operation(endpoint, method, path)
            # kosi read none of the code behind this declared route, so
            # its silence on flows here means "not looked at", not
            # "clean". Carried per operation, where the record it
            # belongs to is visible.
            if unsubstantiated:
                operation["x-kosi-substantiated"] = False
            existing = path_item.get(method)
            if existing:
                path_item[method] = _merge_operations(existing, operation)
            else:
                path_item[method] = operation

    return result


def _merge_operations(existing: Dict, new: Dict) -> Dict:
    """Merge two operations registered against the same path+method.

    Only the ``x-atom-usages.call`` line-number lists concatenate; every
    other field prefers the existing entry, since the records describe
    the same route discovered twice.
    """
    merged = dict(existing)
    new_calls = new.get("x-atom-usages", {}).get("call", {})
    if new_calls:
        existing_calls = merged.setdefault("x-atom-usages", {}).setdefault("call", {})
        for file_path, line_numbers in new_calls.items():
            bucket = existing_calls.setdefault(file_path, [])
            for line_number in line_numbers:
                if line_number not in bucket:
                    bucket.append(line_number)
    return merged
