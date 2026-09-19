"""Reachability drift between two runs of the same engine.

A repository with several thousand flows is never triaged; the handful that
appeared this week is. ``drift`` is a pure function over two
:class:`~atom_tools.lib.unified.UnifiedReport` objects — no engine invocation,
so it runs in seconds in CI.

Two properties decide whether a diff is usable at all, and both are enforced
here:

**A flow that only moved is not a new risk.** Line and column numbers shift on
every edit, so they are excluded from flow identity and a location-only change
is reported as ``moved``, never as ``added`` plus ``removed``.

**A drop in analysis coverage must never read as a risk reduction.** A run that
analysed fewer files, or that the engine itself cut short, trips the gate
regardless of which keys the caller selected — otherwise a half-broken build
renders as a green diff, which is the most dangerous thing a diff tool can do.
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from atom_tools.lib.unified import UnifiedFlow, UnifiedReport

logger = logging.getLogger(__name__)

# Maps the three unified severity levels onto the RiskDelta buckets.
SEVERITY_BUCKETS = {"error": "high", "warning": "medium", "note": "low"}

# --fail-on keys, mapped to the RiskDelta field they read.
GATE_KEYS = {
    "new-high": "NewHighSeverityFlows",
    "new-medium": "NewMediumSeverityFlows",
    "new-anonymous-endpoint": "NewAnonymousEndpoints",
    "new-package": "NewlyReachablePackages",
    "new-sink-category": "NewSinkCategories",
    "new-entrypoint": "NewEntryPoints",
}

# A coverage drop beyond this fraction trips the gate on its own.
COVERAGE_REGRESSION_THRESHOLD = 0.10

GATE_EXIT_CODE = 2


# A directory must cover at least this share of the remaining absolute paths
# to be treated as a root worth stripping.
ROOT_MIN_SHARE = 0.05
# Guards against stripping so much of a path that distinct files collide.
ROOT_MIN_DEPTH = 2

# A drive-letter prefix, the one absolute spelling that does not start with a
# separator.
_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def _slashed(path: str) -> str:
    """The path with every separator spelled ``/``.

    The paths here come out of an engine's report, so their separators are the
    ones of the machine that *ran the engine* -- which is not necessarily the
    machine running drift. Reading them with ``os.sep`` makes the comparison
    depend on the host: a golem report full of ``/Users/...`` paths, diffed on
    Windows, yields no root at all and renders every file at full length. A
    backslash inside an engine-reported source path is a separator, never a
    filename character, so normalising is safe in both directions.
    """
    return path.replace("\\", "/")


def _is_absolute(path: str) -> bool:
    """Absolute in the report's own terms, on any host: a leading separator or
    a drive letter."""
    return path.startswith(("/", "\\")) or bool(_DRIVE.match(path))


def candidate_roots(paths: Iterable[str], min_share: float = ROOT_MIN_SHARE) -> List[str]:
    """
    Every ancestor directory that covers at least ``min_share`` of the absolute
    paths, deepest first — the plausible checkout roots for a report.

    Which one is *the* root cannot be decided from one report alone: a golem
    run references both the repo and the Go module cache, so nothing in the
    path set marks where the checkout begins. :func:`align_roots` picks between
    these candidates using the other side of the comparison.
    """
    absolute = [_slashed(p) for p in paths if p and _is_absolute(p)]
    if not absolute:
        return []
    total = len(absolute)
    counts: Counter = Counter()
    for path in absolute:
        parts = path.rsplit("/", 1)[0].split("/")
        for depth in range(ROOT_MIN_DEPTH, len(parts) + 1):
            counts["/".join(parts[:depth])] += 1
    candidates = [d for d, n in counts.items() if d and n >= total * min_share]
    return sorted(candidates, key=lambda d: (-d.count("/"), d))


def align_roots(old_paths: Sequence[str], new_paths: Sequence[str]) -> Tuple[str, str]:
    """
    Choose one root per side so the two reports' paths line up.

    Both sides are the same repository, so the right roots are the ones that
    make the normalised path sets overlap most. Scoring the choice against the
    other side is what lets drift survive a baseline and a current generated in
    different directories — the case that otherwise reports 100% churn.

    Known limit: a dependency cache that moved *independently* of the checkout
    (a different ``GOPATH`` as well as a different workspace) is not recovered
    by a single root per side. Flows through third-party code would then read
    as added and removed. Same-machine comparisons, and CI where only the
    workspace differs, are unaffected.
    """
    old_candidates = candidate_roots(old_paths) or [""]
    new_candidates = candidate_roots(new_paths) or [""]
    old_unique, new_unique = set(old_paths), set(new_paths)
    best: Tuple = (-1, 0, "", "")
    for old_root in old_candidates:
        old_norm = {normalize_path(p, old_root) for p in old_unique}
        for new_root in new_candidates:
            new_norm = {normalize_path(p, new_root) for p in new_unique}
            score = len(old_norm & new_norm)
            depth = old_root.count("/") + new_root.count("/")
            if (score, depth) > (best[0], best[1]):
                best = (score, depth, old_root, new_root)
    return best[2], best[3]


def normalize_path(path: str, roots) -> str:
    """Strip the matching root from ``path`` and normalise separators to ``/``."""
    if not path:
        return ""
    if isinstance(roots, str):
        roots = [roots] if roots else []
    cleaned = _slashed(path)
    if _is_absolute(path):
        for root in roots:
            root = _slashed(root)
            if root and cleaned.startswith(root + "/"):
                cleaned = cleaned[len(root) + 1 :]
                break
    # Only a leading "./" is noise. lstrip("./") would also eat the leading
    # slash of a path no root matched, turning an absolute dependency-cache
    # path into a relative-looking one.
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def report_paths(report: UnifiedReport) -> List[str]:
    """Every file path a report mentions, flows and endpoints alike."""
    paths = [n.file for flow in report.flows for n in flow.nodes if n.file]
    paths.extend(str(e.get("file")) for e in report.endpoints if e.get("file"))
    return paths


def report_root(report: UnifiedReport) -> str:
    """
    The single most plausible root for one report, used when there is no other
    side to align against (rendering, coverage). Drift itself always uses
    :func:`align_roots`, which is strictly better informed.
    """
    candidates = candidate_roots(report_paths(report))
    return candidates[-1] if candidates else ""


def identity_key(flow: UnifiedFlow, root: str) -> Tuple:
    """
    The coarse identity of a flow: analysis facts only, never locations.

    Deliberately excluded: line and column numbers, engine node ids (unstable
    across runs by construction — this is what caused the SARIF fingerprint
    collisions) and path length.

    ``sink_argument_index`` appears in the original design note but does not
    exist on :class:`~atom_tools.lib.unified.UnifiedNode`; only rusi preserves
    anything like it, and only inside ``extra``. Including it "when present"
    would give rusi flows a different key shape from every other engine, so it
    is left out entirely.
    """
    sink = flow.sink
    return (
        flow.source_category,
        flow.sink_category,
        (sink.symbol or sink.name) if sink else "",
        normalize_path(sink.file, root) if sink else "",
        tuple(sorted(flow.purls)),
    )


def witness_key(flow: UnifiedFlow, root: str) -> Tuple:
    """
    Identity plus the symbol/file chain of the whole path.

    The coarse identity collides heavily on real data — golem's ipsw report has
    397 flows over 91 identity keys — so it cannot stand alone as a 1:1 key.
    Adding the location-free chain separates 339 of those 397, against golem's
    own ``uniqueFlowCount`` of 335, which is close enough to treat the chain as
    the engine's own notion of a distinct flow.

    Identity still drives added/removed, because a refactor that inserts a
    wrapper changes the chain without introducing a new risk. Chain changes are
    reported separately as ``witnessChanged``.
    """
    return identity_key(flow, root) + (
        tuple((n.symbol or n.name, normalize_path(n.file, root)) for n in flow.nodes),
    )


def location(flow: UnifiedFlow, root: str) -> Tuple:
    """The location fingerprint used to tell ``moved`` from unchanged."""
    return tuple(
        (normalize_path(n.file, root), n.line, n.column) for n in flow.nodes
    )


def _describe(flow: UnifiedFlow, root: str) -> Dict:
    """A JSON-serialisable summary of one flow, for the drift document."""
    source, sink = flow.source, flow.sink
    described = {
        "sourceCategory": flow.source_category,
        "sinkCategory": flow.sink_category,
        "severity": flow.severity,
        "severitySource": flow.severity_source,
        "engine": flow.engine,
        "purls": sorted(flow.purls),
        "pathTruncated": flow.path_truncated,
        "pathLength": len(flow.nodes),
    }
    if source:
        described["source"] = {
            "name": source.symbol or source.name,
            "file": normalize_path(source.file, root),
            "line": source.line,
        }
    if sink:
        described["sink"] = {
            "name": sink.symbol or sink.name,
            "file": normalize_path(sink.file, root),
            "line": sink.line,
        }
    if flow.id:
        described["flowId"] = flow.id
    return described


def _group(flows: Sequence[UnifiedFlow], root: str) -> Dict[Tuple, List[UnifiedFlow]]:
    grouped: Dict[Tuple, List[UnifiedFlow]] = defaultdict(list)
    for flow in flows:
        grouped[identity_key(flow, root)].append(flow)
    return grouped


def _endpoint_key(endpoint: Dict, root: str) -> Tuple:
    """Endpoint identity: method + path + kind, never the line it sits on."""
    return (
        str(endpoint.get("method") or "").upper(),
        str(endpoint.get("path") or ""),
        str(endpoint.get("kind") or ""),
        normalize_path(str(endpoint.get("file") or ""), root),
    )


def _severity_sources(flows: Iterable[UnifiedFlow]) -> List[str]:
    return sorted({f.severity_source for f in flows if f.severity_source})


def _coverage(report: UnifiedReport, root: str) -> Dict:
    """
    What the run actually looked at, so a smaller run cannot read as a safer one.

    ``truncated`` comes from the engine's own self-report where it has one —
    golem sets ``dataFlow.stats.truncated`` and says why — not from a guess
    about record counts.
    """
    files = {normalize_path(n.file, root) for flow in report.flows for n in flow.nodes if n.file}
    provenance = report.provenance or {}
    # Report-level truncation (the engine stopped early) is a coverage fact.
    # Per-path truncation (a witness was capped) is a rendering caveat about an
    # individual flow, not a smaller run, so the two are counted separately.
    truncated = bool(provenance.get("dataflow_truncated") or provenance.get("truncated"))
    reasons = [d for d in report.diagnostics if "truncat" in d.lower()]
    return {
        "engine": report.engine,
        "engineVersion": report.engine_version,
        "analysisMode": report.analysis_mode,
        "flows": len(report.flows),
        "files": len(files),
        "packages": len({p for flow in report.flows for p in flow.purls}),
        "endpoints": len(report.endpoints),
        "truncated": truncated,
        "truncationReasons": reasons,
        "truncatedPaths": sum(1 for f in report.flows if f.path_truncated),
        "severitySources": _severity_sources(report.flows),
        "diagnostics": len(report.diagnostics),
    }


def _coverage_delta(old: Dict, new: Dict) -> Dict:
    """Coverage regression detection. A shrinking denominator is not a win."""
    regressions = []
    for metric in ("files", "endpoints"):
        before, after = old[metric], new[metric]
        if before and after < before * (1 - COVERAGE_REGRESSION_THRESHOLD):
            regressions.append(
                f"{metric} analysed fell from {before} to {after}"
                f" ({(before - after) / before:.0%} drop); a smaller run is not a safer one"
            )
    if new["truncated"] and not old["truncated"]:
        reasons = "; ".join(new["truncationReasons"]) or "engine reported a truncated run"
        regressions.append(f"the new run is truncated and the baseline was not: {reasons}")
    return {
        "old": old,
        "new": new,
        "regressions": regressions,
        "regressed": bool(regressions),
    }


def compute_drift(old: UnifiedReport, new: UnifiedReport) -> Dict:
    """
    Compare two unified reports and return the drift document.

    Both reports must come from the same engine: identity keys are built from
    engine-specific category vocabularies and symbol spellings, so comparing a
    golem baseline against a dosai current would report every flow as both
    added and removed. A mismatch is recorded as a diagnostic and the caller
    decides what to do about it.
    """
    diagnostics: List[str] = []
    if old.engine and new.engine and old.engine != new.engine:
        diagnostics.append(
            f"baseline engine '{old.engine}' differs from current engine '{new.engine}';"
            " identity keys are engine-specific, so this comparison is not meaningful."
        )
    # A root per side: the baseline and the current are the same repository,
    # possibly checked out in different directories, and the whole point of
    # normalisation is that this must not register as churn.
    old_root, new_root = align_roots(report_paths(old), report_paths(new))

    old_groups, new_groups = _group(old.flows, old_root), _group(new.flows, new_root)
    added, removed, moved, witness_changed = [], [], [], []

    for key, new_flows in new_groups.items():
        old_flows = old_groups.get(key, [])
        old_locations = Counter(location(f, old_root) for f in old_flows)
        old_chains = Counter(witness_key(f, old_root) for f in old_flows)
        # Flows whose location is unchanged are matched first, so the ones left
        # over are genuinely unaccounted for rather than whichever happened to
        # be emitted last.
        unmatched = []
        for flow in new_flows:
            here = location(flow, new_root)
            if old_locations.get(here):
                old_locations[here] -= 1
            else:
                unmatched.append(flow)
        # Each remaining baseline flow under this identity absorbs one
        # unmatched current flow as a move; only the surplus beyond that is new.
        absorbable = sum(old_locations.values())
        moved.extend(_describe(f, new_root) for f in unmatched[:absorbable])
        added.extend(_describe(f, new_root) for f in unmatched[absorbable:])
        for flow in new_flows[: len(old_flows)]:
            if not old_chains.get(witness_key(flow, new_root)):
                witness_changed.append(_describe(flow, new_root))

    for key, old_flows in old_groups.items():
        deficit = len(old_flows) - len(new_groups.get(key, []))
        if deficit > 0:
            removed.extend(_describe(f, old_root) for f in old_flows[-deficit:])

    old_eps = Counter(_endpoint_key(e, old_root) for e in old.endpoints)
    new_eps = Counter(_endpoint_key(e, new_root) for e in new.endpoints)
    added_eps = sorted(k for k in new_eps if k not in old_eps)
    removed_eps = sorted(k for k in old_eps if k not in new_eps)

    old_purls = {p for flow in old.flows for p in flow.purls}
    new_purls = {p for flow in new.flows for p in flow.purls}
    old_sinks = {f.sink_category for f in old.flows if f.sink_category}
    new_sinks = {f.sink_category for f in new.flows if f.sink_category}

    buckets = Counter(SEVERITY_BUCKETS.get(f["severity"], "unknown") for f in added)
    coverage = _coverage_delta(_coverage(old, old_root), _coverage(new, new_root))

    risk_delta = {
        "NewHighSeverityFlows": buckets.get("high", 0),
        "NewMediumSeverityFlows": buckets.get("medium", 0),
        "NewLowSeverityFlows": buckets.get("low", 0),
        # No endpoint in the unified model carries an exposure tier. dosai
        # knows it (its AttackSurface array tiers entry points as
        # anonymous-http / authenticated-http) but the adapters do not surface
        # that yet, and nothing at all is available for golem or rusi. null
        # says "not computed"; a confident 0 here would be a lie a CI gate
        # acts on. Filled in when the attack-surface work lands.
        "NewAnonymousEndpoints": None,
        "NewEntryPoints": len(added_eps),
        "NewlyReachablePackages": len(new_purls - old_purls),
        "NewSinkCategories": len(new_sinks - old_sinks),
    }

    return {
        "driftVersion": 1,
        "baseline": {"file": old.source_file, "engine": old.engine},
        "current": {"file": new.source_file, "engine": new.engine},
        # Severity comes from the engine for golem and dosai and from the
        # shared taxonomy for rusi, which emits no severity at all. Counters
        # that silently mix the two would compare an engine's judgement with
        # our own lookup, so the sources are stated rather than blended.
        "severitySources": {
            "baseline": _severity_sources(old.flows),
            "current": _severity_sources(new.flows),
        },
        "AddedFlows": added,
        "RemovedFlows": removed,
        "MovedFlows": moved,
        "WitnessChangedFlows": witness_changed,
        "AddedEntryPoints": [dict(zip(("method", "path", "kind", "file"), k)) for k in added_eps],
        "RemovedEntryPoints": [
            dict(zip(("method", "path", "kind", "file"), k)) for k in removed_eps
        ],
        "AddedPackages": sorted(new_purls - old_purls),
        "RemovedPackages": sorted(old_purls - new_purls),
        "NewSinkCategories": sorted(new_sinks - old_sinks),
        "RiskDelta": risk_delta,
        "coverage": coverage,
        # Drift's own findings, which the command warns about. The engines'
        # diagnostics are kept separately: they describe the runs, not the
        # comparison, and rusi alone emits a dozen per report.
        "diagnostics": diagnostics,
        "engineDiagnostics": {
            "baseline": list(old.diagnostics),
            "current": list(new.diagnostics),
        },
    }


def evaluate_gates(drift: Dict, fail_on: Optional[str]) -> Tuple[bool, List[str]]:
    """
    Decide whether the drift trips the CI gate.

    A coverage regression trips it regardless of the selected keys: the caller
    asked about risk, and a run that looked at materially less of the code
    cannot answer that question at all.
    """
    reasons: List[str] = []
    coverage = drift.get("coverage", {})
    if coverage.get("regressed"):
        reasons.extend(f"coverage: {r}" for r in coverage.get("regressions", []))
    risk = drift.get("RiskDelta", {})
    for raw_key in (fail_on or "").split(","):
        key = raw_key.strip()
        if not key:
            continue
        field = GATE_KEYS.get(key)
        if field is None:
            raise ValueError(f"Unknown --fail-on key: {key}. Known: {', '.join(sorted(GATE_KEYS))}")
        value = risk.get(field)
        if value is None:
            reasons.append(f"{key}: not computed by this engine's report; gate cannot be evaluated")
        elif value > 0:
            reasons.append(f"{key}: {field} is {value}")
    return bool(reasons), reasons


def _flow_line(flow: Dict) -> str:
    sink = flow.get("sink") or {}
    where = f"{sink.get('file', '?')}:{sink.get('line', '?')}"
    return (
        f"{flow['severity']:<8} {flow['sourceCategory']} -> {flow['sinkCategory']}"
        f"  {sink.get('name', '?')}  ({where})"
    )


def _collapse(flows: Sequence[Dict]) -> List[str]:
    """
    Render flows one line each, collapsing repeats into a single ``xN`` line.

    Several flows can share an identity, a location *and* a severity — golem's
    ipsw pair produces sixteen identical ``ParsePKCS8PrivateKey`` lines — and
    printing each of them buries the rest of the diff. The count is kept
    because it is a real multiplicity, not a display artefact; the full records
    remain in the json output.
    """
    counts = Counter(_flow_line(flow) for flow in flows)
    seen, ordered = set(), []
    for flow in flows:
        line = _flow_line(flow)
        if line in seen:
            continue
        seen.add(line)
        ordered.append(f"{line}  x{counts[line]}" if counts[line] > 1 else line)
    return ordered


def render_console(drift: Dict) -> List[str]:
    """Compact +/- summary: coverage first, then added flows by severity."""
    lines: List[str] = []
    coverage = drift["coverage"]
    if coverage["regressed"]:
        lines.append("<error>Coverage regressed — this drift cannot be read as a risk reduction:</error>")
        lines.extend(f"  ! {r}" for r in coverage["regressions"])
        lines.append("")
    old_cov, new_cov = coverage["old"], coverage["new"]
    lines.append(
        f"{old_cov['engine']} baseline {old_cov['flows']} flow(s) / {old_cov['files']} file(s)"
        f"  ->  current {new_cov['flows']} flow(s) / {new_cov['files']} file(s)"
    )
    sources = sorted(set(drift["severitySources"]["current"]))
    if sources:
        # "derived" alone names nothing; say what the severity was derived
        # from, the way explain's per-flow sentence does.
        names = {
            "engine": "engine",
            "derived": "the shared taxonomy (the engine emitted no severity)",
        }
        lines.append(f"severity source: {', '.join(names.get(s, s) for s in sources)}")
    lines.append("")
    lines.append(
        f"+{len(drift['AddedFlows'])} added  -{len(drift['RemovedFlows'])} removed"
        f"  ~{len(drift['MovedFlows'])} moved  ={len(drift['WitnessChangedFlows'])} witness-changed"
    )
    for bucket in ("error", "warning", "note"):
        group = [f for f in drift["AddedFlows"] if f["severity"] == bucket]
        lines.extend(f"  + {line}" for line in _collapse(group))
    lines.extend(f"  - {line}" for line in _collapse(drift["RemovedFlows"]))
    risk = drift["RiskDelta"]
    lines.append("")
    lines.append("RiskDelta:")
    for field, value in risk.items():
        shown = "not computed" if value is None else value
        lines.append(f"  {field}: {shown}")
    return lines


def render_markdown(drift: Dict) -> str:
    """PR-comment rendering; the primary CI consumption path."""
    coverage = drift["coverage"]
    out = ["## atom-tools drift", ""]
    if coverage["regressed"]:
        out.append("> [!WARNING]")
        out.append("> **Coverage regressed.** A smaller run is not a safer one:")
        out.extend(f"> - {r}" for r in coverage["regressions"])
        out.append("")
    old_cov, new_cov = coverage["old"], coverage["new"]
    names = {
        "engine": "engine",
        "derived": "the shared taxonomy (the engine emitted no severity)",
    }
    severity_note = ", ".join(
        names.get(s, s) for s in sorted(set(new_cov["severitySources"]))
    )
    out.append(f"`{old_cov['engine']}` — severity source: {severity_note or 'n/a'}")
    out.append("")
    out.append("| | baseline | current |")
    out.append("|---|---|---|")
    for metric in ("flows", "files", "packages", "endpoints"):
        out.append(f"| {metric} | {old_cov[metric]} | {new_cov[metric]} |")
    out.append("")
    out.append(
        f"**+{len(drift['AddedFlows'])} added**, "
        f"-{len(drift['RemovedFlows'])} removed, "
        f"{len(drift['MovedFlows'])} moved (location only), "
        f"{len(drift['WitnessChangedFlows'])} witness changed."
    )
    if drift["AddedFlows"]:
        out.extend(
            ["", "### Added flows", "", "| n | severity | source | sink | where |", "|---|---|---|---|---|"]
        )
        counts: Counter = Counter()
        rows: Dict[Tuple, Dict] = {}
        for flow in drift["AddedFlows"]:
            sink = flow.get("sink") or {}
            row = (
                flow["severity"],
                flow["sourceCategory"],
                flow["sinkCategory"],
                sink.get("name", "?"),
                f"{sink.get('file', '?')}:{sink.get('line', '?')}",
            )
            counts[row] += 1
            rows.setdefault(row, flow)
        for row in rows:
            severity, source, sink_category, name, where = row
            out.append(
                f"| {counts[row]} | {severity} | {source} | {sink_category}"
                f" `{name}` | `{where}` |"
            )
    out.extend(["", "### RiskDelta", ""])
    for field, value in drift["RiskDelta"].items():
        shown = "_not computed_" if value is None else value
        out.append(f"- **{field}**: {shown}")
    return "\n".join(out) + "\n"
