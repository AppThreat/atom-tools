"""Tests for the graph command and the call-graph metrics it computes.

The committed fixtures are the oracle, and the numbers below were measured
against them (see PROVENANCE.md for how each fixture was produced and
trimmed). Two suites of numbers matter most here:

**The fan-in disagreement is a feature.** dosai's FanIn/FanOut were computed
over the engine's full 21,570-node run; the fixture keeps a contiguous
300-edge slice. A recomputation over the slice's own edges therefore matches
only 266 of 315 nodes on FanIn (311 on FanOut), and the engine's FanIn sums
to 448 against 300 edges. These tests pin that disagreement — a graph
command that silently recomputed (or a fixture re-trimmed until the numbers
agreed) would fail them.

**The dead-code trap stays closed.** Only 20 of 315 dosai Reachability
entries name a reachable entry point, so a naive metric would announce 295
deletable functions while the engine's own DeadCode array is empty. The
tests assert the engine's verdict is what gets reported, with the caveat
attached.
"""

import copy
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application
from atom_tools.lib import callgraph as cg
from atom_tools.lib.adapters import parse_report

ECOSYSTEM = Path("test/data/ecosystem")
DOSAI_DATAFLOWS = ECOSYSTEM / "dotnet-eshoponweb-dosai-dataflows.json"
DOSAI_METHODS = ECOSYSTEM / "dotnet-eshoponweb-dosai-methods.json"
GOLEM = ECOSYSTEM / "go-ipsw-golem.json"
RUSI = ECOSYSTEM / "rust-microservices-kafka-rusi.json"
ATOM_CPG = ECOSYSTEM / "java-petclinic-atom-cpg.graphml"
ATOM_CENTRALITY = ECOSYSTEM / "java-petclinic-atom-centrality.json"
ATOM_SCC = ECOSYSTEM / "java-petclinic-atom-scc.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def dosai_graph():
    return cg.load_dosai(load_json(DOSAI_METHODS), str(DOSAI_METHODS))


@pytest.fixture(scope="module")
def golem_graph():
    return cg.load_golem(load_json(GOLEM), str(GOLEM))


@pytest.fixture(scope="module")
def rusi_graph():
    return cg.load_rusi(load_json(RUSI), str(RUSI))


@pytest.fixture(scope="module")
def atom_graph():
    return cg.load_atom_graphml(str(ATOM_CPG))


# --- engine metrics are carried verbatim, and the disagreement is pinned -----


def test_dosai_fan_in_fan_out_are_the_engines_values(dosai_graph):
    """The join to Reachability[] is exact: every node carries the engine's
    FanIn/FanOut for its NodeId, and nothing is recomputed."""
    reach = {r["NodeId"]: r for r in load_json(DOSAI_METHODS)["Reachability"]}
    assert len(dosai_graph.nodes) == 315
    for node in dosai_graph.nodes:
        assert node.fan_in == reach[node.id]["FanIn"]
        assert node.fan_out == reach[node.id]["FanOut"]
    assert sum(n.fan_in for n in dosai_graph.nodes) == 448
    assert sum(n.fan_out for n in dosai_graph.nodes) == 309


def test_recomputed_fan_in_over_the_slice_disagrees_with_the_engine(dosai_graph):
    """The fixture is an honest slice: recomputing over its 300 edges must
    NOT reproduce the engine's whole-run numbers. These figures are the
    proof the command is not silently recomputing."""
    fan_in, fan_out = {}, {}
    for edge in dosai_graph.edges:
        fan_out[edge.caller] = fan_out.get(edge.caller, 0) + 1
        fan_in[edge.callee] = fan_in.get(edge.callee, 0) + 1
    in_matches = sum(1 for n in dosai_graph.nodes if n.fan_in == fan_in.get(n.id, 0))
    out_matches = sum(1 for n in dosai_graph.nodes if n.fan_out == fan_out.get(n.id, 0))
    assert len(dosai_graph.edges) == 300
    assert in_matches == 266  # 49 nodes disagree
    assert out_matches == 311  # 4 nodes disagree
    assert sum(fan_in.values()) == 300  # != the engine's 448


def test_golem_reachability_verdicts_are_preserved_verbatim(golem_graph):
    """golem's reachability.nodes is a boolean per node — there is no path
    witness to recompute. The per-node verdicts must be exactly the
    engine's, including the 984-of-986-unreachable verdict the engine gives
    these nodes over its full run (its own 186 init/main roots are not part
    of this endpoint-anchored subgraph)."""
    raw = {
        r["nodeId"]: r["reachableFromRoots"]
        for r in load_json(GOLEM)["callGraph"]["reachability"]["nodes"]
    }
    verdicts = {
        n.id: n.reachable_from_roots
        for n in golem_graph.nodes
        if n.reachable_from_roots is not None
    }
    assert verdicts == {k: v for k, v in raw.items() if k in verdicts}
    assert len(verdicts) == 986
    assert sum(1 for v in verdicts.values() if v) == 2


def test_golem_reports_itself_as_trimmed(golem_graph):
    assert golem_graph.trimmed
    assert golem_graph.full_nodes == 7848 and golem_graph.full_edges == 22308
    assert golem_graph.engine_root_reasons == {"init": 184, "main": 2}
    assert sum(1 for r in golem_graph.engine_roots if r in golem_graph.by_id) == 0


# --- kosi: one whole graph, verdicts carried ---------------------------------


@pytest.fixture(scope="module")
def kosi_graph():
    return cg.load_kosi(load_json(ECOSYSTEM / "kotlin-dsl-media-auth-kosi.json"), str(ECOSYSTEM / "kotlin-dsl-media-auth-kosi.json"))


def test_kosi_graph_is_whole_and_its_verdicts_are_verbatim(kosi_graph):
    """The fixture commits kosi's whole callGraph section, so counts are the
    engine's own; the reachability entries carry the run's
    reach-from-root-scopes verdict per node (73 of 83 reachable), exactly as
    emitted. kosi has since learned to resolve lambda-valued calls, which is
    why the edge mix is no longer static-only."""
    assert kosi_graph.engine == "kosi"
    assert len(kosi_graph.nodes) == 83
    assert len(kosi_graph.edges) == 52
    assert kosi_graph.call_type_mix() == {"static": 31, "lambda-value": 21}
    verdicts = [n.reachable_from_roots for n in kosi_graph.nodes if n.reachable_from_roots is not None]
    assert len(verdicts) == 83
    assert sum(1 for v in verdicts if v) == 73
    # kosi nodes name their functions (canonicalName) — anchoring goes
    # through the same name index rusi's opaque ids need.
    assert any(n.name == "fixtures.dslmedia.DeniedServlet.doGet" for n in kosi_graph.nodes)


def test_kosi_dead_code_is_the_engine_verdict(kosi_graph):
    result = cg.compute_dead_code(kosi_graph)
    assert result["computed"] is True
    assert result["source"] == "engine"
    assert result["unreachableFromRootsPerEngine"] == 10
    assert result["nodesWithVerdict"] == 83
    assert any("not a deletability" in d for d in result["diagnostics"])


# --- dispatch confidence ------------------------------------------------------


def test_confidence_tiers_are_ordered_and_validated():
    assert cg.CONFIDENCE_TIERS == ("exact", "external", "candidate", "unknown")
    with pytest.raises(ValueError, match="Unknown confidence"):
        cg.filter_by_confidence([rusi_graph], "probable")


def test_min_confidence_exact_strictly_reduces_rusi(rusi_graph):
    """rusi is the real test bed for confidence filtering: seven call types
    and candidate_count on 181 edges. `exact` keeps only static+trait-impl."""
    (filtered,), reports = cg.filter_by_confidence([rusi_graph], "exact")
    report = reports[0]
    assert report["edgesBefore"] == 2156
    assert report["edgesKept"] == 308  # 306 static + 2 trait-impl
    assert report["edgesDropped"] == 1848
    assert len(filtered.edges) == 308
    assert set(e.call_type for e in filtered.edges) == {"static", "trait-impl"}


def test_min_confidence_is_a_reported_no_op_on_golem(golem_graph):
    """golem's graph is single-valued (3,325 of 3,325 static): the filter
    cannot reduce it, and that is stated, not passed through silently."""
    (filtered,), reports = cg.filter_by_confidence([golem_graph], "exact")
    assert len(filtered.edges) == 3325
    assert reports[0]["edgesDropped"] == 0
    assert "no-op" in reports[0]["note"]
    assert "same confidence tier" in reports[0]["note"]


def test_rusi_confidence_mix_and_candidate_counts(rusi_graph):
    mix = rusi_graph.confidence_mix()
    assert mix == {"candidate": 278, "exact": 308, "external": 1570}
    counted = [e.candidate_count for e in rusi_graph.edges if e.candidate_count]
    assert len(counted) == 181
    # The over-approximation spread the engine actually recorded: 2..37
    # candidates per edge (the 37s are macro-generated match arms).
    assert min(counted) == 2 and max(counted) == 37


def test_dosai_confidence_comes_from_dispatch_and_evidence(dosai_graph):
    """DispatchConfidence is set on exactly the 4 cha-candidate edges; the
    other 296 carry Roslyn-direct evidence and are exact."""
    assert dosai_graph.confidence_mix() == {"candidate": 4, "exact": 296}
    assert sum(1 for e in dosai_graph.edges if e.dispatch_confidence) == 4


# --- external nodes -----------------------------------------------------------


def test_rusi_external_edges_are_pure_leaf_calls(rusi_graph):
    """1,570 of 2,156 edges leave the workspace, and not one of them
    originates from an external node — which is why rankings exclude
    external nodes by default rather than letting third-party leaves
    dominate them."""
    external = {n.id for n in rusi_graph.nodes if n.external}
    assert len(external) == 341
    assert sum(1 for e in rusi_graph.edges if e.callee in external) == 1570
    assert sum(1 for e in rusi_graph.edges if e.caller in external) == 0


def test_centrality_excludes_external_nodes_by_default(rusi_graph):
    document = cg.compute_centrality(rusi_graph)
    assert len(document["ranked"]) == 371  # internal only
    assert all(not row["external"] for row in document["ranked"])
    assert document["externalNodesExcludedFromRanking"] == 341
    with_external = cg.compute_centrality(rusi_graph, include_external=True)
    assert len(with_external["ranked"]) == 712
    assert abs(sum(r["pageRank"] for r in with_external["ranked"]) - 1.0) < 1e-3


# --- chokepoints --------------------------------------------------------------


def test_golem_chokepoints_join_the_flow_model(golem_graph):
    """Sources and sinks come from the flow model anchored in the call
    graph (13 of 58 source functions and 27 of 77 sinks anchor), and the
    betweenness ranking over those pairs is non-trivial."""
    from atom_tools.lib.adapters import parse_report

    report = parse_report(load_json(GOLEM), source_file=str(GOLEM))
    sources, sinks = cg.flow_functions(report)
    assert len(sources) == 58 and len(sinks) == 77
    result = cg.compute_chokepoints(golem_graph, flow_sources=sources, flow_sinks=sinks)
    assert result["seeds"]["policy"] == "flow-sources→flow-sinks"
    assert result["seeds"]["sources"] == 13 and result["seeds"]["sinks"] == 27
    assert result["seeds"]["pairs"] == 48
    assert len(result["ranked"]) == 16
    assert result["ranked"][0]["betweenness"] == 2.0
    assert "capped" not in result


def test_chokepoint_cap_is_reported_never_silent(dosai_graph):
    """dosai has no flow model in a methods report and no entry point in
    the slice, so seeds fall back to 106 zero-in-degree nodes — more than
    the default cap of 64. The cap must be visible in the result and in
    the console rendering."""
    result = cg.compute_chokepoints(dosai_graph)
    assert result["seeds"]["policy"] == "zero-indegree"
    assert result["seeds"]["source"] == "derived"
    assert result["capped"] == {
        "sourcesEnumerated": 64,
        "sourcesAvailable": 106,
        "effect": "betweenness scores are a lower bound",
    }
    document = cg.compute_graph_document([dosai_graph], "chokepoints")
    console = "\n".join(cg.render_console(document))
    assert "PATH ENUMERATION CAPPED at 64 of 106 source nodes" in console
    assert "lower bound" in console
    # raising the cap above the seed count removes the cap entirely
    uncapped = cg.compute_chokepoints(dosai_graph, max_sources=200)
    assert "capped" not in uncapped


def test_chokepoint_betweenness_on_a_constructed_graph():
    """a→b→d, a→c→d: b and c each carry every a→d path; d is a sink (never
    ranked), a a source; an isolated node scores nothing."""
    nodes = [cg.CallNode(id=i, name=i, external=False) for i in ("a", "b", "c", "d", "lonely")]
    edges = [
        cg.CallEdge(caller="a", callee="b", confidence="candidate"),
        cg.CallEdge(caller="b", callee="d", confidence="candidate"),
        cg.CallEdge(caller="a", callee="c", confidence="candidate"),
        cg.CallEdge(caller="c", callee="d", confidence="candidate"),
    ]
    graph = cg.UnifiedCallGraph(
        engine="synthetic", source_file="synthetic", nodes=nodes, edges=edges
    )
    result = cg.compute_chokepoints(graph, flow_sources={"a"}, flow_sinks={"d"})
    scores = {row["id"]: row["betweenness"] for row in result["ranked"]}
    # Two equal a→d shortest paths: b and c each carry half the pair's paths.
    assert scores == {"b": 0.5, "c": 0.5}
    assert result["seeds"]["pairs"] == 1
    # an exact-only filter removes every edge: no path, no chokepoint
    (filtered,), _ = cg.filter_by_confidence([graph], "exact")
    filtered_result = cg.compute_chokepoints(filtered, flow_sources={"a"}, flow_sinks={"d"})
    assert filtered_result["ranked"] == []


# --- blast radius -------------------------------------------------------------


def test_blast_radius_of_a_leaf_is_itself(golem_graph):
    """An external leaf with no outgoing edge reaches exactly itself."""
    result = cg.compute_blast_radius(golem_graph, "(*github.com/apex/log.Entry).Debug")
    assert result["reachIncludingSelf"] == 1
    assert result["internalReachable"] == 0 and result["externalReachable"] == 1
    assert result["maxDepth"] == 0


def test_blast_radius_of_a_root_is_the_reachable_component(rusi_graph):
    result = cg.compute_blast_radius(rusi_graph, "common_security::load_jwk_decoders")
    assert result["reachIncludingSelf"] == 13
    assert result["internalReachable"] == 4 and result["externalReachable"] == 9
    assert result["maxDepth"] == 2
    assert "Box::new" in result["externalTargets"]


def test_blast_radius_rejects_unknown_nodes(rusi_graph):
    with pytest.raises(ValueError, match="not a node id and not a unique node name"):
        cg.compute_blast_radius(rusi_graph, "no such function")


# --- entry depth --------------------------------------------------------------


def test_dosai_entry_depth_is_the_engines_own(dosai_graph):
    """dosai computes DepthFromEntryPoint on exactly the nodes it deems
    reachable from entry points — 20 of 315 — and those values are carried
    as the engine's, with nothing derived beside them: the engine's entry
    points are not nodes of the slice, so a BFS here could not reproduce
    depths the engine measured over its full run."""
    result = cg.compute_entry_depth(dosai_graph)
    assert result["engineDepths"] == 20 and result["derivedDepths"] == 0
    assert all(row["depthSource"] == "engine" for row in result["depths"])
    depths = sorted(row["depth"] for row in result["depths"])
    assert depths == [1] * 6 + [2] * 14
    assert result["engineUnreachableFromEntryPoints"] == 295
    assert any("unreachable from any entry point" in d for d in result["diagnostics"])


def test_golem_entry_depth_uses_the_engines_min_depth_where_it_has_one(golem_graph):
    """
    golem supplies depth itself, in reachability.nodes[].minDepth. It is
    omitempty, so it appears only on nodes the engine found reachable from its
    own roots -- 2 of 986 in this endpoint-anchored subgraph, against 593 of
    6090 in the untrimmed run. Those two are carried as `engine` and are never
    recomputed; the rest are derived by BFS from the 28 endpoint handlers that
    anchor, and the two sources are reported separately rather than blended.
    """
    from atom_tools.lib.adapters import parse_report

    report = parse_report(load_json(GOLEM), source_file=str(GOLEM))
    result = cg.compute_entry_depth(golem_graph, report.endpoints)
    assert result["seeds"]["policy"] == "endpoints"
    assert result["seeds"]["sources"] == 28
    engine_rows = [r for r in result["depths"] if r["depthSource"] == "engine"]
    derived_rows = [r for r in result["depths"] if r["depthSource"] == "derived"]
    assert len(engine_rows) == 2
    assert result["derivedDepths"] == len(derived_rows)
    # The engine's own value, verbatim, with its rootIds carried as entry points.
    apex = next(r for r in engine_rows if r["id"] == "github.com/apex/log.Error")
    assert apex["depth"] == 2
    assert apex["entryPoints"] == [
        "github.com/blacktop/ipsw/cmd/ipsw.main",
        "github.com/blacktop/ipsw/cmd/ipswd.main",
    ]
    # No node is reported twice, and no derived row shadows an engine one.
    assert len({r["id"] for r in result["depths"]}) == len(result["depths"])
    assert not {r["id"] for r in engine_rows} & {r["id"] for r in derived_rows}


def test_golem_witness_paths_are_read_when_the_run_supplies_them():
    """
    golem's reachability.paths is real -- computeWitnessPaths, gated behind
    --reachable-symbols -- and omitempty, so every fixture here lacks it.
    Absent must mean "not requested", never "golem cannot produce it", so the
    loader reads the section when it is present.
    """
    content = load_json(GOLEM)
    assert "paths" not in content["callGraph"]["reachability"]
    node_ids = [n["id"] for n in content["callGraph"]["nodes"][:2]]
    content["callGraph"]["reachability"]["paths"] = [
        {"symbol": "crypto/x509.ParsePKCS8PrivateKey", "nodeIds": node_ids,
         "edgeIds": ["e1"], "depth": 2}
    ]
    graph = cg.load_golem(content, str(GOLEM))
    assert len(graph.engine_witness_paths) == 1
    assert graph.engine_witness_paths[0]["symbol"] == "crypto/x509.ParsePKCS8PrivateKey"
    assert graph.engine_witness_paths[0]["nodeIds"] == node_ids


# --- dead-code: the engine's verdict or nothing -------------------------------


def test_dosai_dead_code_is_the_engines_empty_list_not_295(dosai_graph):
    result = cg.compute_dead_code(dosai_graph)
    assert result["computed"] and result["source"] == "engine"
    assert result["deadCodeCount"] == 0
    # The trap: 295 nodes have no reachable entry point. That count is
    # carried as engine reachability data with its definition attached —
    # never as a deletability verdict.
    assert result["unreachableFromEntryPointsPerEngine"] == 295
    joined = " ".join(result["diagnostics"])
    assert "not a deletability verdict" in joined
    assert "Dead-code report truncated at 500 entries" in joined


def test_golem_dead_code_reports_the_engines_root_verdict(golem_graph):
    result = cg.compute_dead_code(golem_graph)
    assert result["unreachableFromRootsPerEngine"] == 984
    assert result["nodesWithVerdict"] == 986
    assert result["rootsTotal"] == 186 and result["rootsInGraph"] == 0
    assert any("not a deletability claim" in d for d in result["diagnostics"])
    assert any("cannot be re-checked here" in d for d in result["diagnostics"])


def test_rusi_dead_code_refuses_to_derive(rusi_graph):
    result = cg.compute_dead_code(rusi_graph)
    assert not result["computed"]
    assert "not dead code" in result["reason"]


# --- cycles -------------------------------------------------------------------


def test_dosai_cycles_are_the_engines_clusters(dosai_graph):
    result = cg.compute_cycles(dosai_graph)
    assert result["source"] == "engine"
    assert result["recursiveClusterCount"] == 1
    assert result["nodesInRecursiveCycle"] == 1
    assert result["clusters"][0]["members"] == [
        "Microsoft.eShopWeb.Infrastructure.Data.CatalogContextSeed.SeedAsync"
        "(Microsoft.eShopWeb.Infrastructure.Data.CatalogContext,"
        "Microsoft.Extensions.Logging.ILogger,int):System.Threading.Tasks.Task"
    ]


def test_derived_cycles_on_golem_and_rusi(golem_graph, rusi_graph):
    golem_result = cg.compute_cycles(golem_graph)
    assert golem_result["source"] == "derived"
    assert golem_result["recursiveClusterCount"] == 10
    assert golem_result["clusterCount"] == 956
    assert max(len(c["members"]) for c in golem_result["clusters"]) == 28
    rusi_result = cg.compute_cycles(rusi_graph)
    assert rusi_result["recursiveClusterCount"] == 6
    assert rusi_result["clusterCount"] == 709


# --- atom: graphml loader and the algorithms join ------------------------------


def test_atom_graphml_loader(atom_graph):
    """219 METHOD nodes (121 internal, 98 external) with 533 call sites
    aggregated into 417 caller→callee edges; dispatch types come from the
    CPG's DISPATCH_TYPE."""
    assert len(atom_graph.nodes) == 219
    assert len(atom_graph.internal_ids) == 121 and len(atom_graph.external_ids) == 98
    assert len(atom_graph.edges) == 417
    assert sum(e.call_site_count for e in atom_graph.edges) == 533
    assert atom_graph.call_type_mix() == {
        "DYNAMIC_DISPATCH": 173,
        "STATIC_DISPATCH": 244,
    }


def test_atom_algorithms_centrality_joins_verbatim(atom_graph):
    with open(ATOM_CENTRALITY, encoding="utf-8") as f:
        algorithms = {"centrality": json.load(f)}
    result = cg.compute_centrality(atom_graph, algorithms=algorithms)
    assert result["atomAlgorithmsJoined"] == 121
    # atom's own pageRank/inDegree values, next to ours, unmodified
    engine_ranking = {entry["method"]: entry for entry in algorithms["centrality"]["ranking"]}
    for row in result["ranked"]:
        engine_row = engine_ranking[row["id"]]
        assert row["atomPageRank"] == engine_row["pageRank"]
        assert row["atomInDegree"] == engine_row["inDegree"]
    top = engine_ranking["<operator>.assignment"]  # external: excluded by default
    assert top not in result["ranked"]


def test_atom_algorithms_scc_is_used_verbatim(atom_graph):
    with open(ATOM_SCC, encoding="utf-8") as f:
        algorithms = {"scc": json.load(f)}
    result = cg.compute_cycles(atom_graph, algorithms=algorithms)
    assert result["source"] == "engine"
    assert result["clusterCount"] == 219
    assert result["recursiveClusterCount"] == 0  # petclinic: no recursion
    assert result["clusters"] == []


# --- GraphML / GEXF export -----------------------------------------------------


def test_export_graphml_matches_dosai_key_vocabulary(dosai_graph):
    document = cg.export_graphml([dosai_graph])
    root = ET.fromstring(document)
    namespace = {"g": "http://graphml.graphdrawing.org/xmlns"}
    keys = {k.get("id"): k.get("attr.name") for k in root.findall("g:key", namespace)}
    for dosai_key in (
        "label",
        "kind",
        "file",
        "purl",
        "external",
        "reachableEntryPoints",
        "minDepthFromEntryPoint",
        "fanIn",
        "fanOut",
        "inRecursiveCycle",
        "callType",
        "sourcePurl",
        "targetPurl",
        "location",
        "callSiteCount",
        "dispatchConfidence",
    ):
        assert keys.get(dosai_key) == dosai_key
    graph = root.find("g:graph", namespace)
    nodes = graph.findall("g:node", namespace)
    edges = graph.findall("g:edge", namespace)
    assert len(nodes) == 315 and len(edges) == 300
    # engine fanIn values ride along verbatim
    fan_ins = [
        d.text for n in nodes for d in n.findall("g:data", namespace) if d.get("key") == "fanIn"
    ]
    assert sum(int(v) for v in fan_ins) == 448
    # edge ids are e1..eN in dosai's sort order
    assert edges[0].get("id") == "e1" and edges[-1].get("id") == "e300"


def test_export_gexf_is_valid_and_carries_the_same_vocabulary(dosai_graph):
    root = ET.fromstring(cg.export_gexf([dosai_graph]))
    namespace = {"g": "http://www.gexf.net/1.3"}
    attributes = {
        a.get("id") for a in root.findall(".//g:attributes[@class='node']/g:attribute", namespace)
    }
    assert {"fanIn", "fanOut", "external", "minDepthFromEntryPoint"} <= attributes
    assert len(root.findall(".//g:nodes/g:node", namespace)) == 315
    assert len(root.findall(".//g:edges/g:edge", namespace)) == 300


def test_derived_depth_is_never_written_as_the_engines():
    """Our own numbers go under distinct keys in the exports: a depth we
    derived must never appear as minDepthFromEntryPoint."""
    nodes = [
        cg.CallNode(id="main", name="main"),
        cg.CallNode(id="helper", name="helper", min_depth_from_entry=1, depth_source="derived"),
    ]
    graph = cg.UnifiedCallGraph(
        engine="synthetic",
        source_file="s",
        nodes=nodes,
        edges=[cg.CallEdge(caller="main", callee="helper")],
    )
    document = cg.export_graphml([graph])
    assert 'key="derivedEntryDepth">1<' in document
    assert 'key="minDepthFromEntryPoint"' not in document


# --- the document and the console ----------------------------------------------


def test_document_reports_trim_and_confidence_diagnostics(golem_graph):
    document = cg.compute_graph_document([golem_graph], "chokepoints", min_confidence="exact")
    joined = " ".join(document["diagnostics"])
    assert "subgraph of the engine's run (3325 of 22308 edges" in joined
    assert "kept 3325 of 3325 edges" in joined
    assert document["graphs"][0]["confidenceMix"] == {"exact": 3325}
    assert document["options"]["maxChokepointSources"] == 64


def test_metric_validation():
    with pytest.raises(ValueError, match="Unknown metric"):
        cg.compute_graph_document([], "betweenness")
    with pytest.raises(ValueError, match="--blast-radius NODE"):
        cg.compute_graph_document([], "blast-radius")


# --- CLI ------------------------------------------------------------------------


def run_graph(args):
    app = Application()
    tester = CommandTester(app.find("graph"))
    tester.execute(args)
    return tester.io.fetch_output()


def test_command_chokepoints_console_through_cleo_io():
    output = run_graph(f"-i {GOLEM} --top 5")
    assert "chokepoints" in output
    assert "13 source(s) → 27 sink(s)" in output
    assert "flow-sources→flow-sinks" in output
    assert "betweenness 2.0" in output


def test_command_min_confidence_reports_the_reduction():
    output = run_graph(f"-i {RUSI} --min-confidence exact --top 1")
    assert "kept 308 of 2156 edges" in output
    assert "no node lies on any source→sink path" in output


def test_command_dead_code_console_carries_the_caveat():
    output = run_graph(f"-i {DOSAI_METHODS} --metric dead-code")
    assert "engine DeadCode entries: 0" in output
    assert "not a deletability verdict" in output
    assert "truncated at 500 entries" in output


def test_command_blast_radius(tmp_path):
    output = run_graph(f"-i {GOLEM} --blast-radius '(*github.com/apex/log.Entry).Debug'")
    assert "reach (including the node): 1" in output


def test_command_json_and_mermaid_outputs(tmp_path):
    out = tmp_path / "doc"
    run_graph(f"-i {RUSI} -f json,mermaid -o {out} --metric centrality --top 3")
    with open(out, encoding="utf-8") as f:  # json goes to -o exactly, like attack-surface
        document = json.load(f)
    assert document["metric"] == "centrality"
    assert document["graphs"][0]["nodes"] == 712
    assert len(document["results"][0]["ranked"]) == 371
    with open(f"{out}.mmd", encoding="utf-8") as f:
        diagram = f.read()
    assert diagram.startswith("flowchart LR")
    assert "n1(" in diagram  # ranked nodes are drawn


def test_command_export_writes_graphml_and_gexf(tmp_path):
    out = tmp_path / "graph"
    run_graph(f"-i {DOSAI_METHODS} --export graphml,gexf -o {out} --top 1")
    ET.parse(f"{out}.graphml")
    ET.parse(f"{out}.gexf")
    with open(f"{out}.graphml", encoding="utf-8") as f:
        assert 'attr.name="fanIn"' in f.read()


def test_command_export_honours_explicit_extension(tmp_path):
    out = tmp_path / "callgraph.gexf"
    run_graph(f"-i {RUSI} --export gexf -o {out} --top 1")
    assert out.exists() and not Path(f"{out}.gexf").exists()


def test_command_rejects_flow_only_dosai_input():
    with pytest.raises(ValueError, match="methods report"):
        run_graph(f"-i {DOSAI_DATAFLOWS}")


def test_command_rejects_reachables_input():
    with pytest.raises(ValueError, match="Could not read a call graph"):
        run_graph("-i test/data/java-petclinic-reachables.json")


def test_command_rejects_algorithms_on_non_atom_input():
    with pytest.raises(ValueError, match="only an atom graphml input carries"):
        run_graph(f"-i {RUSI} --algorithms {ATOM_CENTRALITY}")


def test_command_atom_centrality_with_algorithms():
    output = run_graph(f"-i {ATOM_CPG} --metric centrality --algorithms {ATOM_CENTRALITY} --top 3")
    assert "joined verbatim for 121 node(s)" in output
    assert "atom pageRank" in output


# --- golden files ---------------------------------------------------------------


GOLDEN = Path("test/data/golden/graph")
# The default metric (chokepoints) per engine, plus the dead-code pair that
# demonstrates the root-set verdict (see PROVENANCE.md).
#
# The input is pinned as a POSIX string on purpose: the console header and
# the JSON sourceFile fields echo it verbatim, and on Windows str(Path(...))
# spells it with backslashes, which would mismatch every golden below. A
# real Windows user still sees their native separators; only the test
# invocation normalises. Fix chosen over normalising inside _assert_golden
# because the latter cannot know which backslashes came from the platform
# and which from the data.
GOLDEN_INPUTS = {
    "golem": (GOLEM.as_posix(), ""),
    "dosai": (DOSAI_METHODS.as_posix(), ""),
    "rusi": (RUSI.as_posix(), ""),
    "kosi": ((ECOSYSTEM / "kotlin-dsl-media-auth-kosi.json").as_posix(), ""),
    "atom": (ATOM_CPG.as_posix(), ""),
    "golem-dead-code": (GOLEM.as_posix(), "dead-code"),
    "golem-roots-dead-code": ((ECOSYSTEM / "go-ipsw-golem-roots.json").as_posix(), "dead-code"),
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


def _document(source, metric):
    """The command's default wiring: call graph + flow source/sink join
    (graphml inputs carry no flow model, exactly as in the command)."""
    if str(source).endswith((".graphml", ".graph-ml")):
        return cg.compute_graph_document([cg.load_call_graph(source)], metric or "chokepoints")
    content = load_json(source)
    graph = cg.load_call_graph(source, content)
    report = parse_report(content, source_file=source)
    sources, sinks = cg.flow_functions(report)
    return cg.compute_graph_document(
        [graph],
        metric or "chokepoints",
        flow_sources=sources,
        flow_sinks=sinks,
        endpoints_by_source={source: report.endpoints},
    )


def _bounded_for_golden(document):
    """rusi's engine diagnostics run to thousands of strings and every metric
    ranks more nodes than a reviewer reads; keep prefixes and record the rest
    as a count — applied identically when regenerating and comparing."""
    bounded = copy.deepcopy(document)
    for graph in bounded.get("graphs", []):
        diags = graph.get("engineDiagnostics") or []
        if len(diags) > 10:
            graph["engineDiagnostics"] = diags[:10] + [
                f"... {len(diags) - 10} more not pinned ..."
            ]
    for result in bounded.get("results", []):
        ranked = result.get("ranked") or []
        if len(ranked) > 10:
            result["ranked"] = ranked[:10] + [f"... {len(ranked) - 10} more not pinned ..."]
    return bounded


@pytest.mark.parametrize("name", GOLDEN_INPUTS)
def test_golden_console_per_fixture(name):
    """What the command prints per engine, default options.

    Regenerate with: ATOM_TOOLS_REGEN_GOLDEN=1 pytest test/test_graph.py
    """
    source, metric = GOLDEN_INPUTS[name]
    document = _document(source, metric)
    text = "\n".join(cg.render_console(document)) + "\n"
    _assert_golden(f"{name}.console.txt", text)


@pytest.mark.parametrize("name", GOLDEN_INPUTS)
def test_golden_json_per_fixture(name):
    """The json document exactly as ``-f json`` writes it (indent 4, sorted
    keys, plus a trailing newline), ranked lists bounded for review."""
    source, metric = GOLDEN_INPUTS[name]
    document = _bounded_for_golden(_document(source, metric))
    _assert_golden(f"{name}.json", json.dumps(document, indent=4, sort_keys=True) + "\n")
