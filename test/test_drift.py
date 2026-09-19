"""Tests for the drift command and the reachability delta it computes.

The real pair is rusi's `rust-microservices-kafka-rusi-baseline.json` (commit
`1453f9a`) against `rust-microservices-kafka-rusi.json` (commit `4c5596f`),
both produced by the same rusi binary with the same command line; see
`test/data/ecosystem/PROVENANCE.md`. Two of its five flows shifted by one line
between the commits, so it is a real, engine-produced instance of the property
that decides whether a diff is usable: a flow that only moved is not a new
risk.

Everything the pair cannot cover (a genuinely new flow, a coverage collapse, a
different checkout root) is a transformation applied to a real fixture inside
the test. No fixture on disk is hand-edited.
"""

import copy
import json
import os
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application
from atom_tools.lib.adapters import parse_report
from atom_tools.lib.drift import (
    COVERAGE_REGRESSION_THRESHOLD,
    align_roots,
    compute_drift,
    evaluate_gates,
    identity_key,
    normalize_path,
    render_console,
    render_markdown,
    report_paths,
    report_root,
)

ECOSYSTEM = Path("test/data/ecosystem")
RUSI_BASELINE = ECOSYSTEM / "rust-microservices-kafka-rusi-baseline.json"
RUSI_CURRENT = ECOSYSTEM / "rust-microservices-kafka-rusi.json"
GOLEM = ECOSYSTEM / "go-ipsw-golem.json"
GOLEM_BASELINE = ECOSYSTEM / "go-ipsw-golem-baseline.json"
DOSAI = ECOSYSTEM / "dotnet-eshoponweb-dosai-dataflows.json"
KOSI = ECOSYSTEM / "kotlin-command-exec-kosi.json"
KOSI_BASELINE = ECOSYSTEM / "kotlin-command-exec-kosi-baseline.json"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def report(path, content=None):
    return parse_report(content if content is not None else load(path), source_file=str(path))


@pytest.fixture(scope="module")
def rusi_pair():
    return report(RUSI_BASELINE), report(RUSI_CURRENT)


# --- the real pair -------------------------------------------------------


def test_real_rusi_pair_reports_moves_not_churn(rusi_pair):
    """
    Two real rusi runs, five commits apart.

    Both runs found the same five flows; two of them (`load_jwk_decoders` in
    each of the two services) moved from line 38 to line 39, and the engine
    emitted the five slices in a different order. A diff that keyed on line
    numbers or on emission order would report 2 added and 2 removed here.
    """
    drift = compute_drift(*rusi_pair)
    assert drift["AddedFlows"] == []
    assert drift["RemovedFlows"] == []
    assert len(drift["MovedFlows"]) == 2
    assert {f["sink"]["line"] for f in drift["MovedFlows"]} == {39}
    assert all("load_jwk_decoders" in f["sink"]["name"] for f in drift["MovedFlows"])
    assert drift["RiskDelta"]["NewHighSeverityFlows"] == 0
    assert drift["AddedPackages"] == []
    assert drift["AddedEntryPoints"] == []
    assert not drift["coverage"]["regressed"]


def test_real_pair_records_that_rusi_severity_is_derived(rusi_pair):
    """rusi emits no severity field; the drift document must say so rather
    than presenting a taxonomy lookup as the engine's own judgement."""
    drift = compute_drift(*rusi_pair)
    assert drift["severitySources"] == {"baseline": ["derived"], "current": ["derived"]}


def test_real_kosi_pair_shows_the_degradation_gap():
    """Two real kosi runs of the same fixture: the baseline used
    `--backend syntax`, which degrades to no flows, no endpoints and no call
    graph with a single diagnostics entry as the trace; the current run used
    `--backend resolved`. The delta is exactly the engine's own degradation,
    not a code change."""
    drift = compute_drift(report(KOSI_BASELINE), report(KOSI))
    assert len(drift["AddedFlows"]) == 2
    assert len(drift["RemovedFlows"]) == 0
    assert len(drift["MovedFlows"]) == 0
    assert len(drift["AddedEntryPoints"]) == 1
    assert drift["RiskDelta"]["NewHighSeverityFlows"] == 2
    # The current side's severity is the engine's; nothing derived crept in.
    # (The baseline carries none — it has no flows at all to classify.)
    assert drift["severitySources"]["current"] == ["engine"]
    # A baseline that analysed nothing is not a coverage regression — the
    # gate must stay silent while the counts tell the story.
    assert drift["coverage"]["regressed"] is False


# --- properties, on real fixtures ----------------------------------------


@pytest.mark.parametrize("path", [RUSI_CURRENT, GOLEM, DOSAI])
def test_identical_input_is_empty_drift(path):
    drift = compute_drift(report(path), report(path))
    for section in ("AddedFlows", "RemovedFlows", "MovedFlows", "WitnessChangedFlows"):
        assert drift[section] == [], section
    for field, value in drift["RiskDelta"].items():
        assert value in (0, None), field
    assert not drift["coverage"]["regressed"]


def shift_lines(content, offset):
    """Add a constant offset to every line number in a report document."""
    if isinstance(content, dict):
        return {
            k: (v + offset if k in ("line", "Line") and isinstance(v, int) else shift_lines(v, offset))
            for k, v in content.items()
        }
    if isinstance(content, list):
        return [shift_lines(v, offset) for v in content]
    return content


@pytest.mark.parametrize("path", [RUSI_CURRENT, GOLEM])
def test_line_shift_is_moved_not_added(path):
    """
    The single most important property: reindenting a file must not look like
    new risk. Every flow moves, nothing is added or removed.
    """
    original = load(path)
    drift = compute_drift(report(path, original), report(path, shift_lines(original, 7)))
    assert drift["AddedFlows"] == []
    assert drift["RemovedFlows"] == []
    assert drift["MovedFlows"], "a line shift should register as movement"
    assert len(drift["MovedFlows"]) == len(report(path, original).flows)
    assert drift["RiskDelta"]["NewHighSeverityFlows"] == 0


def rebase_paths(content, old_root, new_root):
    """Rewrite an absolute checkout root throughout a report document."""
    if isinstance(content, dict):
        return {k: rebase_paths(v, old_root, new_root) for k, v in content.items()}
    if isinstance(content, list):
        return [rebase_paths(v, old_root, new_root) for v in content]
    if isinstance(content, str) and content.startswith(old_root):
        return new_root + content[len(old_root) :]
    return content


def test_path_rebase_is_not_drift():
    """
    golem emits absolute, machine-specific paths. The same repo checked out
    somewhere else is the same repo, and must produce no drift at all --
    otherwise every CI runner with a different workspace reports 100% churn.
    """
    original = load(GOLEM)
    root = "/Users/prabhu/sandbox/ipsw"
    assert any(root in p for p in report_paths(report(GOLEM, original)))
    rebased = rebase_paths(original, root, "/somewhere/else/ci-workspace")
    drift = compute_drift(report(GOLEM, original), report(GOLEM, rebased))
    assert drift["AddedFlows"] == []
    assert drift["RemovedFlows"] == []
    assert drift["MovedFlows"] == []


def test_normalize_path_leaves_relative_paths_alone():
    assert normalize_path("src/lib.rs", "/a/b") == "src/lib.rs"
    assert normalize_path("/a/b/src/lib.rs", "/a/b") == "src/lib.rs"
    assert normalize_path("", "/a/b") == ""


# --- added flows ---------------------------------------------------------


def test_appended_flow_is_exactly_one_addition():
    """A genuinely new slice, built by duplicating a real one and changing the
    sink symbol so its identity differs, must count once and land in the right
    severity bucket."""
    original = load(GOLEM)
    mutated = copy.deepcopy(original)
    slices = mutated["dataFlow"]["slices"]
    new_slice = copy.deepcopy(slices[0])
    new_slice["id"] = new_slice["id"] + "-synthetic"
    new_slice["sinkCategory"] = "a-category-not-otherwise-present"
    new_slice["severity"] = "high"
    slices.append(new_slice)
    drift = compute_drift(report(GOLEM, original), report(GOLEM, mutated))
    assert len(drift["AddedFlows"]) == 1
    added = drift["AddedFlows"][0]
    assert added["sinkCategory"] == "a-category-not-otherwise-present"
    assert added["severity"] == "error"
    assert drift["RiskDelta"]["NewHighSeverityFlows"] == 1
    assert drift["RiskDelta"]["NewSinkCategories"] == 1
    assert drift["NewSinkCategories"] == ["a-category-not-otherwise-present"]
    assert drift["RemovedFlows"] == []


def test_removed_flow_is_counted_once():
    original = load(GOLEM)
    mutated = copy.deepcopy(original)
    mutated["dataFlow"]["slices"] = mutated["dataFlow"]["slices"][:-1]
    drift = compute_drift(report(GOLEM, original), report(GOLEM, mutated))
    assert len(drift["RemovedFlows"]) == 1
    assert drift["AddedFlows"] == []


def test_duplicate_identities_are_compared_by_count():
    """
    Identity is not 1:1 on real data -- golem's 397 flows share 91 identity
    keys -- so drift compares multiplicities. Dropping one of several flows
    that share a key must count as exactly one removal, not zero.
    """
    original = load(GOLEM)
    parsed = report(GOLEM, original)
    root = report_root(parsed)
    keys = [identity_key(f, root) for f in parsed.flows]
    assert len(set(keys)) < len(keys), "the fixture should contain colliding identities"
    duplicated = next(k for k in keys if keys.count(k) > 1)
    victim = next(
        i for i, f in enumerate(parsed.flows) if identity_key(f, root) == duplicated
    )
    mutated = copy.deepcopy(original)
    del mutated["dataFlow"]["slices"][victim]
    drift = compute_drift(parsed, report(GOLEM, mutated))
    assert len(drift["RemovedFlows"]) == 1
    assert drift["AddedFlows"] == []


# --- coverage ------------------------------------------------------------


def test_coverage_collapse_trips_the_gate_with_zero_added_flows():
    """
    The most dangerous failure mode: a half-broken run that finds fewer flows
    looks like a security improvement. It must trip the gate on its own, with
    no --fail-on key selected at all.
    """
    original = load(GOLEM)
    mutated = copy.deepcopy(original)
    keep = int(len(mutated["dataFlow"]["slices"]) * (1 - COVERAGE_REGRESSION_THRESHOLD * 4))
    mutated["dataFlow"]["slices"] = mutated["dataFlow"]["slices"][:keep]
    drift = compute_drift(report(GOLEM, original), report(GOLEM, mutated))
    assert drift["AddedFlows"] == []
    assert drift["RemovedFlows"], "the truncated run should lose flows"
    assert drift["coverage"]["regressed"]
    tripped, reasons = evaluate_gates(drift, None)
    assert tripped
    assert any("files analysed fell" in r for r in reasons)
    assert any("not a safer one" in r for r in reasons)


def test_newly_truncated_run_trips_the_gate():
    """golem self-reports truncation. A current run that is truncated when the
    baseline was not is a coverage fact, not a flow-count fact."""
    original = load(GOLEM)
    untruncated = copy.deepcopy(original)
    untruncated["dataFlow"]["stats"]["truncated"] = False
    untruncated["dataFlow"]["stats"]["truncationReasons"] = []
    drift = compute_drift(report(GOLEM, untruncated), report(GOLEM, original))
    assert drift["AddedFlows"] == []
    assert drift["coverage"]["new"]["truncated"] is True
    assert drift["coverage"]["old"]["truncated"] is False
    tripped, reasons = evaluate_gates(drift, None)
    assert tripped
    assert any("truncated" in r for r in reasons)
    assert any("slice limit reached" in r for r in reasons)


def test_coverage_is_reported_for_both_sides(rusi_pair):
    drift = compute_drift(*rusi_pair)
    for side in ("old", "new"):
        coverage = drift["coverage"][side]
        assert coverage["engine"] == "rusi"
        assert coverage["flows"] == 5
        assert coverage["endpoints"] == 14
        assert coverage["truncated"] is False


# --- gates ---------------------------------------------------------------


def test_unknown_gate_key_is_rejected(rusi_pair):
    drift = compute_drift(*rusi_pair)
    with pytest.raises(ValueError) as excinfo:
        evaluate_gates(drift, "new-high,not-a-key")
    assert "not-a-key" in str(excinfo.value)
    assert "Known:" in str(excinfo.value)


def test_gate_on_an_uncomputed_counter_fails_closed(rusi_pair):
    """Asking to gate on anonymous endpoints, which nothing can compute yet,
    must not silently pass as if the answer were zero."""
    drift = compute_drift(*rusi_pair)
    tripped, reasons = evaluate_gates(drift, "new-anonymous-endpoint")
    assert tripped
    assert any("not computed" in r for r in reasons)


def test_clean_drift_does_not_trip(rusi_pair):
    drift = compute_drift(*rusi_pair)
    tripped, reasons = evaluate_gates(drift, "new-high,new-package")
    assert not tripped
    assert reasons == []


# --- engines -------------------------------------------------------------


def test_mismatched_engines_are_diagnosed():
    drift = compute_drift(report(GOLEM), report(RUSI_CURRENT))
    assert any("differs from current engine" in d for d in drift["diagnostics"])


def test_engine_diagnostics_are_kept_apart_from_drift_diagnostics(rusi_pair):
    drift = compute_drift(*rusi_pair)
    assert drift["diagnostics"] == []
    assert drift["engineDiagnostics"]["current"], "rusi emits its own diagnostics"


# --- rendering and the command -------------------------------------------


def test_markdown_leads_with_a_coverage_warning():
    original = load(GOLEM)
    mutated = copy.deepcopy(original)
    mutated["dataFlow"]["slices"] = mutated["dataFlow"]["slices"][:100]
    markdown = render_markdown(compute_drift(report(GOLEM, original), report(GOLEM, mutated)))
    assert markdown.index("Coverage regressed") < markdown.index("RiskDelta")
    assert "A smaller run is not a safer one" in markdown


def test_command_writes_json_and_exits_zero(tmp_path):
    app = Application()
    tester = CommandTester(app.find("drift"))
    out = tmp_path / "drift.json"
    tester.execute(f"--old {RUSI_BASELINE} --new {RUSI_CURRENT} -f json -o {out}")
    assert tester.status_code == 0
    document = json.loads(out.read_text())
    assert document["driftVersion"] == 1
    assert len(document["MovedFlows"]) == 2


def test_command_exits_two_when_a_gate_trips(tmp_path):
    """Exit code 2 is the CI contract; 1 stays reserved for errors."""
    original = load(GOLEM)
    mutated = copy.deepcopy(original)
    mutated["dataFlow"]["slices"] = mutated["dataFlow"]["slices"][:100]
    base, current = tmp_path / "base.json", tmp_path / "current.json"
    base.write_text(json.dumps(original))
    current.write_text(json.dumps(mutated))
    app = Application()
    tester = CommandTester(app.find("drift"))
    tester.execute(f"--old {base} --new {current} -f json -o {tmp_path / 'd.json'}")
    assert tester.status_code == 2


def test_command_rejects_an_unknown_format():
    app = Application()
    tester = CommandTester(app.find("drift"))
    with pytest.raises(ValueError) as excinfo:
        tester.execute(f"--old {RUSI_BASELINE} --new {RUSI_CURRENT} -f yaml")
    assert "Unknown format" in str(excinfo.value)


def test_console_output_goes_through_cleo_io():
    """
    query-endpoints prints with bare print(), which bypasses cleo's io and hid
    an empty-listing regression from every test. drift must be capturable.
    """
    app = Application()
    tester = CommandTester(app.find("drift"))
    tester.execute(f"--old {RUSI_BASELINE} --new {RUSI_CURRENT}")
    output = tester.io.fetch_output()
    assert "~2 moved" in output
    assert "NewAnonymousEndpoints: not computed" in output


def test_align_roots_recovers_the_checkout_root_not_the_deepest_directory():
    """
    The root cannot be read off one report: golem's paths span both the repo
    and the Go module cache, so their longest common prefix is `/`. Alignment
    against the other side recovers the actual checkout root, and the deepest
    shared directory is not it.
    """
    original = load(GOLEM)
    rebased = rebase_paths(original, "/Users/prabhu/sandbox/ipsw", "/elsewhere/ci")
    old_paths = report_paths(report(GOLEM, original))
    new_paths = report_paths(report(GOLEM, rebased))
    assert align_roots(old_paths, new_paths) == (
        "/Users/prabhu/sandbox/ipsw",
        "/elsewhere/ci",
    )
    aligned = {normalize_path(p, "/Users/prabhu/sandbox/ipsw") for p in old_paths} & {
        normalize_path(p, "/elsewhere/ci") for p in new_paths
    }
    unstripped = {normalize_path(p, "") for p in old_paths} & {
        normalize_path(p, "") for p in new_paths
    }
    assert len(aligned) > len(unstripped) * 2


# --- the second real pair: golem, ~400 commits of ipsw --------------------


@pytest.fixture(scope="module")
def golem_pair():
    return report(GOLEM_BASELINE), report(GOLEM)


def test_real_golem_pair_separates_movement_from_new_risk(golem_pair):
    """
    Two real golem runs of ipsw, roughly 400 commits apart, generated from
    different directories. 91 flows moved without changing identity; a diff
    keyed on line numbers would have reported them as 91 further additions and
    91 further removals on top of the real ones.
    """
    drift = compute_drift(*golem_pair)
    assert drift["coverage"]["old"]["flows"] == 343
    assert drift["coverage"]["new"]["flows"] == 397
    assert len(drift["AddedFlows"]) == 159
    assert len(drift["RemovedFlows"]) == 105
    assert len(drift["MovedFlows"]) == 91
    assert drift["RiskDelta"]["NewHighSeverityFlows"] == 67
    assert drift["RiskDelta"]["NewMediumSeverityFlows"] == 92
    assert drift["RiskDelta"]["NewEntryPoints"] == 3
    assert drift["severitySources"] == {"baseline": ["engine"], "current": ["engine"]}


def test_both_sides_truncated_does_not_trip_the_coverage_gate(golem_pair):
    """
    Both golem runs hit the 1000-slice limit. Truncation is only a coverage
    *regression* when it is new -- otherwise every golem pair would fail the
    gate forever and the signal would be worthless.
    """
    drift = compute_drift(*golem_pair)
    assert drift["coverage"]["old"]["truncated"] is True
    assert drift["coverage"]["new"]["truncated"] is True
    assert not drift["coverage"]["regressed"]
    tripped, _ = evaluate_gates(drift, "new-package")
    assert not tripped


def test_golem_repo_paths_are_root_relative_across_directories(golem_pair):
    """The pair was generated from /tmp/claude-501/ipsw-base and ~/sandbox/ipsw.
    Repo files must compare as repo-relative or every one of them is churn."""
    drift = compute_drift(*golem_pair)
    files = [f["sink"]["file"] for f in drift["AddedFlows"]]
    assert "pkg/aea/aea.go" in files
    assert not any(f.startswith("/tmp/") for f in files)
    # Dependency-cache paths sit outside the repo root and stay absolute, with
    # their leading slash intact rather than mangled into a relative-looking one.
    cache = [f for f in files if "pkg/mod/" in f]
    assert cache and all(f.startswith("/") for f in cache)


def test_console_collapses_repeated_identical_lines(golem_pair):
    """
    Seventeen added flows share one identity, location and severity here.
    Printing each buries the rest of the diff, so repeats collapse to one line
    with a count -- while the json output keeps every record.
    """
    drift = compute_drift(*golem_pair)
    lines = render_console(drift)
    added = [line for line in lines if line.startswith("  + ")]
    assert len(added) < len(drift["AddedFlows"])
    assert any("ParsePKCS8PrivateKey" in line and "x17" in line for line in added)
    assert sum(int(line.rsplit("x", 1)[1]) if "  x" in line else 1 for line in added) == len(
        drift["AddedFlows"]
    )


# --- golden files ---------------------------------------------------------------


GOLDEN = Path("test/data/golden/drift")
# POSIX strings so the pinned "file" fields match on Windows too, where
# str(Path(...)) spells the same file with backslashes (see test_graph.py).
GOLDEN_PAIRS = {
    "golem": (GOLEM_BASELINE.as_posix(), GOLEM.as_posix()),
    "rusi": (RUSI_BASELINE.as_posix(), RUSI_CURRENT.as_posix()),
    "kosi": (KOSI_BASELINE.as_posix(), KOSI.as_posix()),
}


def _assert_golden(filename, text):
    golden = GOLDEN / filename
    if os.environ.get("ATOM_TOOLS_REGEN_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(text)
    assert golden.exists(), (
        f"missing golden file {golden}; regenerate with ATOM_TOOLS_REGEN_GOLDEN=1"
    )
    assert golden.read_text() == text


def _bounded_for_golden(drift):
    """The golem pair's flow lists run to 159 entries; a golden that size gets
    approved without being read. Keep a prefix and record the rest as a count —
    applied identically when regenerating and comparing, so the pinned prefix
    is exact and the tail is consciously not."""
    bounded = copy.deepcopy(drift)
    limits = {
        "AddedFlows": 5,
        "RemovedFlows": 5,
        "MovedFlows": 5,
        "WitnessChangedFlows": 5,
        "AddedEntryPoints": 3,
        "RemovedEntryPoints": 3,
        "AddedPackages": 3,
        "RemovedPackages": 3,
    }
    for key, keep in limits.items():
        flows = bounded.get(key) or []
        if len(flows) > keep:
            bounded[key] = flows[:keep] + [f"... {len(flows) - keep} more not pinned ..."]
    return bounded


@pytest.mark.parametrize("name", GOLDEN_PAIRS)
def test_golden_console_per_pair(name):
    """What the command prints per engine pair, default options.

    Regenerate with: ATOM_TOOLS_REGEN_GOLDEN=1 pytest test/test_drift.py
    """
    old_path, new_path = GOLDEN_PAIRS[name]
    text = "\n".join(render_console(compute_drift(report(old_path), report(new_path)))) + "\n"
    _assert_golden(f"{name}.console.txt", text)


@pytest.mark.parametrize("name", GOLDEN_PAIRS)
def test_golden_json_per_pair(name):
    """The json document exactly as ``-f json`` writes it (indent 4, sorted
    keys, plus a trailing newline), flow lists bounded for review."""
    old_path, new_path = GOLDEN_PAIRS[name]
    drift = _bounded_for_golden(compute_drift(report(old_path), report(new_path)))
    _assert_golden(f"{name}.json", json.dumps(drift, indent=4, sort_keys=True) + "\n")


def test_root_alignment_does_not_depend_on_the_host_separator():
    """The paths in a report are spelled by the machine that ran the *engine*.

    Reading them with ``os.sep`` made the answer depend on the machine running
    drift instead: a golem report full of ``/Users/...`` paths, diffed on
    Windows, produced no root at all and rendered every file at full length --
    which is what the drift goldens would have hit on the windows-latest CI
    leg. The logic now reads both separators, so a report keeps its root
    whichever host it is diffed on, and a Windows-spelled report is aligned
    just the same.
    """
    posix = [
        "/Users/prabhu/sandbox/ipsw/pkg/aea/aea.go",
        "/Users/prabhu/sandbox/ipsw/internal/commands/ent/ui.go",
    ]
    # Same repository, reported by an engine that ran on Windows.
    windows = [
        "C:\\work\\ipsw\\pkg\\aea\\aea.go",
        "C:\\work\\ipsw\\internal\\commands\\ent\\ui.go",
    ]
    old_root, new_root = align_roots(posix, windows)
    assert old_root == "/Users/prabhu/sandbox/ipsw"
    assert new_root == "C:/work/ipsw"
    assert {normalize_path(p, old_root) for p in posix} == {
        normalize_path(p, new_root) for p in windows
    } == {"pkg/aea/aea.go", "internal/commands/ent/ui.go"}
