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


# ----------------------------------------------------- kosi (synthetic wire)

# A minimal kosi report, transcribed from real 0.2.0 binary output (the
# committed kosi fixtures carry the full shapes). Kept inline so the adapter's
# contract — not the fixtures — is what these pin.
KOSI_SYNTHETIC = {
    "schemaVersion": "kosi/1",
    "tool": {"name": "kosi", "version": "0.2.0", "description": "kosi", "commit": "2e1f7b53"},
    "options": {"backend": "resolved", "dataflow": "all", "callgraph": "auto", "roots": ["all"]},
    "callGraph": None,
    "dataFlow": {
        "mode": "all",
        "nodes": [
            {
                "id": "dfn-000001",
                "name": "store vcommand",
                "kind": "source",
                "modulePath": ".",
                "purl": "pkg:generic/demo@unspecified",
                "filePath": "src/main/kotlin/Demo.kt",
                "position": {"filename": "src/main/kotlin/Demo.kt", "line": 12, "column": 5},
            },
            {
                "id": "dfn-000002",
                "name": "java.lang.ProcessBuilder",
                "kind": "sink",
                "modulePath": ".",
                "purl": "pkg:generic/demo@unspecified",
                "filePath": "src/main/kotlin/Demo.kt",
                "position": {"filename": "src/main/kotlin/Demo.kt", "line": 14, "column": 5},
            },
        ],
        "edges": [{"id": "dfe-000001", "kind": "data", "sourceId": "dfn-000001", "targetId": "dfn-000002"}],
        "slices": [
            {
                "id": "slice-000001",
                "sourceId": "dfn-000001",
                "sinkId": "dfn-000002",
                "sourceName": "endpoint-params fixtures.demo.Runner.run",
                "sinkName": "java.lang.ProcessBuilder",
                "sourceFunction": "fixtures.demo.Runner.run",
                "sinkFunction": "fixtures.demo.Runner.run",
                "sourceCategory": "untrusted-input",
                "sinkCategory": "process-exec",
                "severity": "critical",
                "confidence": "high",
                "riskScore": "9.0",
                "ruleId": "taint/untrusted-input-to-process-exec",
                "ruleName": "untrusted-input to process-exec",
                "description": "Value from untrusted-input reaches process-exec sink.",
                "purls": ["pkg:generic/demo@unspecified"],
                "taintKinds": ["untrusted-input"],
                "nodeIds": ["dfn-000001", "dfn-000002"],
                "edgeIds": ["dfe-000001"],
                "pathLength": 2,
                "sinkArgumentIndex": 0,
                "elided": None,
                "sanitizerNodeIds": [],
                "crossesModule": False,
                "crossesDependency": False,
                "reachableFromRoots": False,
                "rootWitness": [],
                "flowKey": "abc",
                "origins": ["pack"],
            }
        ],
    },
    "apiEndpoints": [
        {
            "id": "ep-000001",
            "framework": "javalin",
            # The writer spells it singular even though the data class says
            # httpMethods; read the wire, not the Kotlin.
            "httpMethod": ["GET", "POST"],
            "pathTemplate": "/demo",
            "handlerSymbol": "fixtures.demo.app$lambda1",
            "handlerCanonicalName": "fixtures.demo.app$lambda1",
            "modulePath": ".",
            "purl": "pkg:generic/demo@unspecified",
            "position": {"filename": "src/main/kotlin/DemoRoutes.kt", "line": 9, "column": 5},
            "authentication": ["role(ADMIN)"],
            "exported": None,
            "permissions": None,
            "deepLinkHosts": None,
            "pathParameters": [],
            "queryParameters": [],
            "consumes": [],
            "produces": [],
            "reachableSources": [],
            "sliceIds": [],
            "foundBy": "dsl",
        },
        {
            "id": "ep-000002",
            "framework": "android",
            "httpMethod": [],
            "pathTemplate": "MetaProvider",
            "handlerSymbol": "fixtures.demo.MetaProvider.query",
            "handlerCanonicalName": "fixtures.demo.MetaProvider.query",
            "modulePath": "",
            "purl": "",
            "position": {"filename": "/abs/AndroidManifest.xml", "line": 1, "column": 1},
            "authentication": [],
            "exported": False,
            "permissions": None,
            "deepLinkHosts": None,
            "pathParameters": [],
            "queryParameters": [],
            "consumes": [],
            "produces": [],
            "reachableSources": [],
            "sliceIds": [],
            "foundBy": "manifest",
        },
    ],
    "packages": [{"name": "demo", "purl": "pkg:generic/demo@unspecified", "modulePath": ".", "files": []}],
    "diagnostics": [],
    "stats": {"sliceCount": 1, "truncations": {}, "degraded": None},
}


def test_kosi_detect_requires_a_flow_or_endpoint_section():
    assert detect_engine(KOSI_SYNTHETIC) == "kosi"
    assert detect_engine({"tool": {"name": "kosi"}, "schemaVersion": "kosi/1"}) is None


def test_kosi_null_sections_are_not_computed_not_empty():
    content = {**KOSI_SYNTHETIC, "dataFlow": None, "callGraph": None}
    report = parse_report(content, source_file="kosi.json")
    assert report.flows == []
    # ``mode`` stays "none": the run said it did not compute data flow, which
    # is the same distinction the graph command draws for a missing graph.
    assert report.analysis_mode == "none"


def test_kosi_severity_and_categories_come_from_the_slice():
    report = parse_report(KOSI_SYNTHETIC, source_file="kosi.json")
    assert len(report.flows) == 1
    flow = report.flows[0]
    assert flow.severity == "error"  # critical folded
    assert flow.severity_source == "engine"
    assert flow.confidence == "high"
    assert flow.source_category == "untrusted-input"
    assert flow.sink_category == "process-exec"
    # kosi records categories on the slice, not its nodes; the terminal nodes
    # carry them so tag-driven consumers see the same thing they see for the
    # engines whose nodes carry categories.
    assert flow.source.tags == ["untrusted-input"]
    assert flow.sink.tags == ["process-exec"]
    assert flow.sink.role == "sink"
    # sinkArgumentIndex 0 is a real argument position and must survive the
    # truthiness filter the other extras use.
    assert flow.extra["sinkArgumentIndex"] == 0
    assert flow.extra["ruleId"] == "taint/untrusted-input-to-process-exec"


def test_kosi_endpoint_method_list_fans_out_and_empty_stays_unresolved():
    report = parse_report(KOSI_SYNTHETIC, source_file="kosi.json")
    # Two declared methods are two exposures, each keeping the verbatim record.
    demo = [e for e in report.endpoints if e["path"] == "/demo"]
    assert [e["method"] for e in demo] == ["GET", "POST"]
    assert demo[0]["raw"] is demo[1]["raw"]
    # An empty method list is not "any method": it means none was resolved.
    provider = next(e for e in report.endpoints if e["path"] == "MetaProvider")
    assert provider["method"] is None
    assert provider.get("methodUnresolved") is True
    assert provider["raw"]["exported"] is False


def test_kosi_stats_degradation_is_diagnosed():
    degraded = {
        **KOSI_SYNTHETIC,
        "stats": {"sliceCount": 1, "truncations": {"analysis-seconds": 1}, "degraded": "max-analysis-seconds"},
    }
    report = parse_report(degraded, source_file="kosi.json")
    assert any("max-analysis-seconds" in d for d in report.diagnostics)
    assert any("analysis-seconds" in d for d in report.diagnostics)
    assert report.provenance["degraded"] == "max-analysis-seconds"
    assert report.provenance["truncations"] == {"analysis-seconds": 1}


# ------------------------------------------- kosi (committed fixture counts)

KOSI = ECOSYSTEM / "kotlin-command-exec-kosi.json"
KOSI_BASELINE = ECOSYSTEM / "kotlin-command-exec-kosi-baseline.json"
KOSI_DSL = ECOSYSTEM / "kotlin-dsl-media-auth-kosi.json"
KOSI_ANDROID = ECOSYSTEM / "kotlin-android-manifest-app-kosi.json"
KOSI_CRYPTO = ECOSYSTEM / "kotlin-crypto-material-flow-kosi.json"


def test_kosi_flows_match_own_stats_block():
    content = load(KOSI)
    report = parse(KOSI)
    assert len(report.flows) == content["stats"]["sliceCount"] == 2
    assert len(report.flows) == len(content["dataFlow"]["slices"])
    # kosi emits its own severity; nothing here is taxonomy-derived.
    assert all(f.severity_source == "engine" for f in report.flows)
    assert {f.severity for f in report.flows} == {"error"}  # critical folded
    assert all(f.confidence == "high" for f in report.flows)
    # The whole report is committed, so its tables are the oracle.
    assert not [d for d in report.diagnostics if d.startswith("Dropped")]
    expected_nodes = sum(len(s["nodeIds"]) for s in content["dataFlow"]["slices"])
    assert sum(len(f.nodes) for f in report.flows) == expected_nodes


def test_kosi_endpoint_carries_the_engine_slice_link():
    content = load(KOSI)
    report = parse(KOSI)
    assert len(report.endpoints) == len(content["apiEndpoints"]) == 1
    # --endpoint-sources made the endpoint-rooted slice name its endpoint:
    # the one direct flow link the ecosystem emits besides dosai's verdicts.
    assert content["apiEndpoints"][0]["sliceIds"] == ["slice-000001"]
    endpoint = report.endpoints[0]
    assert endpoint["method"] == "GET"
    assert endpoint["handler"] == "fixtures.exec.CmdRunner.runCommand"
    assert endpoint["raw"]["reachableSources"] == ["untrusted-input"]


def test_kosi_endpoint_wire_names_are_read_not_assumed():
    report = parse(KOSI_DSL)
    d = load(KOSI_DSL)
    # 17 apiEndpoints in, 17 out: each declares a single method or none.
    assert len(report.endpoints) == len(d["apiEndpoints"]) == 17
    declared = sum(1 for e in d["apiEndpoints"] if e.get("httpMethod"))
    assert sum(1 for e in report.endpoints if e["method"]) == declared == 16
    # The writer emits httpMethod (singular) where the data class declares
    # httpMethods; parsing the data class's spelling would find nothing.
    assert all("httpMethod" in e for e in d["apiEndpoints"])
    assert not any("httpMethods" in e for e in d["apiEndpoints"])


def test_kosi_android_endpoints_exported_both_ways():
    d = load(KOSI_ANDROID)
    report = parse(KOSI_ANDROID)
    exported = [e["raw"]["exported"] for e in report.endpoints]
    assert exported.count(True) == 4
    assert exported.count(False) == 2
    assert len(report.endpoints) == len(d["apiEndpoints"]) == 6
    # Manifest endpoints are components, not HTTP routes: no method was
    # resolved and none may be invented.
    assert all(e["method"] is None and e.get("methodUnresolved") for e in report.endpoints)
    # Manifest endpoints USED to carry an absolute filename where source
    # endpoints carried a relative one, and the adapter reads the value
    # rather than either convention. kosi has since made them relative, so
    # what is pinned now is the current fact — and, more usefully, that no
    # filename here names this machine, because a fixture that bakes in a
    # developer's home directory is a fixture nobody else can verify.
    files = [e["position"]["filename"] for e in d["apiEndpoints"]]
    assert all(not f.startswith("/") for f in files), files
    assert all("/Users/" not in f for f in files), files


def test_kosi_unsubstantiated_endpoint_is_marked_not_dropped():
    """An endpoint kosi declared but read no code for is carried AND flagged.

    The manifest fixture names six components and kosi read the class behind
    five of them. The sixth is a declaration with nothing behind it: no
    handler was analysed, so no flow can ever reach it and zero weaknesses
    there means unexamined, not clean. Dropping it would hide a declared
    entry point; carrying it silently would publish an unexamined one as
    evidence. Both are wrong, so it is carried and flagged.
    """
    d = load(KOSI_ANDROID)
    report = parse(KOSI_ANDROID)
    on_the_wire = [e.get("substantiated") for e in d["apiEndpoints"]]
    assert on_the_wire.count(False) == 1, on_the_wire
    flagged = [e for e in report.endpoints if e.get("substantiated") is False]
    assert len(flagged) == 1
    # Only the false case travels: absent means substantiated or not stated,
    # and a key present on every endpoint would say nothing.
    assert all(
        "substantiated" not in e
        for e in report.endpoints
        if e["raw"].get("substantiated") is not False
    )


def test_kosi_runtime_provenance_is_read_now_that_kosi_writes_it():
    """``runtime`` used to be declared and dropped by the writer; it is not.

    ``native_image`` is the one that matters: kosi ships a native binary and
    a fat jar built from different metadata, and which artifact answered is
    a fact about how far to trust the report.
    """
    d = load(KOSI)
    assert isinstance(d.get("runtime"), dict), "kosi now writes runtime"
    report = parse(KOSI)
    assert report.provenance["native_image"] is d["runtime"]["nativeImage"]
    assert report.provenance["kotlin_version"] == d["runtime"]["kotlinVersion"]
    assert report.provenance["host"] == d["runtime"]["host"]


def test_kosi_syntax_backend_degrades_to_near_empty_with_a_named_reason():
    content = load(KOSI_BASELINE)
    report = parse(KOSI_BASELINE)
    assert content["dataFlow"] is not None or report.flows == []
    assert len(report.flows) == 0
    assert len(report.endpoints) == 0
    assert report.provenance["backend"] == "syntax"
    # The one honest trace of why is the diagnostics entry; it must survive.
    assert any("syntax-backend-no-resolution" in d for d in content["diagnostics"]) or any(
        "syntax-backend" in d for d in report.diagnostics
    )


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
    "kosi": _golden_input(KOSI),
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
