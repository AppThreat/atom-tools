"""Adapter for kosi reports (Kotlin/JVM).

kosi (the Kotlin Source Inspector) emits one camelCase envelope — closer to
golem than to dosai's several commands — with ``schemaVersion: "kosi/1"`` and
a ``tool`` object. ``dataFlow.slices[]`` reference ``dataFlow.nodes`` by id
(the ``dfn-*`` id space, separate from the ``callGraph`` id space). Slices
carry an explicit severity (critical/high/medium/low) and confidence, so
``severity_source="engine"``, like dosai and golem.

Envelope honesty, read off the wire rather than the Kotlin data classes (the
writer in ``KosiReport.kt`` is the contract, and it diverges from the data
class in both directions):

- ``runtime`` is declared on ``KosiReport`` but the JSON writer never emits
  it — a report has 18 top-level keys, not the 19 the data class declares.
- ``callGraph`` and ``dataFlow`` are emitted as explicit ``null`` when their
  modes did not run. ``null`` is not-computed, the same distinction the
  ``graph`` command draws; neither is folded into an empty section.
- ``ApiEndpoint.httpMethods`` (plural, on the data class) is written as
  ``httpMethod`` (singular). Field names here are checked against real
  report bytes, not the schema sources.

The committed fixtures were produced by the 0.2.0 binary (commit
``2e1f7b53``), which predates the P22 schema rework: slices carry
``reachableFromRoots``/``rootWitness``/``elided`` and no ``pathKind``/``frames``/
``framesCutBy``. Every one of those is read when present and never assumed,
so a newer kosi report parses unchanged (see ``path_truncated`` below).
kosi is pre-1.0 and moving; ``schemaVersion`` is the pin, not the shape.
"""

import logging
from typing import Dict, List, Optional, Tuple

from atom_tools.lib import taxonomy
from atom_tools.lib.unified import (
    UnifiedFlow,
    UnifiedNode,
    UnifiedReport,
    check_schema_version,
    hydrate,
)

logger = logging.getLogger(__name__)

ENGINE = "kosi"
SUPPORTED_SCHEMA = "kosi/1"


def detect(content) -> bool:
    """True for kosi reports carrying a flow or endpoint section."""
    tool = content.get("tool") if isinstance(content, dict) else None
    return (
        isinstance(tool, dict)
        and tool.get("name") == "kosi"
        and ("dataFlow" in content or "apiEndpoints" in content)
    )


def _node(raw: Dict, role: str) -> UnifiedNode:
    position = raw.get("position") or {}
    return UnifiedNode(
        name=raw.get("name") or "",
        code=raw.get("name") or "",
        file=position.get("filename") or raw.get("filePath") or "",
        line=position.get("line") if isinstance(position.get("line"), int) else None,
        column=position.get("column") if isinstance(position.get("column"), int) else None,
        package=raw.get("modulePath") or None,
        purl=raw.get("purl") or None,
        role=role,
    )


# kosi's declared-requirement vocabulary, read off EndpointDetector.kt /
# WebXmlParser.kt / Endpoints.kt and confirmed against real reports:
#   role(<r>)                          a route-level role requirement
#   security-constraint(<roles>)       web.xml constraint naming roles
#   security-constraint(authenticated) web.xml roles "*" — any authenticated principal
#   security-constraint(denied)        web.xml deny-all — a refusal, not a login
#   auth-handler(<scheme>)             an authentication handler chained onto the route
#   meta-security(...) / contract-security(...)
#                                      http4k security assignments
#   <scheme>                           a declared scheme with no parameters
KOSI_DENY = "security-constraint(denied)"


def _exposure(ep: Dict) -> Tuple[Optional[str], Optional[bool], str]:
    """Tier an endpoint from kosi's own declarations, and nothing else.

    The discipline this follows (kosi's docs say it, and the tier system
    exists to enforce it): **an empty declaration is not a denial.**
    ``authentication: []`` means no requirement was declared at a site kosi
    models — a filter kosi does not model may still guard the route — so an
    empty list must never become ``anonymous-http``; it stays ``unknown-auth``
    via the kind path.

    What a non-empty declaration *is* decides the mapping:

    - ``security-constraint(denied)`` is a **deny rule**. Matching on
      "security-constraint" would call a route that rejects everyone
      "authenticated"; instead a deny maps to ``internal`` — the
      least-exposed tier, and the honest sentence: nothing external may
      reach this endpoint at all. The full string is matched, so a
      hypothetical role literally named "denied" cannot hit this branch.
    - ``exported: false`` is a positive engine statement (the component is
      not externally launchable) and maps to ``internal``. ``exported:
      true`` says reachable, which is not anonymous, so it maps to nothing.
    - every other declaration is a positive requirement and maps to
      ``authenticated-http``.

    Returns (tier or None, allow_anonymous or None, evidence text). The
    evidence string is what the tier is traceable to — never a guess.
    """
    auth = [a for a in (ep.get("authentication") or []) if isinstance(a, str)]
    exported = ep.get("exported")
    deny = any(a == KOSI_DENY for a in auth)
    if deny:
        return (
            "internal",
            False,
            f"declares a deny rule ({KOSI_DENY}): no caller may reach this endpoint",
        )
    if exported is False:
        return (
            "internal",
            None,
            "records the component as not exported (not externally launchable)",
        )
    if auth:
        return (
            "authenticated-http",
            False,
            "declares " + ", ".join(sorted(set(auth))),
        )
    return None, None, ""


def _endpoint(ep: Dict) -> List[Dict]:
    """One kosi ApiEndpoint as one or more unified endpoint dicts.

    kosi records the served methods as a list on a single endpoint record;
    every other engine's endpoint carries one method. A route serving GET and
    POST is two exposures, so the list fans out — one dict per method, each
    keeping the verbatim record under ``raw``. An empty list is NOT "any
    method": it means no method was resolved at a site kosi models (the
    android manifest components never have one, and a dsl route whose method
    register did not fold keeps none), so it stays method-less and is flagged
    ``methodUnresolved`` — attack-surface renders that as the path alone
    rather than asserting its own "ANY".
    """
    methods = [m for m in (ep.get("httpMethod") or []) if isinstance(m, str)]
    position = ep.get("position") or {}
    exposure, allow_anonymous, evidence = _exposure(ep)
    # Only the dsl/annotation/descriptor findings name HTTP routes; the
    # manifest ones are android components (framework "android") and saying
    # "http-route" over them would be our word contradicting the framework
    # printed beside it.
    kind = "" if ep.get("foundBy") == "manifest" else "http-route"
    base = {
        "path": ep.get("pathTemplate"),
        "kind": kind,
        "framework": ep.get("framework"),
        "handler": ep.get("handlerCanonicalName") or ep.get("handlerSymbol") or None,
        "file": position.get("filename") or "",
        "line": position.get("line") if isinstance(position.get("line"), int) else None,
        "package": ep.get("modulePath") or "",
        "purl": ep.get("purl") or None,
        "id": ep.get("id"),
        "raw": ep,
        # The tier kosi's own declarations support, or absent when they say
        # nothing (attack-surface then renders unknown-auth, its honest gap).
        **({"exposure": exposure} if exposure else {}),
        **({"exposureEvidence": evidence} if evidence else {}),
        **({"allowAnonymous": allow_anonymous} if allow_anonymous is not None else {}),
        **({} if methods else {"methodUnresolved": True}),
    }
    if not methods:
        return [{**base, "method": None}]
    return [{**base, "method": method} for method in methods]


def parse(content, source_file: str = "") -> UnifiedReport:
    """Normalise a kosi report into a unified report."""
    tool = content.get("tool") or {}
    options = content.get("options") or {}
    # kosi degrades quietly: a thin report often has one diagnostics entry as
    # the only trace of why (a syntax-backend run, a missing JDK module).
    # Passing them through is what keeps "found nothing" from reading as the
    # engine's verdict when it is really "ran degraded".
    diagnostics: List[str] = [
        f"{d.get('code')}: {d.get('message')}" if d.get("code") else d.get("message") or str(d)
        for d in content.get("diagnostics") or []
        if isinstance(d, dict)
    ]
    check_schema_version(ENGINE, content.get("schemaVersion", ""), SUPPORTED_SCHEMA, diagnostics)
    # kosi's own degradation contract: an analysis that hit its wall-clock or
    # RSS budget says so in stats.degraded, and the caps it hit are counted in
    # stats.truncations. A report that stopped early must not read as a
    # complete one.
    stats = content.get("stats") or {}
    if isinstance(stats.get("degraded"), str) and stats["degraded"]:
        diagnostics.append(f"kosi degraded this run: {stats['degraded']}")
    truncations = stats.get("truncations")
    if isinstance(truncations, dict) and truncations:
        capped = ", ".join(f"{k} {v}" for k, v in sorted(truncations.items()))
        diagnostics.append(f"kosi hit analysis caps: {capped}")

    # kosi emits an explicit null when the dataflow mode did not run.
    data_flow = content.get("dataFlow") or {}
    mode = data_flow.get("mode") or "none"

    nodes_by_id = {n.get("id"): n for n in data_flow.get("nodes") or []}
    flows: List[UnifiedFlow] = []
    dropped_ids: List[str] = []
    dropped_flows = 0
    for sl in data_flow.get("slices") or []:
        id_order = sl.get("nodeIds") or [sl.get("sourceId"), sl.get("sinkId")]
        missing: List[str] = []
        hydrated = hydrate(sl.get("id", ""), [i for i in id_order if i], nodes_by_id, missing)
        if missing:
            dropped_ids.extend(missing)
            dropped_flows += 1
            continue
        nodes = [_node(n, "step") for n in hydrated]
        for node, raw in zip(nodes, hydrated):
            if raw.get("kind") == "source":
                node.role = "source"
            elif raw.get("kind") == "sink":
                node.role = "sink"
        # kosi records the categories on the slice, not on its nodes; the
        # engines whose nodes carry their own category (dosai/golem/rusi) get
        # tag-driven consumers for free. Carrying them on the terminal nodes
        # here is the same fact, from the only place kosi states it.
        if nodes:
            if sl.get("sourceCategory"):
                nodes[0].tags = [sl["sourceCategory"]]
            if sl.get("sinkCategory"):
                nodes[-1].tags = [sl["sinkCategory"]]
        level = taxonomy.normalise_engine_severity(sl.get("severity"))
        severity_source = "engine" if level else "derived"
        if not level:
            level, _ = taxonomy.derive_level_and_tag(
                sl.get("sourceCategory"), sl.get("sinkCategory")
            )
        purls = [p for p in sl.get("purls") or [] if isinstance(p, str)]
        # Witness honesty: the 0.2.0 binary flags a cut walk with ``elided``
        # and carries no ``pathKind``; the P22+ schema replaces that with
        # pathKind "partial"/"symbol-only" and framesCutBy. Read both
        # spellings; a path that was never walked (symbol-only) is not a
        # truncated one — it is a different, weaker claim.
        path_kind = sl.get("pathKind")
        path_truncated = (
            bool(sl.get("elided"))
            or sl.get("framesCutBy") is not None
            or path_kind == "partial"
        )
        extra: Dict = {
            k: sl[k]
            for k in (
                "flowKey",
                "ruleId",
                "ruleName",
                "riskScore",
                "sourcePurl",
                "targetPurl",
                "accessPath",
                "origins",
                "crossesModule",
                "crossesDependency",
                "sourceName",
                "sinkName",
                "sourceModulePath",
                "sinkModulePath",
                "edgeIds",
            )
            if sl.get(k)
        }
        if sl.get("sinkArgumentIndex") is not None:
            # 0 is a real argument position and must survive the truthiness
            # filter the other extras use.
            extra["sinkArgumentIndex"] = sl["sinkArgumentIndex"]
        if sl.get("pathLength") is not None:
            extra["pathLength"] = sl["pathLength"]
        flows.append(
            UnifiedFlow(
                id=sl.get("id", ""),
                nodes=nodes,
                source_category=sl.get("sourceCategory") or "",
                sink_category=sl.get("sinkCategory") or "",
                severity=level or "note",
                severity_source=severity_source,
                confidence=(sl.get("confidence") or "").lower() or None,
                taint_kinds=list(sl.get("taintKinds") or []),
                purls=purls,
                sanitized=bool(sl.get("sanitizerNodeIds")),
                path_truncated=path_truncated,
                engine=ENGINE,
                engine_version=tool.get("version", ""),
                analysis_mode=mode,
                raw=sl,
                extra=extra,
            )
        )

    if dropped_flows:
        message = (
            f"Dropped {dropped_flows} kosi slice(s) with unresolvable node ids: "
            f"{sorted(set(dropped_ids))[:5]}"
        )
        logger.warning(message)
        diagnostics.append(message)

    packages = [
        {
            "purl": p.get("purl"),
            "reachable": None,
            "kind": None,
            "confidence": None,
        }
        for p in content.get("packages") or []
        if isinstance(p, dict) and p.get("purl")
    ]
    # The engine's evidence tables (modules/files/imports/declarations/usages/
    # securitySignals/services/urls) are raw material no current command reads;
    # they survive in ``raw`` flows/endpoints and in the source document.
    provenance = {
        "engine": ENGINE,
        "engine_version": tool.get("version", ""),
        "schema_version": content.get("schemaVersion", ""),
        "analysis_mode": mode,
        "severity": "engine",
        "backend": options.get("backend"),
        "callgraph_mode": (content.get("callGraph") or {}).get("mode") if content.get("callGraph") else None,
        "roots": options.get("roots"),
    }
    if isinstance(stats.get("degraded"), str) and stats["degraded"]:
        provenance["degraded"] = stats["degraded"]
    if isinstance(truncations, dict) and truncations:
        provenance["truncations"] = dict(truncations)
    return UnifiedReport(
        engine=ENGINE,
        engine_version=tool.get("version", ""),
        schema_version=content.get("schemaVersion", ""),
        analysis_mode=mode,
        source_file=source_file,
        flows=flows,
        endpoints=[ep for raw_ep in content.get("apiEndpoints") or [] for ep in _endpoint(raw_ep)],
        packages=packages,
        diagnostics=diagnostics,
        provenance=provenance,
    )
