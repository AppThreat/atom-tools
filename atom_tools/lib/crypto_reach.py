"""Crypto inventory joined to entry-point reachability.

cdxgen can tell you MD5 is present; nothing tells you whether the MD5 call
site sits on a flow reachable from an entry point. That join — attack-surface
∩ crypto — is what this module computes, and the honest answer has to be
per-engine because the three engines that emit crypto evidence leave the join
at three different granularities (all measured against the committed fixtures
in ``test/data/ecosystem/``):

**dosai already did the join.** Its ``crypto`` command carries
``ReachableFromEntryPoint`` / ``EntryPointIds`` / ``DataFlowSliceIds`` on every
asset, operation, material and finding (``Dosai/CryptoAnalysis.cs``), computed
over the engine's full run. Nothing is derived here: the verdict is rendered
verbatim and the join is labeled ``engine`` — the same distinction
``severity_source`` makes for flows. On the eShopOnWeb fixture the engine's
crypto verdict for ``GetTokenAsync`` names the same two entry-point ids as the
engine's own ``Reachability`` array in the methods report for the same method,
which is the strongest cross-check available and the reason a re-derivation
would only be worse.

**rusi joins at function grain.** Its crypto materials carry ``function``, the
fully-qualified enclosing function, and all 17 anchor in the call graph by
``qualified_name``. Reachability is *derived*: a material is inside the callee
closure of an anchored endpoint handler or it is not — and on the committed
fixture 0 of 17 are, because they hang off event dispatchers, ``main`` and
background listeners instead of HTTP handlers. That is an answer, not a
failure, and the static callers are printed so a reader can see what the
material actually hangs off.

**golem joins at package grain at best.** Its crypto items carry no
enclosing-function field — only ``packagePath`` and ``symbol`` — and crypto
sites are recorded where the algorithm is used while flow nodes sit at
source/sink/step boundaries, so positional joins are near-empty by
construction (0 exact ``file:line`` hits for the 9 assets, 1 for 323
operations). The claim a package-level join supports is *this weak-SHA1 site
sits in a package that carries tainted flows*, which is materially weaker
than *this MD5 call is on a tainted path* — the renderings say the weaker
sentence, every time.

**kosi splits by record kind, and the label says so.** Its crypto operations
carry the enclosing function (``function``) and join at function grain, the
same way rusi's materials do. Its materials and findings carry only a file
position — no enclosing function, no package — so they join at file grain:
*a tainted flow runs through this file*, the middle rung between function and
package, stated as exactly that. Its assets, protocols and libraries carry no
location of any kind (assets name algorithms and primitives; protocols and
libraries are bare strings) and are inventory only — there is nothing to
join on, and the rendering says that instead of inventing a package.

**rusi's zeros are coverage statements, not findings.** Its components come
from a hard-coded symbol catalog (SHA-256/512/1, MD5, BLAKE3, ring, AES-GCM,
ChaCha20-Poly1305, PBKDF2, JWT, TLS, RSA, Ed25519 —
``classify_stable_crypto_call`` in ``crates/rusi-core/src/lib.rs``), findings
are emitted only from those components, the section-level
``crypto.properties`` has no writer in the crate, and there is no ``strength``
field anywhere: the only weak-crypto signal is ``category == "weak-crypto"``
from exactly two rules (SHA-1 and MD5). DES, RC4 and ECB are not modeled, so
for rusi the honest sentence is "rusi does not look for this", never "rusi
found nothing".

**atom emits no crypto section of any kind**; an atom input is reported as
out of scope rather than folded into an empty report. Crypto also stays
*engine-side* rather than entering the unified model — the unified document
carries no crypto payload by design, so ``crypto-reach -i unified.json`` says
precisely that instead of quietly computing nothing.

No single headline number crosses engines: a "N weak crypto sites are
reachable" total computed over an engine verdict, a function join and a
package join would be exactly the category of statistic Phase 2 had to fix
once already.
"""

import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from atom_tools.lib import taxonomy

logger = logging.getLogger(__name__)

CRYPTO_REACH_VERSION = 1

# Join provenance, mirroring severity_source / depth_source.
JOIN_ENGINE = "engine"  # the engine's own reachability verdict (dosai)
JOIN_DERIVED = "derived"  # our join over the engine's call graph / flows

# Join granularity per engine: dosai's records carry their own verdict,
# rusi's materials an enclosing function, golem's items only a package, and
# kosi's per record kind — operations a function, materials and findings a
# file, the rest nothing (the block label lists the grains actually used).
GRANULARITIES = {"dosai": "record", "rusi": "function", "golem": "package", "kosi": "function"}
GRANULARITY_PACKAGE = "package"
GRANULARITY_FUNCTION = "function"
GRANULARITY_FILE = "file"

# Strength vocabularies observed in the fixtures. Neither engine declares
# these as an enum — they are string literals in rule tables — so an
# unobserved value warns and continues rather than hard-failing, the rule the
# adapters already follow for schemaVersion. dosai's `legacy` tier has no
# equivalent in golem and both belong to the triage population.
ATTENTION_STRENGTHS = ("weak", "legacy")
KNOWN_STRENGTHS = ("strong", "acceptable", "weak", "legacy")

# golem's literal-material findings are inventory (hardcoded secret strings,
# 133 of 146 findings on the fixture); everything else is the triage payload.
LITERAL_MATERIAL = "LITERAL-MATERIAL"

RUSI_SYMBOL_CATALOG = (
    "SHA-256/512/1, MD5, BLAKE3, ring digest/aead, AES-GCM,"
    " ChaCha20-Poly1305, PBKDF2, JWT (jsonwebtoken), TLS (rustls), RSA,"
    " Ed25519, Argon2"
)

# Ranking keeps the engine's own word, not the folded level: critical and
# high both fold to error, but a critical finding must not list below a high
# one. dosai's Pascal-casing folds case-insensitively.
SEVERITY_WORD_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "moderate": 2,
    "low": 3,
    "info": 4,
    "informational": 4,
}


@dataclass
class CryptoItem:
    """One crypto record from an engine's inventory, with its reach verdict."""

    engine: str
    kind: str  # asset | operation | material | protocol | finding | library
    id: str
    name: str = ""
    algorithm: str = ""
    strength: Optional[str] = None  # verbatim; rusi has none
    severity: str = ""  # verbatim engine spelling (dosai's "High" stays "High")
    severity_level: str = ""  # folded onto error/warning/note, for ranking
    confidence: str = ""
    rule_id: str = ""
    cwe: str = ""
    package: str = ""
    file: str = ""
    line: Optional[int] = None
    function: str = ""  # rusi materials only
    attention: bool = False  # weak/legacy strength or a weak-crypto rule
    # The join verdict; always carries ``granularity`` and ``source``.
    reach: Dict = field(default_factory=dict)
    raw: Dict = field(default_factory=dict)

    def rank_key(self) -> Tuple:
        return (
            0 if self.attention else 1,
            SEVERITY_WORD_RANK.get((self.severity or "").strip().lower(), 5),
            self.kind,
            self.id or f"{self.file}:{self.line}",
        )

    def to_dict(self) -> Dict:
        return {
            "Engine": self.engine,
            "Kind": self.kind,
            "Id": self.id,
            "Name": self.name or None,
            "Algorithm": self.algorithm or None,
            "Strength": self.strength,
            "Severity": self.severity or None,
            "SeverityLevel": self.severity_level or None,
            "Confidence": self.confidence or None,
            "RuleId": self.rule_id or None,
            "Cwe": self.cwe or None,
            "Package": self.package or None,
            "File": self.file or None,
            "LineNumber": self.line,
            "Function": self.function or None,
            "Attention": self.attention or None,
            "Reach": dict(self.reach),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CryptoItem":
        return cls(
            engine=data.get("Engine") or "",
            kind=data.get("Kind") or "",
            id=data.get("Id") or "",
            name=data.get("Name") or "",
            algorithm=data.get("Algorithm") or "",
            strength=data.get("Strength"),
            severity=data.get("Severity") or "",
            severity_level=data.get("SeverityLevel") or "",
            confidence=data.get("Confidence") or "",
            rule_id=data.get("RuleId") or "",
            cwe=data.get("Cwe") or "",
            package=data.get("Package") or "",
            file=data.get("File") or "",
            line=data.get("LineNumber"),
            function=data.get("Function") or "",
            attention=bool(data.get("Attention")),
            reach=data.get("Reach") or {},
        )


def _range_start(holder: Any) -> Dict:
    """The position dict a golem range/rusi position starts from."""
    if not isinstance(holder, dict):
        return {}
    if isinstance(holder.get("start"), dict):
        return holder["start"]
    return holder


def _is_attention(kind: str, strength: Optional[str], rule_id: str, category: str = "") -> bool:
    if isinstance(strength, str) and strength.strip().lower() in ATTENTION_STRENGTHS:
        return True
    if kind == "finding" and LITERAL_MATERIAL not in (rule_id or "").upper():
        return True
    if category == "weak-crypto":  # rusi's only weak signal
        return True
    return False


def _unknown_strength(engine: str, strength: Any, label: str) -> Optional[str]:
    if strength is None or not isinstance(strength, str):
        return None
    if strength.strip().lower() in KNOWN_STRENGTHS:
        return None
    return (
        f"unrecognised {engine} crypto strength '{strength}' on {label};"
        " carried verbatim"
    )


# -- dosai: the engine's own verdict, verbatim ----------------------------------


def _dosai_crypto(raw: Dict) -> Tuple[List[CryptoItem], Dict[str, int], List[str]]:
    """dosai crypto records with the engine's reachability taken verbatim."""
    diagnostics: List[str] = []
    cdf = raw.get("CryptoDataFlows") or {}
    entry_points = {ep.get("Id"): ep for ep in cdf.get("EntryPoints") or []}
    slice_ids = {s.get("Id") for s in cdf.get("Slices") or []}
    items: List[CryptoItem] = []
    sections: Dict[str, int] = {}
    # Field names checked one by one against Dosai/CryptoAnalysis.cs:34-120.
    # Three of them did not exist: CryptoOperation has OperationType and
    # Algorithm but no "Operation", so every operation fell back to rendering
    # its opaque id ("operation cop1" for a weak DES/RC2/RC4 use); CryptoAsset
    # and CryptoProtocol have no "Algorithm"/"Protocol" field at all. Reading a
    # key an engine does not publish is indistinguishable from the engine
    # leaving it empty, which is exactly the confusion this command exists to
    # avoid -- so a field that does not exist is None here, not a guess.
    specs = (
        ("asset", "Assets", "Name", None, "Strength"),
        ("operation", "Operations", None, "Algorithm", None),
        ("material", "Materials", "Name", "Algorithm", None),
        ("protocol", "Protocols", "Name", None, "Strength"),
        ("finding", "Findings", "Summary", None, None),
    )
    for kind, section, name_key, algo_key, strength_key in specs:
        records = raw.get(section) or []
        sections[section] = len(records)
        for record in records:
            location = record.get("Location") or {}
            strength = record.get(strength_key) if strength_key else None
            rule_id = record.get("RuleId") or ""
            severity = record.get("Severity") or ""
            warning = _unknown_strength("dosai", strength, record.get("Id") or "?")
            if warning:
                diagnostics.append(warning)
            name = record.get(name_key) or "" if name_key else ""
            if kind == "operation":
                # An operation's two identifying fields are what it does and
                # what with; neither alone reads as anything.
                name = " ".join(
                    p for p in (record.get("OperationType"), record.get("Algorithm")) if p
                )
            items.append(
                CryptoItem(
                    engine="dosai",
                    kind=kind,
                    id=record.get("Id") or "",
                    name=name,
                    algorithm=(record.get(algo_key) or "") if algo_key else "",
                    strength=strength if isinstance(strength, str) else None,
                    severity=severity,
                    severity_level=taxonomy.normalise_engine_severity(severity) or "",
                    confidence=(record.get("Confidence") or ""),
                    rule_id=rule_id,
                    cwe=record.get("Cwe") or "",
                    file=location.get("Path") or location.get("FileName") or "",
                    line=location.get("LineNumber"),
                    attention=_is_attention(kind, strength, rule_id),
                    reach=_dosai_reach(record, entry_points, slice_ids),
                    raw=record,
                )
            )
    return items, sections, diagnostics


def _dosai_reach(record: Dict, entry_points: Dict, slice_ids: set) -> Dict:
    """The engine's per-record reachability, resolved onto routes and slices."""
    entry_refs = []
    for ep_id in record.get("EntryPointIds") or []:
        ep = entry_points.get(ep_id)
        if ep is None:
            entry_refs.append({"id": ep_id, "resolved": False})
            continue
        route = ep.get("Route")
        entry_refs.append(
            {
                "id": ep_id,
                "resolved": True,
                "label": (
                    f"{ep.get('HttpMethod') or 'ANY'} {route}"
                    if route
                    else ".".join(
                        p for p in (ep.get("Namespace"), ep.get("ClassName"), ep.get("MethodName")) if p
                    )
                    or ep.get("MethodId")
                    or ep_id
                ),
                "kind": ep.get("Kind"),
                "file": ep.get("Path") or ep.get("FileName"),
                "line": ep.get("LineNumber"),
                "authorizationRequired": ep.get("AuthorizationRequired"),
            }
        )
    return {
        "granularity": GRANULARITIES["dosai"],
        "source": JOIN_ENGINE,
        "reachableFromEntryPoint": record.get("ReachableFromEntryPoint"),
        "entryPoints": entry_refs,
        "dataFlowSliceIds": sorted(s for s in record.get("DataFlowSliceIds") or [] if s in slice_ids),
        "methodId": record.get("MethodId") or None,
    }


# -- golem: a package-level join, stated as exactly that ------------------------


def _golem_crypto(
    raw: Dict, report, surface: Dict, graph
) -> Tuple[List[CryptoItem], Dict[str, int], List[str]]:
    """golem crypto records joined to flows and endpoints at package grain.

    ``report`` is the parsed unified report (flows and their node packages),
    ``surface`` the attack-surface document (per-endpoint attached flows) and
    ``graph`` the loaded call graph (the engine's own root verdicts), each
    from the same input file.
    """
    crypto = raw.get("crypto") or {}
    sections = {
        section: len(crypto.get(section) or [])
        for section in ("libraries", "assets", "operations", "materials", "protocols", "findings")
    }
    flows_by_package: Dict[str, List[str]] = defaultdict(list)
    for flow in report.flows:
        for package in {n.package for n in flow.nodes if n.package}:
            flows_by_package[package].append(flow.id)
    flows_by_id = {f.id: f for f in report.flows}
    endpoints_by_package: Dict[str, List[str]] = defaultdict(list)
    for tier in surface.get("tiers") or []:
        for entry in tier.get("EntryPoints") or []:
            if entry.get("Engine") != "golem":
                continue
            label = (
                f"{entry.get('HttpMethod') or 'ANY'} {entry.get('Route')}"
                if entry.get("Route")
                else (entry.get("Handler") or entry.get("EntryPointId") or "")
            )
            for flow_id in (entry.get("Reach") or {}).get("flowIds") or []:
                flow = flows_by_id.get(flow_id)
                if flow is None:
                    continue
                for package in {n.package for n in flow.nodes if n.package}:
                    if label not in endpoints_by_package[package]:
                        endpoints_by_package[package].append(label)
    # The engine's own liveness verdict, aggregated at the only grain golem's
    # crypto items support: package. A package whose nodes are all
    # unreachable-from-roots is dead per the engine even when a flow passes
    # through it, and both facts are worth having.
    root_reachable: Dict[str, int] = defaultdict(int)
    root_total: Dict[str, int] = defaultdict(int)
    if graph is not None:
        for node in graph.nodes:
            if node.package:
                root_total[node.package] += 1
                if node.reachable_from_roots:
                    root_reachable[node.package] += 1

    def join(package: str) -> Dict:
        flow_ids = sorted(set(flows_by_package.get(package) or []))
        endpoint_labels = sorted(endpoints_by_package.get(package) or [])
        reach: Dict = {
            "granularity": GRANULARITY_PACKAGE,
            "source": JOIN_DERIVED,
            "package": package or None,
            "packageOnFlow": bool(flow_ids),
            "flowsThroughPackage": len(flow_ids),
            "flowIds": flow_ids[:20],
            # The rung the evidence supports, spelled out so no rendering has
            # to improvise a stronger one.
            "claim": (
                "the crypto site sits in a package that carries tainted flows"
                " — not that the crypto call itself is on a tainted path"
            ),
        }
        if endpoint_labels:
            reach["flowsThroughPackageReachEndpoints"] = endpoint_labels
        if graph is not None and package in root_total:
            reach["engineRootVerdict"] = {
                "reachableNodesInPackage": root_reachable.get(package, 0),
                "nodesInPackage": root_total[package],
                "rootsTotal": len(graph.engine_roots),
                "rootReasons": dict(graph.engine_root_reasons),
            }
        return reach

    diagnostics: List[str] = []
    items: List[CryptoItem] = []
    specs = (
        ("asset", "assets", "symbol", "primitive"),
        ("operation", "operations", "symbol", "algorithm"),
        ("material", "materials", "symbol", "type"),
        ("protocol", "protocols", "symbol", ""),
        ("finding", "findings", "ruleId", ""),
    )
    for kind, section, name_key, algo_key in specs:
        for record in crypto.get(section) or []:
            start = _range_start(record.get("range"))
            file, line = start.get("filename") or "", start.get("line")
            strength = record.get("strength")
            rule_id = record.get("ruleId") or ""
            severity = record.get("severity") or ""
            label = record.get("symbol") or record.get("id") or "?"
            warning = _unknown_strength("golem", strength, label)
            if warning:
                diagnostics.append(warning)
            items.append(
                CryptoItem(
                    engine="golem",
                    kind=kind,
                    id=record.get("id") or "",
                    name=(rule_id if kind == "finding" else record.get(name_key) or ""),
                    algorithm=(record.get(algo_key) or "") if algo_key else "",
                    strength=strength if isinstance(strength, str) else None,
                    severity=severity,
                    severity_level=taxonomy.normalise_engine_severity(severity) or "",
                    confidence=(record.get("confidence") or ""),
                    rule_id=rule_id,
                    cwe=record.get("cwe") or "",
                    package=record.get("packagePath") or "",
                    file=file,
                    line=line,
                    attention=_is_attention(kind, strength, rule_id),
                    reach=join(record.get("packagePath") or ""),
                    raw=record,
                )
            )
    diagnostics.append(
        "golem's crypto items carry no enclosing-function field — the join is"
        " package-level: 'the site sits in a package that carries tainted"
        " flows', never 'this call is on a tainted path'."
    )
    return items, sections, diagnostics


# -- rusi: a function-level join over its call graph ----------------------------


def _rusi_crypto(
    raw: Dict, report, surface: Dict, graph
) -> Tuple[List[CryptoItem], Dict[str, int], List[str]]:
    """rusi crypto evidence joined at enclosing-function grain.

    Materials carry ``function``; that function is anchored in the call graph
    (the same anchor chain attack-surface uses, imported from there — not a
    second implementation) and tested against every anchored endpoint's
    callee closure. Libraries and findings carry no function field, so they
    stay at package grain — stated, not smoothed over.
    """
    crypto = raw.get("crypto") or {}
    sections = {
        section: len(crypto.get(section) or [])
        for section in ("libraries", "components", "materials", "findings")
    }
    closures: List[Tuple[str, set]] = []  # (endpoint label, closure node ids)
    from atom_tools.lib.attack_surface import _rusi_call_graph

    loaded = _rusi_call_graph(raw)
    if loaded and graph is not None:
        mini, _ = loaded
        for tier in surface.get("tiers") or []:
            for entry in tier.get("EntryPoints") or []:
                if entry.get("Engine") != "rusi":
                    continue
                endpoint = {
                    "handler": entry.get("Handler"),
                    "package": entry.get("Package"),
                    "file": entry.get("File") or "",
                    "raw": entry.get("raw") or {},
                }
                seeds, _how = mini.anchor(endpoint)
                if seeds:
                    route = entry.get("Route")
                    label = (
                        f"{entry.get('HttpMethod') or 'ANY'} {route}"
                        if route
                        else (entry.get("Handler") or entry.get("EntryPointId") or "")
                    )
                    closures.append((label, set(mini.closure(seeds))))
    items: List[CryptoItem] = []
    diagnostics: List[str] = []

    def function_reach(function: str) -> Dict:
        reach: Dict = {
            "granularity": GRANULARITY_FUNCTION,
            "source": JOIN_DERIVED,
            "function": function or None,
        }
        if graph is None or not function:
            reach["state"] = "not-computed"
            reach["reason"] = "no call graph to anchor the function in"
            return reach
        # anchor() refuses ambiguous names; for a reachability question
        # "inside the closure of any same-named node" is the honest reading,
        # so an ambiguous qualified name is accepted rather than reported as
        # absent from the graph.
        anchored = graph.anchor(function) or graph.by_name.get(function) or []
        if not anchored:
            reach["state"] = "function-not-in-graph"
            return reach
        reached_from = sorted(
            label for label, closure in closures if any(n in closure for n in anchored)
        )
        if reached_from:
            reach["state"] = "reachable-from-endpoint"
            reach["endpoints"] = reached_from
            return reach
        reach["state"] = "in-graph-no-endpoint-reach"
        callers = sorted(
            {
                graph.by_id[c].name
                for node_id in anchored
                for c in graph.in_edges.get(node_id, ())
                if c in graph.by_id
            }
        )
        if callers:
            reach["callers"] = callers[:5]
            reach["note"] = (
                "inside the call graph but in no anchored endpoint's closure;"
                " static callers listed — event handlers, main and background"
                " listeners land here, as do functions reached only through"
                " dynamic dispatch"
            )
        else:
            reach["note"] = (
                "anchors in the call graph with no static caller — either"
                " dead, or reached through dynamic dispatch the static graph"
                " does not model"
            )
        return reach

    def package_reach(package: str) -> Dict:
        flow_ids = sorted(
            {
                f.id
                for f in report.flows
                if package and any(n.package == package for n in f.nodes)
            }
        )
        return {
            "granularity": GRANULARITY_PACKAGE,
            "source": JOIN_DERIVED,
            "package": package or None,
            "packageOnFlow": bool(flow_ids),
            "flowsThroughPackage": len(flow_ids),
            "claim": (
                "the item sits in a package that carries tainted flows — not"
                " that the crypto call itself is on a tainted path"
            ),
        }

    for record in crypto.get("materials") or []:
        items.append(
            CryptoItem(
                engine="rusi",
                kind="material",
                id=record.get("id") or "",
                name=record.get("name") or "",
                algorithm=record.get("kind") or "",
                confidence=record.get("confidence") or "",
                package=record.get("package_path") or "",
                file=record.get("file_path") or "",
                line=(record.get("position") or {}).get("line"),
                function=record.get("function") or "",
                attention=False,  # rusi emits neither strength nor findings here
                reach=function_reach(record.get("function") or ""),
                raw=record,
            )
        )
    for record in crypto.get("libraries") or []:
        properties = record.get("properties") or {}
        items.append(
            CryptoItem(
                engine="rusi",
                kind="library",
                id=record.get("id") or "",
                name=record.get("path") or "",
                algorithm=record.get("family") or "",
                confidence=properties.get("confidence") or "",
                package=record.get("package_path") or "",
                file=record.get("file_path") or "",
                line=(record.get("position") or {}).get("line"),
                attention=False,
                reach=package_reach(record.get("package_path") or ""),
                raw=record,
            )
        )
    for record in crypto.get("findings") or []:
        category = record.get("category") or ""
        items.append(
            CryptoItem(
                engine="rusi",
                kind="finding",
                id=record.get("id") or "",
                name=record.get("summary") or "",
                severity=record.get("severity") or "",
                severity_level=taxonomy.normalise_engine_severity(record.get("severity")) or "",
                confidence=record.get("confidence") or "",
                rule_id=category,
                package=record.get("package_path") or "",
                file=record.get("file_path") or "",
                line=(record.get("position") or {}).get("line"),
                attention=_is_attention("finding", None, "", category),
                reach=package_reach(record.get("package_path") or ""),
                raw=record,
            )
        )
    stats = raw.get("stats") or {}
    if stats.get("crypto_component_count") == 0:
        diagnostics.append(
            "rusi's crypto components match a fixed symbol catalog"
            f" ({RUSI_SYMBOL_CATALOG}); zero components means zero catalog"
            " matches, not an absence of crypto — crypto not spelled as one"
            " of those symbols is invisible to rusi."
        )
    if stats.get("crypto_finding_count") == 0:
        diagnostics.append(
            "rusi emits crypto findings only from catalog components, and its"
            " only weak-crypto rules are SHA-1 and MD5 (category"
            " 'weak-crypto'); DES, RC4 and ECB are not modeled. 'rusi does"
            " not look for this' is the honest sentence, not 'rusi found"
            " nothing'."
        )
    diagnostics.append(
        "rusi has no strength field at all: materials are triaged by kind and"
        " construction site, not by algorithm strength."
    )
    return items, sections, diagnostics


# -- kosi: three grains, one per record kind ------------------------------------


def _kosi_crypto(
    raw: Dict, report, surface: Dict, graph
) -> Tuple[List[CryptoItem], Dict[str, int], List[str]]:
    """kosi crypto evidence joined at the grain each record kind supports.

    Operations carry ``function`` — anchored in the call graph and tested
    against every anchored endpoint's callee closure, the same derivation
    rusi's materials get. Materials and findings carry a file position only,
    so their claim is the file-level one. Assets, protocols and libraries
    carry no location at all: they are inventory, and their reach says so
    rather than borrowing a grain the record does not have.
    """
    crypto = raw.get("crypto") or {}
    sections = {
        section: len(crypto.get(section) or [])
        for section in ("libraries", "assets", "operations", "materials", "protocols", "findings")
    }
    closures: List[Tuple[str, set]] = []  # (endpoint label, closure node ids)
    from atom_tools.lib.attack_surface import _kosi_call_graph

    loaded = _kosi_call_graph(raw)
    if loaded and graph is not None:
        mini, _ = loaded
        for tier in surface.get("tiers") or []:
            for entry in tier.get("EntryPoints") or []:
                if entry.get("Engine") != "kosi":
                    continue
                endpoint = {
                    "handler": entry.get("Handler"),
                    "package": entry.get("Package"),
                    "file": entry.get("File") or "",
                    "raw": entry.get("raw") or {},
                }
                seeds, _how = mini.anchor(endpoint)
                if seeds:
                    route = entry.get("Route")
                    label = (
                        f"{entry.get('HttpMethod') or ''} {route}".strip()
                        if route
                        else (entry.get("Handler") or entry.get("EntryPointId") or "")
                    )
                    closures.append((label, set(mini.closure(seeds))))
    flows_by_file: Dict[str, List[str]] = defaultdict(list)
    for flow in report.flows:
        for file in {n.file for n in flow.nodes if n.file}:
            flows_by_file[file].append(flow.id)
    items: List[CryptoItem] = []
    diagnostics: List[str] = []

    def function_reach(function: str) -> Dict:
        reach: Dict = {
            "granularity": GRANULARITY_FUNCTION,
            "source": JOIN_DERIVED,
            "function": function or None,
        }
        if graph is None or not function:
            reach["state"] = "not-computed"
            reach["reason"] = "no call graph to anchor the function in"
            return reach
        # anchor() refuses ambiguous names; for a reachability question
        # "inside the closure of any same-named node" is the honest reading,
        # so an ambiguous qualified name is accepted rather than reported as
        # absent from the graph.
        anchored = graph.anchor(function) or graph.by_name.get(function) or []
        if not anchored:
            reach["state"] = "function-not-in-graph"
            return reach
        reached_from = sorted(
            label for label, closure in closures if any(n in closure for n in anchored)
        )
        if reached_from:
            reach["state"] = "reachable-from-endpoint"
            reach["endpoints"] = reached_from
            return reach
        reach["state"] = "in-graph-no-endpoint-reach"
        callers = sorted(
            {
                graph.by_id[c].name
                for node_id in anchored
                for c in graph.in_edges.get(node_id, ())
                if c in graph.by_id
            }
        )
        if callers:
            reach["callers"] = callers[:5]
            reach["note"] = (
                "inside the call graph but in no anchored endpoint's closure;"
                " static callers listed — event handlers, main and background"
                " listeners land here, as do functions reached only through"
                " dynamic dispatch"
            )
        else:
            reach["note"] = (
                "anchors in the call graph with no static caller — either"
                " dead, or reached through dynamic dispatch the static graph"
                " does not model"
            )
        return reach

    def file_reach(file: str) -> Dict:
        flow_ids = sorted(set(flows_by_file.get(file) or []))
        return {
            "granularity": GRANULARITY_FILE,
            "source": JOIN_DERIVED,
            "file": file or None,
            "fileOnFlow": bool(flow_ids),
            "flowsThroughFile": len(flow_ids),
            "flowIds": flow_ids[:20],
            "claim": (
                "the crypto site sits in a file that carries tainted flows —"
                " not that the crypto call itself is on a tainted path"
            ),
        }

    def no_location(kind: str) -> Dict:
        return {
            "source": JOIN_DERIVED,
            "state": "no-location",
            "reason": (
                f"kosi's crypto {kind} carry no file, function or package"
                " field — there is nothing to join on; this is inventory"
                " only"
            ),
        }

    for record in crypto.get("operations") or []:
        items.append(
            CryptoItem(
                engine="kosi",
                kind="operation",
                id=record.get("id") or "",
                name=" ".join(p for p in (record.get("kind"), record.get("asset")) if p),
                algorithm=record.get("asset") or "",
                file=record.get("filePath") or "",
                line=(record.get("position") or {}).get("line"),
                function=record.get("function") or "",
                attention=False,
                reach=function_reach(record.get("function") or ""),
                raw=record,
            )
        )
    for record in crypto.get("materials") or []:
        position = record.get("position") or {}
        items.append(
            CryptoItem(
                engine="kosi",
                kind="material",
                id=record.get("id") or "",
                name=record.get("name") or "",
                algorithm=record.get("kind") or "",
                file=record.get("filePath") or "",
                line=position.get("line"),
                attention=False,
                reach=file_reach(record.get("filePath") or ""),
                raw=record,
            )
        )
    for record in crypto.get("findings") or []:
        code = record.get("code") or ""
        severity = record.get("severity") or ""
        items.append(
            CryptoItem(
                engine="kosi",
                kind="finding",
                id=record.get("id") or "",
                name=code,
                algorithm=record.get("asset") or "",
                severity=severity,
                severity_level=taxonomy.normalise_engine_severity(severity) or "",
                rule_id=code,
                file=record.get("filePath") or "",
                line=(record.get("position") or {}).get("line"),
                attention=_is_attention("finding", None, code),
                reach=file_reach(record.get("filePath") or ""),
                raw=record,
            )
        )
    for record in crypto.get("assets") or []:
        items.append(
            CryptoItem(
                engine="kosi",
                kind="asset",
                id=record.get("id") or "",
                name=record.get("algorithm") or "",
                algorithm=record.get("algorithm") or "",
                attention=False,
                reach=no_location("assets"),
                raw=record,
            )
        )
    for name in crypto.get("protocols") or []:
        items.append(
            CryptoItem(
                engine="kosi",
                kind="protocol",
                id="",
                name=name if isinstance(name, str) else str(name),
                attention=False,
                reach=no_location("protocols"),
                raw={"protocol": name},
            )
        )
    for name in crypto.get("libraries") or []:
        items.append(
            CryptoItem(
                engine="kosi",
                kind="library",
                id="",
                name=name if isinstance(name, str) else str(name),
                attention=False,
                reach=no_location("libraries"),
                raw={"library": name},
            )
        )
    if any(sections.values()):
        diagnostics.append(
            "crypto assets, protocols and libraries carry no location and no"
            " strength field: they are inventory only, and weakness claims come"
            " from kosi's own findings."
        )
    else:
        diagnostics.append(
            "the report's crypto section is empty — no record of any kind."
            " Whether that means nothing matched kosi's shipped pattern pack"
            " or the generating mode did not populate the section cannot be"
            " read off the report itself."
        )
    return items, sections, diagnostics


# -- the document ---------------------------------------------------------------

ENGINES_WITH_CRYPTO = ("golem", "rusi", "dosai", "kosi")


def _load_graph_softly(loader, raw: Dict, path: str):
    """Load a call graph, or None when the input carries none."""
    try:
        return loader(raw, path)
    except (ValueError, KeyError, TypeError):
        return None


def compute_crypto_reach(inputs: List, weak_only: bool = False) -> Dict:
    """Compute the crypto-reach document over one or more parsed inputs.

    Engines mix freely; each engine's items carry their own join granularity
    and provenance, and the summary reports per-engine counts only — never a
    cross-engine total, which would average three different meanings of
    "reachable" into one number.
    """
    from atom_tools.lib.attack_surface import compute_attack_surface
    from atom_tools.lib.callgraph import load_golem, load_kosi, load_rusi
    from atom_tools.lib.unified import detect as detect_unified

    blocks: List[Dict] = []
    out_of_scope: List[Dict] = []
    engines_present = set()
    # Unified documents are detected structurally and never dispatched by
    # their engine field: a unified doc whose engine says "rusi" carries no
    # crypto section, and routing it through the rusi join would produce a
    # confidently empty block instead of the precise reason.
    unified_inputs = [i for i in inputs if isinstance(i.raw, dict) and detect_unified(i.raw)]
    unified_ids = {id(i) for i in unified_inputs}
    crypto_inputs = [i for i in inputs if id(i) not in unified_ids]

    for engine in ENGINES_WITH_CRYPTO:
        engine_inputs = [i for i in crypto_inputs if i.engine == engine]
        if not engine_inputs:
            continue
        combined: List[CryptoItem] = []
        diagnostics: List[str] = []
        sections: Dict[str, int] = {}
        coverage_notes: List[str] = []
        for inp in engine_inputs:
            if engine == "dosai":
                if not (isinstance(inp.raw, dict) and "Assets" in inp.raw):
                    out_of_scope.append(
                        {
                            "engine": "dosai",
                            "file": inp.path,
                            "reason": (
                                "this dosai document carries no crypto section"
                                " (Assets/Operations/Materials/Findings); the"
                                " crypto payload comes from 'dosai crypto'"
                            ),
                        }
                    )
                    continue
                items, secs, diags = _dosai_crypto(inp.raw)
            elif engine == "golem":
                graph = _load_graph_softly(load_golem, inp.raw, inp.path)
                surface = compute_attack_surface([inp])
                items, secs, diags = _golem_crypto(inp.raw, inp.report, surface, graph)
                coverage_notes.extend(_coverage_notes("golem", surface, graph))
            elif engine == "kosi":
                graph = _load_graph_softly(load_kosi, inp.raw, inp.path)
                surface = compute_attack_surface([inp])
                items, secs, diags = _kosi_crypto(inp.raw, inp.report, surface, graph)
                coverage_notes.extend(_coverage_notes("kosi", surface, graph))
            else:  # rusi
                graph = _load_graph_softly(load_rusi, inp.raw, inp.path)
                surface = compute_attack_surface([inp])
                items, secs, diags = _rusi_crypto(inp.raw, inp.report, surface, graph)
                coverage_notes.extend(_coverage_notes("rusi", surface, graph))
            combined.extend(items)
            sections.update(secs)
            diagnostics.extend(diags)
        if weak_only:
            combined = [i for i in combined if i.attention]
        engines_present.add(engine)
        # The block label must not overstate: rusi's materials join at function
        # grain while its libraries and findings carry no function field and
        # stay at package grain, so the label lists every granularity the
        # items actually use ("function/package"), never just the finest one.
        present = sorted(
            {i.reach.get("granularity") for i in combined if i.reach.get("granularity")}
        )
        blocks.append(
            {
                "engine": engine,
                "joinGranularity": "/".join(present) or GRANULARITIES[engine],
                "joinSource": JOIN_ENGINE if engine == "dosai" else JOIN_DERIVED,
                "inventory": dict(sorted(sections.items())),
                "itemsTotal": len(combined),
                "attentionItems": sum(1 for i in combined if i.attention),
                "coverageNotes": coverage_notes,
                "items": [i.to_dict() for i in sorted(combined, key=CryptoItem.rank_key)],
                "diagnostics": list(dict.fromkeys(diagnostics)),
            }
        )

    for inp in unified_inputs + [i for i in crypto_inputs if i.engine not in engines_present]:
        if isinstance(inp.raw, dict) and detect_unified(inp.raw):
            reason = (
                "unified documents carry no crypto inventory — crypto stays"
                " engine-side by design; pass the engine's own report"
                " (golem analyze, rusi analyze or dosai crypto)"
            )
        else:
            reason = (
                "atom emits no crypto section of any kind; there is nothing"
                " to join for this input"
            )
        out_of_scope.append({"engine": inp.engine, "file": inp.path, "reason": reason})

    if not blocks:
        raise ValueError(
            "no input carries a crypto section (golem analyze --dataflow"
            " crypto|all, rusi analyze, dosai crypto)."
            + (f" {out_of_scope[0]['reason']}" if out_of_scope else "")
        )

    return {
        "cryptoReachVersion": CRYPTO_REACH_VERSION,
        "engine": "+".join(sorted(engines_present)),
        "sources": [i.path for i in inputs],
        "weakOnly": weak_only or None,
        # Per-engine summary only; see the module docstring for why there is
        # no cross-engine headline.
        "summary": {
            "perEngine": {
                block["engine"]: {
                    "joinGranularity": block["joinGranularity"],
                    "joinSource": block["joinSource"],
                    "itemsTotal": block["itemsTotal"],
                    "attentionItems": block["attentionItems"],
                }
                for block in blocks
            },
            "outOfScope": out_of_scope or None,
        },
        "engines": blocks,
        "diagnostics": [
            f"{block['engine']}: {diagnostic}"
            for block in blocks
            for diagnostic in block["diagnostics"]
        ],
    }


def _coverage_notes(engine: str, surface: Dict, graph) -> List[str]:
    """What the endpoint join covered, in the surface's own words."""
    notes: List[str] = []
    coverage = surface.get("coverage", {}).get(engine) or {}
    anchored = coverage.get("endpointsAnchored", 0)
    total = coverage.get("endpoints", 0)
    notes.append(
        f"endpoint closures from the attack-surface join: {anchored} of"
        f" {total} endpoint(s) anchored in this input's call graph"
    )
    if graph is not None and graph.trimmed:
        notes.append(
            f"the call graph is a subgraph of the engine's run"
            f" ({len(graph.edges)} of {graph.full_edges} edges present);"
            " closures are computed within that subgraph"
        )
    return notes


# -- renderings -----------------------------------------------------------------


def _item_lines(item: CryptoItem) -> List[str]:
    """The console lines for one item: what it is, then its reach verdict."""
    what = item.name or item.id
    strength = f", strength {item.strength}" if item.strength else ""
    severity = f", severity {item.severity}" if item.severity else ""
    rule = f" ({item.rule_id})" if item.rule_id and item.rule_id != what else ""
    cwe = f", {item.cwe}" if item.cwe else ""
    # The path, not its basename. Every engine records a path that says where
    # the code lives, and the directory is the most useful thing on the line:
    # 6 of the 13 dosai records on eShopOnWeb sit under tests/, which a bare
    # "ApiTokenHelper.cs:46" hides, and a Go repo has a dozen "client.go".
    where = f"  {item.file}:{item.line}" if item.file else ""
    lines = [f"{item.kind} {what}{rule}{strength}{severity}{cwe}{where}"]
    reach = item.reach
    if reach.get("source") == JOIN_ENGINE:
        state = (
            "reachable from an entry point (engine verdict)"
            if reach.get("reachableFromEntryPoint")
            else "not reachable from any entry point (engine verdict)"
        )
        lines.append(f"  reach: engine-reported · {state}")
        for entry in reach.get("entryPoints") or []:
            if entry.get("resolved"):
                auth = (
                    ""
                    if entry.get("authorizationRequired") is None
                    else f" (auth required: {entry['authorizationRequired']})"
                )
                lines.append(f"    entry point: {entry['label']}{auth}")
            else:
                lines.append(f"    entry point: {entry['id']} (unresolved id)")
        if reach.get("dataFlowSliceIds"):
            lines.append(f"    witness slices: {', '.join(reach['dataFlowSliceIds'])}")
        return lines
    if reach.get("granularity") == GRANULARITY_FUNCTION:
        state = reach.get("state", "")
        if state == "reachable-from-endpoint":
            for endpoint in reach.get("endpoints") or []:
                lines.append(f"  reach: function-level · inside {endpoint}'s closure")
        elif state == "in-graph-no-endpoint-reach":
            callers = ", ".join(reach.get("callers") or []) or "none"
            lines.append(
                "  reach: function-level · in the call graph, in no anchored"
                f" endpoint's closure · static callers: {callers}"
            )
        elif state == "function-not-in-graph":
            lines.append(
                f"  reach: function-level · '{reach.get('function')}' is not a"
                " node of the call graph"
            )
        else:
            lines.append(f"  reach: function-level · {reach.get('reason') or state}")
        return lines
    # kosi's assets, protocols and libraries: no file, function or package to
    # join on. Saying so beats the package sentence the fall-through would
    # print over a record that has no package.
    if reach.get("state") == "no-location":
        lines.append(f"  reach: none · {reach.get('reason')}")
        return lines
    # kosi's materials and findings: a file position, and nothing finer.
    if reach.get("granularity") == GRANULARITY_FILE:
        if reach.get("fileOnFlow"):
            lines.append(
                f"  reach: file-level · {reach.get('flowsThroughFile', 0)}"
                " tainted flow(s) through this file"
            )
            lines.append(f"  claim: {reach.get('claim')}")
        else:
            lines.append("  reach: file-level · no analysed flow runs through this file")
        return lines
    # package-level: golem items, rusi libraries and findings
    if reach.get("packageOnFlow"):
        detail = f"{reach.get('flowsThroughPackage', 0)} tainted flow(s) through package"
        endpoints = reach.get("flowsThroughPackageReachEndpoints")
        if endpoints:
            shown = ", ".join(endpoints[:3])
            more = f" (+{len(endpoints) - 3} more)" if len(endpoints) > 3 else ""
            detail += f", of which some hang off: {shown}{more}"
        lines.append(f"  reach: package-level · {detail}")
        lines.append(f"  claim: {reach.get('claim')}")
        verdict = reach.get("engineRootVerdict")
        if verdict:
            lines.append(
                "  engine roots: "
                f"{verdict['reachableNodesInPackage']} of"
                f" {verdict['nodesInPackage']} call-graph node(s) in this"
                " package are reachable from the engine's root set"
            )
    else:
        lines.append(
            "  reach: package-level · no analysed flow runs through this"
            " item's package"
        )
    return lines


def render_console(document: Dict, max_entries: int = 40) -> List[str]:
    """Console rendering as lines for cleo's io — never bare print()."""
    lines: List[str] = []
    per_engine = document["summary"]["perEngine"]
    granularity = ", ".join(
        f"{engine} {facts['joinGranularity']}-level ({facts['joinSource']})"
        for engine, facts in sorted(per_engine.items())
    )
    lines.append(
        f"Crypto reach: {document['engine']} — join granularity per engine:"
        f" {granularity}"
    )
    lines.append(
        "reachability means a different thing at each granularity; counts are"
        " per engine and are never summed across them."
    )
    lines.append("")
    shown = 0
    truncated = False
    for block in document["engines"]:
        # The inventory keys are each engine's own section names, so dosai's
        # are PascalCase ("Assets") where golem's and rusi's are lower. Case
        # carried from a JSON schema into an English count sentence reads as a
        # difference between the engines, which it is not.
        inventory = ", ".join(f"{v} {k.lower()}" for k, v in block["inventory"].items())
        lines.append(f"* {block['engine']}: {block['itemsTotal']} item(s) ({inventory})")
        lines.append(
            f"  triage population (weak/legacy strength or a weak-crypto"
            f" rule): {block['attentionItems']} item(s)"
        )
        for item_dict in block["items"]:
            if shown >= max_entries:
                truncated = True
                break
            item_lines = _item_lines(CryptoItem.from_dict(item_dict))
            lines.append(f"  {shown + 1}. {item_lines[0].strip()}")
            lines.extend(f"     {line.strip()}" for line in item_lines[1:])
            shown += 1
        for note in block.get("coverageNotes") or []:
            lines.append(f"  coverage: {note}")
        lines.append("")
        if truncated:
            break
    if truncated:
        lines.append(
            f"listing truncated at --max-entries {max_entries}; the json"
            " output carries every item."
        )
        lines.append("")
    for out in document["summary"].get("outOfScope") or []:
        lines.append(
            f"out of scope ({out['engine']},"
            f" {os.path.basename(out['file'])}): {out['reason']}"
        )
    for diagnostic in document.get("diagnostics", []):
        lines.append(f"note: {diagnostic}")
    return lines
