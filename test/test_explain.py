"""Tests for the explain command: the unified round-trip, the narrative's
honesty clauses, the query grammar, the agent document's budget, the MCP
server, and golden-file renderings per fixture.

The honesty tests are the point of the phase: every clause of the showcase
paragraph is checked against what each engine's fixture can actually support
(only dosai classifies authentication; atom records no version; no fixture
carries a populated sanitizer; fewer than half of atom's flows have source
tags), and the hedges are asserted as strings so a regression reads as a
sentence change, not a count change.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application
from atom_tools.lib.adapters import detect_engine, parse_report
from atom_tools.lib.attack_surface import SurfaceInput, is_usages_slice
from atom_tools.lib.explain import (
    SANITIZER_CAPABLE_ENGINES,
    build_agent_document,
    build_context,
    explain_flow_lines,
    find_flow,
    flows_for_file,
    flows_for_package,
    render_markdown,
    render_text,
)
from atom_tools.lib.query import parse_query, run_query

ECOSYSTEM = Path("test/data/ecosystem")
DOSAI = ECOSYSTEM / "dotnet-eshoponweb-dosai-dataflows.json"
GOLEM = ECOSYSTEM / "go-ipsw-golem.json"
RUSI = ECOSYSTEM / "rust-microservices-kafka-rusi.json"
RUSI_BASELINE = ECOSYSTEM / "rust-microservices-kafka-rusi-baseline.json"
KOSI = ECOSYSTEM / "kotlin-command-exec-kosi.json"
ATOM = Path("test/data/java-petclinic-reachables.json")
GOLDEN = Path("test/data/golden/explain")

FIXTURES = {"dosai": DOSAI, "golem": GOLEM, "rusi": RUSI, "kosi": KOSI, "atom": ATOM}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def context_for(*paths):
    inputs = []
    for path in paths:
        raw = load(path)
        report = None if is_usages_slice(raw) else parse_report(raw, source_file=str(path))
        inputs.append(SurfaceInput(report=report, raw=raw, path=str(path)))
    return build_context(inputs)


# --- the unified round-trip --------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_unified_document_round_trips_exactly(name):
    """parse_report → to_dict → parse_report reproduces the model (all engines)."""
    report = parse_report(load(FIXTURES[name]), source_file=str(FIXTURES[name]))
    document = report.to_dict()
    assert detect_engine(document) == "unified"
    back = parse_report(document, source_file=str(FIXTURES[name]))
    assert back == report


def test_merged_unified_document_round_trips():
    reports = [parse_report(load(p), source_file=str(p)) for p in (GOLEM, RUSI)]
    from atom_tools.lib.unified import merge_reports

    merged = merge_reports(reports)
    back = parse_report(merged.to_dict(), source_file=merged.source_file)
    assert back == merged
    assert back.engine == "golem+rusi"
    assert len(back.flows) == 402


@pytest.mark.parametrize(
    ("command", "args"),
    (
        ("stats", "-i {input}"),
        ("filter", "-i {input}"),
        ("attack-surface", "-i {input} -f json -o {out}"),
        ("drift", "--old {input} --new {input} -f json -o {out}"),
    ),
)
def test_report_commands_accept_a_unified_document(command, args, tmp_path):
    """The round-trip fix is in unified.py, so every report-taking command benefits."""
    report = parse_report(load(RUSI), source_file=str(RUSI))
    unified = tmp_path / "unified.json"
    unified.write_text(json.dumps(report.to_dict()))
    app = Application()
    tester = CommandTester(app.find(command))
    tester.execute(args.format(input=unified, out=tmp_path / "out.json"))
    assert tester.status_code == 0


@pytest.mark.parametrize(
    ("fixture", "key", "count"),
    ((GOLEM, "apiEndpoints", 57), (RUSI, "api_endpoints", 14)),
)
def test_reachables_emission_keeps_endpoints_through_a_unified_hop(fixture, key, count, tmp_path):
    """`--emit reachables` from unified.json must not drop the endpoint table.

    `to_reachables_document` copied the endpoint array out of the *vendor*
    document, which is absent once the input is a unified one -- so making
    unified documents readable quietly introduced a data loss: golem's 57
    endpoints vanished on the way back out, and go_converter/rust_converter
    read exactly these keys. The model carries each endpoint's verbatim vendor
    entry, so the rebuilt array must equal the directly emitted one.
    """
    from atom_tools.lib.unified import to_reachables_document

    raw = load(fixture)
    report = parse_report(raw, source_file=str(fixture))
    direct = to_reachables_document(report, original=raw)
    unified = json.loads(json.dumps(report.to_dict()))
    rebuilt = to_reachables_document(parse_report(unified, source_file="unified.json"), original=unified)
    assert len(direct[key]) == count
    assert rebuilt[key] == direct[key]


# --- the showcase clauses, per engine ----------------------------------------


def test_joined_flow_says_exposure_unknown_for_non_dosai_engines():
    """golem/rusi/atom never get "anonymous" — only dosai classifies auth."""
    ctx = context_for(GOLEM)
    joined = [f for f in ctx.report.flows if f.id in ctx.flow_entry_points]
    assert joined, "the golem fixture anchors some flows"
    block = "\n".join(explain_flow_lines(joined[0], ctx))
    assert "does not classify authentication, so the route's exposure is unknown" in block
    assert "anonymous" not in block.replace("unknown-auth", "")


def test_kosi_undeclared_route_says_the_engine_recorded_no_requirement():
    """kosi classifies its endpoints, so the generic "does not classify"
    sentence would be false about it. The unknown-auth wording is per-route:
    no requirement was declared at a site kosi models — never "open", never
    "anonymous"."""
    ctx = context_for(KOSI)
    joined = [f for f in ctx.report.flows if f.id in ctx.flow_entry_points]
    assert [f.id for f in joined] == ["slice-000001"]
    block = "\n".join(explain_flow_lines(joined[0], ctx))
    assert "kosi records no authentication requirement for this route" in block
    assert "anonymous" not in block.replace("unknown-auth", "")
    # The second slice is not endpoint-rooted: the unjoined flow says so
    # instead of dropping the clause.
    unjoined = "\n".join(explain_flow_lines(ctx.report.flows[1], ctx))
    assert "no entry-point link" in unjoined
    assert "anonymous" not in unjoined.replace("unknown-auth", "")


def test_dosai_flow_names_no_route_and_never_claims_anonymity():
    ctx = context_for(DOSAI)
    block = "\n".join(explain_flow_lines(ctx.report.flows[0], ctx))
    assert "dosai links weaknesses — not flows — to entry points" in block
    assert "anonymous" not in block


def test_atom_version_is_stated_as_absent_not_invented():
    ctx = context_for(ATOM)
    block = "\n".join(explain_flow_lines(ctx.report.flows[0], ctx))
    assert "atom (no version recorded in the slice)" in block
    ctx = context_for(GOLEM)
    block = "\n".join(explain_flow_lines(ctx.report.flows[0], ctx))
    assert "golem 3.2.0, all mode" in block


def test_severity_provenance_is_stated_per_flow():
    golem_ctx = context_for(GOLEM)
    golem = "\n".join(explain_flow_lines(golem_ctx.report.flows[0], golem_ctx))
    assert "Severity `warning` (engine-reported)" in golem
    atom_ctx = context_for(ATOM)
    flow = next(f for f in atom_ctx.report.flows if f.severity == "warning")
    block = "\n".join(explain_flow_lines(flow, atom_ctx))
    assert "Severity `warning` (derived from the shared taxonomy, not engine-reported)" in block


def test_sanitizer_sentence_is_reported_absence_not_a_finding():
    """dosai/golem get the hedged sentence; rusi/atom get no sentence at all."""
    for path in (DOSAI, GOLEM):
        ctx = context_for(path)
        block = "\n".join(explain_flow_lines(ctx.report.flows[0], ctx))
        assert "Sanitizer: No sanitizer reported on this path" in block
        assert "this run found none to report" in block
    for path in (RUSI, ATOM):
        ctx = context_for(path)
        block = "\n".join(explain_flow_lines(ctx.report.flows[0], ctx))
        assert "Sanitizer" not in block
        assert "sanitizer" not in block.lower()


def test_sanitized_flow_is_reported_as_such():
    """When a sanitizer-capable engine does report a sanitizer, the sentence says so."""
    ctx = context_for(DOSAI)
    flow = ctx.report.flows[0]
    assert flow.engine in SANITIZER_CAPABLE_ENGINES and not flow.sanitized
    flow.sanitized = True
    block = "\n".join(explain_flow_lines(flow, ctx))
    assert "reported this flow as sanitized (a sanitizer suppressed it)" in block


def test_untagged_source_omits_the_tag_clause_and_overview_counts_the_gap():
    """85 of 163 atom flows carry no source tags; the clause is omitted, the
    overview states the coverage instead of hiding it."""
    ctx = context_for(ATOM)
    untagged = next(f for f in ctx.report.flows if f.source is not None and not f.source.tags)
    block = "\n".join(explain_flow_lines(untagged, ctx))
    path_line = next(line for line in block.splitlines() if line.startswith("  Path:"))
    assert " tagged `" not in path_line
    overview = "\n".join(render_text(ctx, max_flows=0).splitlines()[:6])
    assert "source tags: 78 of 163 flow(s) carry tags on the source node" in overview


def test_unclassified_sink_is_stated_not_defaulted():
    ctx = context_for(ATOM)
    flow = next(f for f in ctx.report.flows if not f.sink_category)
    block = "\n".join(explain_flow_lines(flow, ctx))
    assert "with no sink category recorded in this slice" in block


def test_truncated_witness_is_flagged_on_the_path_clause():
    ctx = context_for(RUSI)
    flow = ctx.report.flows[0]
    flow.path_truncated = True
    block = "\n".join(explain_flow_lines(flow, ctx))
    assert "the witness path is a representative excerpt, not every step (path_truncated)" in block


def test_unified_input_hedges_the_endpoint_join():
    """From a unified document there is no call graph, so the clause says so."""
    report = parse_report(load(GOLEM), source_file="golem.json")
    unified = report.to_dict()
    inputs = [
        SurfaceInput(report=parse_report(unified, source_file="unified.json"), raw=unified, path="unified.json")
    ]
    ctx = build_context(inputs)
    assert ctx.unified_engines == ["golem"]
    assert not ctx.flow_entry_points
    block = "\n".join(explain_flow_lines(ctx.report.flows[0], ctx))
    assert "the input is a unified document, which carries no call graph" in block


def test_join_numbers_match_the_measured_fixtures():
    """The one join is attack_surface's; its real coverage shows up verbatim."""
    golem = context_for(GOLEM)
    assert len(golem.flow_entry_points) == 136  # unique flows behind 179 attachments
    rusi = context_for(RUSI)
    assert len(rusi.flow_entry_points) == 1
    atom = context_for(ATOM)
    assert len(atom.flow_entry_points) == 2
    assert "31 of 57 endpoint(s) anchored" in "\n".join(render_text(golem, max_flows=0).splitlines()[:8])


# --- selection ----------------------------------------------------------------


def test_find_flow_unknown_id_lists_a_hint():
    ctx = context_for(RUSI)
    with pytest.raises(ValueError, match="Did you mean"):
        find_flow(ctx.report, "df-slice-03a64c7753789d6X")


def test_flows_for_package_and_file():
    ctx = context_for(ATOM)
    spring = flows_for_package(ctx.report, "spring-web")
    assert spring and all("spring-web" in p.lower() for f in spring for p in f.purls)
    owner = flows_for_file(ctx.report, "owner/OwnerController.java")
    assert owner and all(any("OwnerController.java" in n.file for n in f.nodes) for f in owner)


# --- the query grammar (dosai port) -------------------------------------------


def items(ctx=None):
    ctx = ctx or context_for(RUSI)
    return ctx.collections()


def test_operator_match_order_parses_greater_equal_first():
    parsed = parse_query("flows[source.line>=10]", ["flows"])
    term = parsed.groups[0][0]
    assert (term.property, term.op, term.value) == ("source.line", ">=", "10")
    parsed = parse_query("flows[steps>2]", ["flows"])
    assert parsed.groups[0][0].op == ">"


def test_contains_operator_is_case_insensitive():
    result = run_query(items(), "flows[source_category~=PARAM]")
    assert result["count"] == 5


def test_equality_is_case_insensitive_and_numeric_where_possible():
    assert run_query(items(), "flows[severity=WARNING]")["count"] == 5
    assert run_query(items(), "flows[steps=2]")["count"] == 5
    assert run_query(items(), "flows[steps>=3]")["count"] == 0
    assert run_query(items(), "flows[steps>1.5]")["count"] == 5


def test_conjuncts_and_and_or():
    assert run_query(items(), "flows[severity=error && steps=2]")["count"] == 0
    assert run_query(items(), "flows[severity=error || severity=warning]")["count"] == 5
    assert run_query(items(), "flows[severity=error || severity=warning && steps=2]")["count"] == 5


def test_bare_term_defaults_to_true():
    # A term with no operator compares against "true"; sanitized is a bool.
    assert run_query(items(), "flows[sanitized=false]")["count"] == 5
    assert run_query(items(), "flows[sanitized]")["count"] == 0


def test_dotted_and_list_properties():
    assert run_query(items(), "flows[source.tags~=param]")["count"] == 5
    assert run_query(items(), "flows[purls~=common-security]")["count"] > 0


def test_sort_by_and_count_postfixes():
    ctx = context_for(RUSI)
    ascending = run_query(ctx.collections(), "flows sort by id")
    ids = [item["id"] for item in ascending["items"]]
    assert ids == sorted(ids)
    top = run_query(ctx.collections(), "flows sort by steps desc")
    assert top["items"][0]["steps"] >= top["items"][-1]["steps"]
    assert run_query(ctx.collections(), "flows count")["count"] == 5
    assert run_query(ctx.collections(), "flows count")["items"] == []


def test_missing_sort_property_sorts_last_in_both_directions():
    ctx = context_for(RUSI)
    up = run_query(ctx.collections(), "endpoints sort by kind")
    down = run_query(ctx.collections(), "endpoints sort by kind desc")
    present = [e for e in up["items"] if e.get("kind")]
    absent = [e for e in up["items"] if not e.get("kind")]
    assert up["items"][: len(present)] == present
    assert absent == [e for e in down["items"] if not e.get("kind")]


def test_quoted_values_and_unknown_collection():
    assert run_query(items(), "flows[sink_category='network-request']")["count"] == 5
    with pytest.raises(ValueError, match="Unknown collection"):
        parse_query("slices[severity=error]", ["flows"])
    with pytest.raises(ValueError, match="not accepted"):
        parse_query("report.slices[severity=error]", ["flows"])


# --- the agent document -------------------------------------------------------


def test_agent_document_is_json_and_round_trips(tmp_path):
    document = build_agent_document(context_for(RUSI))
    text = json.dumps(document, indent=2, sort_keys=True)
    assert json.loads(text) == document
    assert document["schema"] == "atom-tools/explain-agent-context@1"
    assert document["tokenBudget"]["respected"] is True
    assert "truncation" not in document  # the small report fits whole


def test_agent_document_respects_the_budget_with_an_unmissable_marker():
    document = build_agent_document(context_for(GOLEM), max_tokens=2000)
    assert document["tokenBudget"]["respected"] is True
    assert document["tokenBudget"]["estimatedTokens"] <= 2000
    marker = document["truncation"]["marker"]
    assert marker.startswith("truncated: ")
    assert "more item(s) not shown" in marker
    assert document["truncation"]["omitted"]["highRiskFlows"] > 300


@pytest.mark.parametrize("fixture", [GOLEM, DOSAI, ATOM, RUSI])
@pytest.mark.parametrize("budget", [4000, 2000, 500])
def test_agent_document_measures_itself_including_its_own_budget_block(fixture, budget):
    """`estimatedTokens` must describe the document that carries it.

    The blocks stating the truncation and the budget used to be appended after
    the trimming loop, so they were never counted: golem at 4000 reported 3894
    tokens and `respected: true` for a document that serialized to 3944. Only
    comparing the reported number against the real serialization catches that
    -- asserting `estimatedTokens <= budget`, as the first version of this test
    did, passes happily on a document that is over.
    """
    document = build_agent_document(context_for(fixture), max_tokens=budget)
    actual = len(json.dumps(document, indent=2, sort_keys=True)) // 4
    assert document["tokenBudget"]["estimatedTokens"] == actual
    assert document["tokenBudget"]["respected"] is (actual <= budget)
    if document["tokenBudget"]["respected"]:
        assert actual <= budget


def test_agent_document_states_its_counting_method():
    document = build_agent_document(context_for(RUSI))
    assert "characters/4" in document["tokenBudget"]["countingMethod"]
    assert "not a real tokeniser" in document["tokenBudget"]["countingMethod"]


def test_agent_flow_facts_carry_the_honesty_fields():
    ctx = context_for(ATOM)
    facts = build_agent_document(ctx, max_tokens=100000)["highRiskFlows"]
    untagged = next(f for f in facts if f["source"] is not None and not f["source"]["tags"])
    assert untagged["source"]["tags"] == []
    assert facts[0]["severitySource"] in ("engine", "derived")


# --- the listing marker -------------------------------------------------------


def test_listing_truncation_marker_is_present_when_it_bites():
    text = render_text(context_for(GOLEM), max_flows=3)
    assert "truncated: 394 more flow(s) not shown" in text
    small = render_text(context_for(RUSI), max_flows=10)
    assert "truncated" not in small


def test_ranking_is_severity_then_entry_point_tier_then_id():
    ctx = context_for(GOLEM)
    ranked = ctx.rank_flows()
    keys = [
        (
            {"error": 0, "warning": 1, "note": 2}[f.severity],
            f.id,
        )
        for f in ranked[:5]
    ]
    assert keys == sorted(keys)
    severities = [{"error": 0, "warning": 1, "note": 2}[f.severity] for f in ranked]
    assert severities == sorted(severities)


# --- the MCP server -----------------------------------------------------------


def _unwrap(result):
    """fastmcp's call_tool returns (blocks, data) or just blocks across 1.x."""
    if isinstance(result, tuple) and len(result) == 2:
        raw = result[1]
        return raw.get("result", raw) if isinstance(raw, dict) else raw
    return result


def _first_text(result) -> str:
    blocks = result[0] if isinstance(result, tuple) else result
    return blocks[0].text


def test_mcp_server_lists_and_calls_tools_without_filesystem_access(monkeypatch):
    pytest.importorskip(
        "mcp.server.fastmcp", reason="the mcp extra is not installed in this environment"
    )
    from atom_tools.lib.explain import build_mcp_server

    ctx = context_for(RUSI)
    baseline = parse_report(load(RUSI_BASELINE), source_file=str(RUSI_BASELINE))
    # golem's 397 flows are what exercises atom.query's 50-item cap; rusi's 5
    # do not. Built before the filesystem is closed off, like the rusi pair.
    golem_server = build_mcp_server(context_for(GOLEM), None)
    server = build_mcp_server(ctx, baseline)
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == [
        "atom.attack_surface",
        "atom.drift",
        "atom.explain_flow",
        "atom.graph_hotspots",
        "atom.query",
    ]

    def no_open(*args, **kwargs):
        raise AssertionError("a tool call touched the filesystem")

    monkeypatch.setattr("builtins.open", no_open)
    narrative = asyncio.run(server.call_tool("atom.explain_flow", {"flow_id": ctx.report.flows[0].id}))
    assert "Reachability" in _first_text(narrative)
    drift = _unwrap(asyncio.run(server.call_tool("atom.drift", {})))
    assert len(drift["MovedFlows"]) == 2  # the documented pair result
    hotspots = _unwrap(asyncio.run(server.call_tool("atom.graph_hotspots", {})))
    assert hotspots["results"][0]["computed"] is True
    # Every exposed tool gets called, not just listed: the surface the server
    # was built with, and both sides of atom.query's cap.
    surface = _unwrap(asyncio.run(server.call_tool("atom.attack_surface", {})))
    assert sum(len(t.get("EntryPoints") or []) for t in surface["tiers"]) == 14
    small = _unwrap(asyncio.run(server.call_tool("atom.query", {"expression": "flows"})))
    assert small["count"] == 5 and "truncated" not in small
    big = _unwrap(asyncio.run(golem_server.call_tool("atom.query", {"expression": "flows"})))
    assert len(big["items"]) == 50
    assert big["truncated"] == {
        "marker": "truncated: 347 more item(s) not shown",
        "total": 397,
    }


def test_mcp_drift_without_baseline_raises(monkeypatch):
    pytest.importorskip("mcp.server.fastmcp")
    from atom_tools.lib.explain import build_mcp_server

    server = build_mcp_server(context_for(RUSI), None)
    with pytest.raises(Exception, match="baseline"):
        asyncio.run(server.call_tool("atom.drift", {}))


def test_cli_and_renderers_load_without_the_mcp_package():
    """The extra stays optional: importing every renderer must not pull mcp in."""
    import subprocess

    code = (
        "import sys;"
        "from atom_tools.cli.application import Application;"
        "app = Application(); app.find('explain');"
        "import atom_tools.lib.explain;"
        "assert 'mcp' not in sys.modules, 'mcp leaked into the core imports';"
        "print('clean')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "clean"


# --- golden files -------------------------------------------------------------


def _golden(name, format_name, extension):
    return GOLDEN / f"{name}{format_name}{extension}"


@pytest.mark.parametrize(
    ("name", "format_name", "extension", "render"),
    [
        ("dosai", ".text", ".txt", lambda ctx: render_text(ctx, max_flows=3)),
        ("golem", ".text", ".txt", lambda ctx: render_text(ctx, max_flows=3)),
        ("rusi", ".text", ".txt", lambda ctx: render_text(ctx, max_flows=3)),
        ("kosi", ".text", ".txt", lambda ctx: render_text(ctx, max_flows=3)),
        ("atom", ".text", ".txt", lambda ctx: render_text(ctx, max_flows=3)),
        ("dosai", ".markdown", ".md", lambda ctx: render_markdown(ctx, max_flows=3)),
        ("golem", ".markdown", ".md", lambda ctx: render_markdown(ctx, max_flows=3)),
        ("rusi", ".markdown", ".md", lambda ctx: render_markdown(ctx, max_flows=3)),
        ("kosi", ".markdown", ".md", lambda ctx: render_markdown(ctx, max_flows=3)),
        ("atom", ".markdown", ".md", lambda ctx: render_markdown(ctx, max_flows=3)),
        (
            "dosai",
            ".agent",
            ".json",
            lambda ctx: json.dumps(build_agent_document(ctx), indent=2, sort_keys=True) + "\n",
        ),
        (
            "golem",
            ".agent",
            ".json",
            lambda ctx: json.dumps(build_agent_document(ctx), indent=2, sort_keys=True) + "\n",
        ),
        (
            "rusi",
            ".agent",
            ".json",
            lambda ctx: json.dumps(build_agent_document(ctx), indent=2, sort_keys=True) + "\n",
        ),
        (
            "kosi",
            ".agent",
            ".json",
            lambda ctx: json.dumps(build_agent_document(ctx), indent=2, sort_keys=True) + "\n",
        ),
        (
            "atom",
            ".agent",
            ".json",
            lambda ctx: json.dumps(build_agent_document(ctx), indent=2, sort_keys=True) + "\n",
        ),
    ],
)
def test_golden_rendering_per_fixture(name, format_name, extension, render):
    """Deterministic output is testable; that is the point of the command.

    Regenerate with: ATOM_TOOLS_REGEN_GOLDEN=1 pytest test/test_explain.py
    """
    text = render(context_for(FIXTURES[name]))
    golden = _golden(name, format_name, extension)
    if os.environ.get("ATOM_TOOLS_REGEN_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(text)
    assert golden.exists(), f"missing golden file {golden}; regenerate with ATOM_TOOLS_REGEN_GOLDEN=1"
    assert golden.read_text() == text


# --- CLI wiring ---------------------------------------------------------------


def run_explain(args):
    app = Application()
    tester = CommandTester(app.find("explain"))
    tester.execute(args)
    return tester


def test_cli_flow_selector_through_cleo_io():
    """Output goes through cleo's io (self.line), never bare print()."""
    tester = run_explain(f"-i {ATOM} --flow atom-flow-74")
    assert tester.status_code == 0
    io = tester.io.fetch_output()
    assert "Flow atom-flow-74" in io
    assert "exposure is unknown" in io


def test_cli_agent_format_writes_parseable_json(tmp_path):
    out = tmp_path / "context.json"
    tester = run_explain(f"-i {RUSI} -f agent -o {out}")
    assert tester.status_code == 0
    document = json.loads(out.read_text())
    assert document["tokenBudget"]["respected"] is True
    assert "Explanation written to" in tester.io.fetch_output()


def test_cli_rejects_multiple_selectors_and_agent_with_selector():
    with pytest.raises(ValueError, match="at most one"):
        run_explain(f"-i {RUSI} --flow x --package y")
    with pytest.raises(ValueError, match="whole report"):
        run_explain(f"-i {RUSI} -f agent --flow x")


def test_cli_unknown_flow_fails_with_hint():
    with pytest.raises(ValueError, match="Unknown flow id"):
        run_explain(f"-i {RUSI} --flow nope")


def test_cli_accepts_unified_document_and_mixed_engines(tmp_path):
    report = parse_report(load(RUSI), source_file=str(RUSI))
    unified = tmp_path / "unified.json"
    unified.write_text(json.dumps(report.to_dict()))
    tester = run_explain(f"-i {unified} --flow df-slice-03a64c7753789d6d")
    assert tester.status_code == 0
    output = tester.io.fetch_output()
    assert "unified document, which carries no call graph" in output
    tester = run_explain(f"-i '{DOSAI},{RUSI}' --max-flows 1")
    assert tester.status_code == 0
    output = tester.io.fetch_output()  # fetch_output consumes the buffer: read once
    assert "dosai 5.0.0.0" in output
    assert "rusi 3.2.0" in output
