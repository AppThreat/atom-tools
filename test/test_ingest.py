"""Tests for the unified flow model, engine adapters and the ingest command.

Every count asserted here comes from the engines' own output — either the
``stats``/``Statistics`` block inside an untrimmed fixture section, or the
trimmed-fixture counts recorded in ``test/data/ecosystem/PROVENANCE.md``
(captured there mechanically at trimming time, before any of this code
existed). Nothing asserts a number this implementation produced in a vacuum.
"""

import hashlib
import json
import logging
import os
import re
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application
from atom_tools.lib.adapters import (
    detect_engine,
    ingest_inputs,
    normalize_engine_report,
    parse_report,
)
from atom_tools.lib.sarif import Sarif
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.stats import SliceStats
from atom_tools.lib.taxonomy import normalise_engine_severity
from atom_tools.lib.unified import merge_reports

ECOSYSTEM = Path(__file__).parent / "data" / "ecosystem"
DOSAI_DATAFLOWS = ECOSYSTEM / "dotnet-eshoponweb-dosai-dataflows.json"
DOSAI_METHODS = ECOSYSTEM / "dotnet-eshoponweb-dosai-methods.json"
DOSAI_CRYPTO = ECOSYSTEM / "dotnet-eshoponweb-dosai-crypto.json"
GOLEM = ECOSYSTEM / "go-ipsw-golem.json"
RUSI = ECOSYSTEM / "rust-microservices-kafka-rusi.json"
ATOM = Path(__file__).parent / "data" / "java-petclinic-reachables.json"

# Trimmed-fixture oracles recorded in PROVENANCE.md (the dosai reports were
# trimmed from the full runs whose Statistics blocks stay in the files).
DOSAI_KEPT_SLICES = 60
DOSAI_KEPT_ENDPOINTS = 60
DOSAI_KEPT_PACKAGES = 45
DOSAI_METHODS_ENDPOINTS = 53 + 57  # ApiEndpoints + EntryPoints
DOSAI_METHODS_PACKAGES = 81
# The full run's own Statistics (verbatim in the fixture, describes the run
# before trimming).
DOSAI_FULL_SLICE_COUNT = 904


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse(path, engine=None):
    return parse_report(load(path), source_file=str(path), engine=engine)


# ---------------------------------------------------------------- detection


def test_detect_engine_per_envelope():
    assert detect_engine(load(DOSAI_DATAFLOWS)) == "dosai"
    assert detect_engine(load(DOSAI_METHODS)) == "dosai"
    assert detect_engine(load(GOLEM)) == "golem"
    assert detect_engine(load(RUSI)) == "rusi"
    assert detect_engine(load(ATOM)) is None  # atom is the default, not detected
    assert detect_engine({"tool": {"name": "other"}}) is None


def test_endpoint_only_golem_extract_still_detected():
    # The endpoint-only extracts used by the OpenAPI converters keep their
    # historical handling but are still recognised engine reports.
    content = load(Path(__file__).parent / "data" / "go-gin-sample-golem.json")
    assert detect_engine(content) == "golem"


# ------------------------------------------- dosai (trimmed fixture counts)


def test_dosai_flows_match_provenance_counts():
    report = parse(DOSAI_DATAFLOWS)
    assert report.engine == "dosai"
    assert report.engine_version == "5.0.0.0"
    assert report.schema_version == "5.0.0"
    assert len(report.flows) == DOSAI_KEPT_SLICES == len(load(DOSAI_DATAFLOWS)["Slices"])
    assert len(report.endpoints) == DOSAI_KEPT_ENDPOINTS
    assert len(report.packages) == DOSAI_KEPT_PACKAGES
    # The full run's own Statistics block is preserved verbatim.
    assert load(DOSAI_DATAFLOWS)["Statistics"]["SliceCount"] == DOSAI_FULL_SLICE_COUNT
    # Hydration: every slice's NodeIds resolved (no drop diagnostics).
    assert not [d for d in report.diagnostics if d.startswith("Dropped")]
    expected_nodes = sum(len(s["NodeIds"]) for s in load(DOSAI_DATAFLOWS)["Slices"])
    assert sum(len(f.nodes) for f in report.flows) == expected_nodes


def test_dosai_severity_comes_from_engine():
    report = parse(DOSAI_DATAFLOWS)
    assert all(f.severity_source == "engine" for f in report.flows)
    by_slice = {
        s["Id"]: normalise_engine_severity(s["Severity"]) for s in load(DOSAI_DATAFLOWS)["Slices"]
    }
    assert all(f.severity == by_slice[f.id] for f in report.flows)
    assert {f.severity for f in report.flows} <= {"error", "warning", "note"}


def test_dosai_methods_report_has_no_flows_by_design():
    report = parse(DOSAI_METHODS)
    assert report.analysis_mode == "methods"
    assert report.flows == []
    assert len(report.endpoints) == DOSAI_METHODS_ENDPOINTS
    assert len(report.packages) == DOSAI_METHODS_PACKAGES


# ------------------------------------- golem/rusi (untrimmed: own counters)


def test_dosai_crypto_report_parses_its_nested_dataflows():
    """The crypto command nests the dataflows payload under CryptoDataFlows;
    the witness slices behind the crypto records (dfs1-3 of 629) parse as
    flows with mode 'crypto', and the engine's Pascal-case severities fold
    (Statistics.ReachableFindingCount 1 is cross-checked in test_crypto_reach)."""
    report = parse(DOSAI_CRYPTO)
    assert report.analysis_mode == "crypto"
    assert [f.id for f in report.flows] == ["dfs1", "dfs2", "dfs3"]
    assert all(f.severity == "error" for f in report.flows)  # engine "high"
    assert all(f.severity_source == "engine" for f in report.flows)
    assert len(report.endpoints) == 60  # CryptoDataFlows.EntryPoints, kept whole
    assert len(report.packages) == 43


def test_golem_flows_match_own_stats_block():
    content = load(GOLEM)
    report = parse(GOLEM)
    stats = content["dataFlow"]["stats"]
    assert len(report.flows) == stats["sliceCount"] == 397
    assert all(f.severity_source == "engine" for f in report.flows)
    assert len(report.endpoints) == content["stats"]["apiEndpointCount"] == 57
    # The engine flagged report-level truncation; it must survive into
    # diagnostics, never silently dropped.
    assert stats["truncated"] is True
    assert any("truncated" in d for d in report.diagnostics)


def test_golem_purl_set_matches_slices():
    content = load(GOLEM)
    report = parse(GOLEM)
    expected = {p for s in content["dataFlow"]["slices"] for p in (s.get("purls") or [])}
    assert {p for f in report.flows for p in f.purls} == expected


def test_rusi_flows_match_own_stats_block():
    content = load(RUSI)
    report = parse(RUSI)
    assert len(report.flows) == content["stats"]["data_flow_slice_count"] == 5
    assert len(report.flows) == content["data_flow"]["stats"]["slice_count"]
    # rusi slices carry no severity: levels must be labelled derived, never
    # presented as engine judgements.
    assert all(f.severity_source == "derived" for f in report.flows)
    assert len(report.endpoints) == content["stats"]["api_endpoint_count"] == 14
    # Every node id resolved.
    assert not [d for d in report.diagnostics if d.startswith("Dropped")]
    expected_nodes = sum(len(s["node_ids"]) for s in content["data_flow"]["slices"])
    assert sum(len(f.nodes) for f in report.flows) == expected_nodes


# --------------------------------------------------------------------- atom


def test_atom_reachables_ingest():
    report = parse(ATOM, engine="atom")
    entries = load(ATOM)
    assert report.engine == "atom"
    assert len(report.flows) == len(entries) == 163
    assert all(f.severity_source == "derived" for f in report.flows)
    assert {p for f in report.flows for p in f.purls} == {
        p for e in entries for p in (e.get("purls") or [])
    }


# ---------------------------------------------------- hydration & escape hatch


def test_unresolvable_node_ids_drop_with_diagnostic(caplog):
    content = load(DOSAI_DATAFLOWS)
    content["Slices"] = content["Slices"][:1]
    content["Slices"][0]["NodeIds"] = content["Slices"][0]["NodeIds"] + ["dfn-does-not-exist"]
    with caplog.at_level(logging.WARNING):
        report = parse_report(content, engine="dosai")
    assert report.flows == []
    assert any(
        re.search(r"Dropped 1 dosai slice\(s\).*dfn-does-not-exist", d) for d in report.diagnostics
    )
    assert "Dropped 1 dosai slice" in caplog.text


def test_raw_and_extra_survive_ingest():
    report = parse(DOSAI_DATAFLOWS)
    slice_raw = load(DOSAI_DATAFLOWS)["Slices"][0]
    flow = next(f for f in report.flows if f.id == slice_raw["Id"])
    assert flow.raw == slice_raw  # escape hatch: the original record, untouched
    assert flow.extra["SinkPurl"] == slice_raw["SinkPurl"]
    golem_report = parse(GOLEM)
    golem_slice = load(GOLEM)["dataFlow"]["slices"][0]
    golem_flow = next(f for f in golem_report.flows if f.id == golem_slice["id"])
    assert golem_flow.raw == golem_slice
    assert golem_flow.extra["riskScore"] == golem_slice["riskScore"]


# --------------------------------------------------------- schema drift


def test_newer_dosai_schema_warns_and_still_ingests():
    content = load(DOSAI_DATAFLOWS)
    content["Metadata"]["SchemaVersion"] = "6.0.0"
    report = parse_report(content, engine="dosai")
    assert len(report.flows) == DOSAI_KEPT_SLICES  # never hard-fail
    assert any("6.0.0" in d and "schema version" in d for d in report.diagnostics)


def test_newer_golem_schema_uri_warns_and_still_ingests():
    content = load(GOLEM)
    content["schemaVersion"] = "https://cdxgen.github.io/cdxgen-plugins-bin/golem/schema/v7"
    report = parse_report(content, engine="golem")
    assert len(report.flows) == 397
    assert any("v7" in d and "schema version" in d for d in report.diagnostics)


# --------------------------------------------------- compat emit & commands


def test_emit_reachables_loads_through_atomslice(tmp_path):
    document = normalize_engine_report(load(GOLEM), str(GOLEM))
    assert document is not None
    assert len(document["reachables"]) == 397
    assert len(document["apiEndpoints"]) == 57  # endpoint keys preserved
    compat_file = tmp_path / "golem-compat.json"
    compat_file.write_text(json.dumps(document), encoding="utf-8")
    atom_slice = AtomSlice(compat_file)
    assert atom_slice.slice_type == "reachables"
    stats = SliceStats(atom_slice.content, atom_slice.slice_type).to_dict()
    assert stats["flow_groups"] == 397


def test_dosai_sarif_carries_engine_severities(tmp_path):
    document = normalize_engine_report(load(DOSAI_DATAFLOWS), str(DOSAI_DATAFLOWS))
    compat_file = tmp_path / "dosai-compat.json"
    compat_file.write_text(json.dumps(document), encoding="utf-8")
    sarif = Sarif(str(compat_file), "dotnet").convert()
    results = sarif["runs"][0]["results"]
    assert len(results) == DOSAI_KEPT_SLICES
    assert all(r["properties"]["severitySource"] == "engine" for r in results)
    levels = {}
    expected = {}
    for s in load(DOSAI_DATAFLOWS)["Slices"]:
        level = normalise_engine_severity(s["Severity"])
        expected[level] = expected.get(level, 0) + 1
    for r in results:
        levels[r["level"]] = levels.get(r["level"], 0) + 1
    assert levels == expected


# ------------------------------------------------------------- multi-input


def test_mixed_engine_ingest():
    report = ingest_inputs([str(GOLEM), str(RUSI)])
    assert report.engine == "golem+rusi"
    assert len(report.flows) == 397 + 5
    assert [s["engine"] for s in report.provenance["sources"]] == ["golem", "rusi"]


def test_merge_reports_rejects_empty():
    with pytest.raises(ValueError):
        merge_reports([])


def test_unknown_document_without_engine_raises():
    with pytest.raises(ValueError, match="--engine"):
        parse_report({"something": "else"})


# ------------------------------------------------------------- taxonomy


def test_severity_normalisation():
    assert normalise_engine_severity("High") == "error"
    assert normalise_engine_severity("critical") == "error"
    assert normalise_engine_severity("Medium") == "warning"
    assert normalise_engine_severity("info") == "note"
    assert normalise_engine_severity(None) is None
    assert normalise_engine_severity("bogus") is None


# ------------------------------- engine tags reach tag-driven consumers


def test_compat_nodes_carry_mapped_chen_tags():
    """Engine categories must also appear as their chen equivalent.

    Without the mapping a golem 'configuration' source and 'external-service'
    sink are invisible to every tag-driven consumer (stats source/sink
    counting, filter, sarif rule derivation), which silently reported zero
    sources and zero sinks for a report with 397 flows.
    """
    document = normalize_engine_report(load(GOLEM), str(GOLEM))
    entry = document["reachables"][0]
    source_tags = entry["flows"][0]["tags"].split(",")
    sink_tags = entry["flows"][-1]["tags"].split(",")
    # The raw engine category is preserved for fidelity ...
    assert "configuration" in source_tags
    assert "external-service" in sink_tags
    # ... and the chen equivalent is added alongside it.
    assert "framework-input" in source_tags
    assert "service-egress" in sink_tags


def test_stats_counts_engine_sources_and_sinks():
    from atom_tools.lib.slices import AtomSlice
    from atom_tools.lib.stats import SliceStats

    atom_slice = AtomSlice(str(GOLEM))
    stats = SliceStats(atom_slice.content, atom_slice.slice_type, str(GOLEM)).to_dict()
    assert stats["flow_groups"] == 397
    assert stats["sources"] > 0
    assert stats["sinks"] > 0


# ------------------------------------------- truncation stays visible


def test_truncated_run_is_reported_to_the_reader():
    """A run the engine cut short must not read as a complete picture."""
    from atom_tools.lib.slices import AtomSlice
    from atom_tools.lib.stats import SliceStats

    document = normalize_engine_report(load(GOLEM), str(GOLEM))
    provenance = document["analysisProvenance"]
    assert provenance["dataflow_truncated"] is True
    assert any("truncated" in d for d in provenance["diagnostics"])

    atom_slice = AtomSlice(str(GOLEM))
    stats = SliceStats(atom_slice.content, atom_slice.slice_type, str(GOLEM)).to_dict()
    assert stats["analysis"]["dataflow_truncated"] is True


def test_atom_slices_have_no_analysis_block():
    """atom output is unchanged: no engine provenance key is invented for it."""
    from atom_tools.lib.slices import AtomSlice
    from atom_tools.lib.stats import SliceStats

    atom_slice = AtomSlice("test/data/java-petclinic-reachables.json")
    stats = SliceStats(atom_slice.content, atom_slice.slice_type, "").to_dict()
    assert "analysis" not in stats


# --- malformed input reporting -------------------------------------------------


INVALID_JSON = Path(__file__).parent / "data" / "invalid.json"


def test_malformed_json_names_the_file_and_position():
    """A truncated or wrong file reports its own path and parse position, not
    a bare 'Expecting value: line 5 column 1' into a file that is never named."""
    with pytest.raises(
        ValueError,
        match=r"could not read the report .*invalid\.json:"
        r" Expecting value: line 5 column 1",
    ):
        run_ingest(f"-i {INVALID_JSON}")


def test_unmatched_input_warns_once_and_exits_non_zero(caplog):
    """One line for a missing input: expand_inputs names the unmatched part;
    the command no longer repeats the same fact a second time."""
    with caplog.at_level(logging.WARNING):
        tester = run_ingest("-i /definitely/not/a/slice.json")
    assert tester.status_code == 1
    assert caplog.text.count("/definitely/not/a/slice.json") == 1


# --- golden files ---------------------------------------------------------------


GOLDEN = Path("test/data/golden/ingest")
# The unified document embeds the input path verbatim (source_file and
# provenance.sources[].file), and the goldens below pin the document's md5 —
# so the invocation must spell the input identically on every machine and
# OS. The absolute per-checkout spelling str(Path(__file__) ...) produces
# would change the digest on every clone; a repo-relative POSIX string is
# stable everywhere (Windows opens forward-slash paths fine). chdir to the
# repo root in each test so the relative string resolves from any cwd.
REPO = Path(__file__).resolve().parent.parent


def _golden_input(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


GOLDEN_FIXTURES = {
    "dosai": _golden_input(DOSAI_DATAFLOWS),
    "golem": _golden_input(GOLEM),
    "rusi": _golden_input(RUSI),
    "atom": _golden_input(ATOM),
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


def run_ingest(args):
    app = Application()
    tester = CommandTester(app.find("ingest"))
    tester.execute(args)
    return tester


@pytest.mark.parametrize("name", GOLDEN_FIXTURES)
def test_golden_console_line_per_fixture(name, tmp_path, monkeypatch):
    """ingest's console rendering is the one summary line; these are also the
    file's only CLI wiring assertions (output goes through cleo's io).

    Regenerate with: ATOM_TOOLS_REGEN_GOLDEN=1 pytest test/test_ingest.py
    """
    monkeypatch.chdir(REPO)
    out = tmp_path / "unified.json"
    tester = run_ingest(f"-i {GOLDEN_FIXTURES[name]} -o {out}")
    assert tester.status_code == 0
    # tmp_path is a per-run temp directory; only the placeholder is stable.
    text = tester.io.fetch_output().replace(str(tmp_path), "<tmp>")
    _assert_golden(f"{name}.console.txt", text)


def test_golden_console_line_reachables_emit(tmp_path, monkeypatch):
    """The --emit reachables half of the split, whose line says flow group(s)."""
    monkeypatch.chdir(REPO)
    out = tmp_path / "reachables.json"
    tester = run_ingest(f"-i {_golden_input(RUSI)} --emit reachables -o {out}")
    assert tester.status_code == 0
    text = tester.io.fetch_output().replace(str(tmp_path), "<tmp>")
    _assert_golden("rusi-reachables.console.txt", text)


@pytest.mark.parametrize("name", GOLDEN_FIXTURES)
def test_golden_unified_document_per_fixture(name, tmp_path, monkeypatch):
    """The unified document is 40 KB to 3.7 MB per engine — not reviewable as
    a whole-file golden. Pin its exact bytes by md5 plus the readable head a
    reviewer needs: engine facts, counts, and the first flow and endpoint
    verbatim. The digest makes any change anywhere trip; the head makes the
    regen diff readable."""
    monkeypatch.chdir(REPO)
    out = tmp_path / "unified.json"
    tester = run_ingest(f"-i {GOLDEN_FIXTURES[name]} -o {out}")
    assert tester.status_code == 0
    document = json.loads(out.read_text())
    summary = [
        f"unified document md5: {hashlib.md5(out.read_bytes()).hexdigest()}",
        f"engine: {document['engine']}"
        f" {document.get('engine_version') or '(no version recorded)'}"
        f", mode {document.get('analysis_mode') or 'none'}",
        f"counts: {len(document['flows'])} flow(s),"
        f" {len(document['endpoints'])} endpoint(s),"
        f" {len(document.get('packages') or [])} package(s),"
        f" {len(document.get('diagnostics') or [])} diagnostic(s)",
    ]
    if document["flows"]:
        summary.append(
            "flow[0]: " + json.dumps(document["flows"][0], indent=2, sort_keys=True)
        )
    else:
        summary.append("flows: (none)")
    if document["endpoints"]:
        summary.append(
            "endpoint[0]: " + json.dumps(document["endpoints"][0], indent=2, sort_keys=True)
        )
    else:
        summary.append("endpoints: (none) — atom reachables carry no endpoint table")
    _assert_golden(f"{name}.unified.txt", "\n".join(summary) + "\n")
