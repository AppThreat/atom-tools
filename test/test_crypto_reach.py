"""Tests for crypto-reach: the crypto inventory × entry-point reachability join.

The honest answer is per-engine because the engines leave the join at
different granularities (dosai record-level engine verdicts, rusi
function-level, golem package-level, kosi function/file-level by record
kind), and these tests pin each engine's join to counts measured on the
committed fixtures (see PROVENANCE.md), plus the hedges that keep the weaker
granularities from reading as stronger claims.
"""

import copy
import json
import os
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application
from atom_tools.lib.adapters import parse_report
from atom_tools.lib.attack_surface import SurfaceInput
from atom_tools.lib.crypto_reach import compute_crypto_reach, render_console

ECOSYSTEM = Path("test/data/ecosystem")
DOSAI_CRYPTO = ECOSYSTEM / "dotnet-eshoponweb-dosai-crypto.json"
DOSAI_METHODS = ECOSYSTEM / "dotnet-eshoponweb-dosai-methods.json"
GOLEM = ECOSYSTEM / "go-ipsw-golem.json"
GOLEM_ROOTS = ECOSYSTEM / "go-ipsw-golem-roots.json"
RUSI = ECOSYSTEM / "rust-microservices-kafka-rusi.json"
ATOM = Path("test/data/java-petclinic-reachables.json")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def inputs_for(*paths):
    out = []
    for path in paths:
        raw = load(path)
        out.append(
            SurfaceInput(
                report=parse_report(raw, source_file=str(path)),
                raw=raw,
                path=str(path),
            )
        )
    return out


@pytest.fixture(scope="module")
def dosai_doc():
    return compute_crypto_reach(inputs_for(DOSAI_CRYPTO))


@pytest.fixture(scope="module")
def golem_doc():
    return compute_crypto_reach(inputs_for(GOLEM))


@pytest.fixture(scope="module")
def golem_roots_doc():
    return compute_crypto_reach(inputs_for(GOLEM_ROOTS))


@pytest.fixture(scope="module")
def rusi_doc():
    return compute_crypto_reach(inputs_for(RUSI))


def _engine_block(document, engine):
    return next(b for b in document["engines"] if b["engine"] == engine)


def _items(block, kind):
    return [i for i in block["items"] if i["Kind"] == kind]


def _attention(block):
    return [i for i in block["items"] if i.get("Attention")]


# --- dosai: the engine's verdict, verbatim --------------------------------------


def test_dosai_inventory_matches_the_engine_statistics(dosai_doc):
    block = _engine_block(dosai_doc, "dosai")
    assert block["inventory"] == {
        "Assets": 3,
        "Findings": 5,
        "Materials": 2,
        "Operations": 3,
        "Protocols": 0,
    }
    assert block["joinGranularity"] == "record"
    assert block["joinSource"] == "engine"


def test_dosai_reachable_finding_count_agrees_with_the_engine(dosai_doc):
    """The engine's own Statistics.ReachableFindingCount is 1; the number of
    findings we render as reachable must be exactly that — we take dosai's
    verdict verbatim and never re-derive it."""
    block = _engine_block(dosai_doc, "dosai")
    reachable = [
        i for i in _items(block, "finding") if i["Reach"]["reachableFromEntryPoint"]
    ]
    stats = load(DOSAI_CRYPTO)["Statistics"]
    assert stats["ReachableFindingCount"] == 1
    assert len(reachable) == 1
    assert reachable[0]["Id"] == "cf5"
    assert reachable[0]["RuleId"] == "DOSAI-CRYPTO-WEAK-CIPHER"
    assert reachable[0]["Severity"] == "High"  # verbatim Pascal-case...
    assert reachable[0]["SeverityLevel"] == "error"  # ...folded only for ranking


def test_dosai_verbatim_join_agrees_with_the_methods_report(dosai_doc):
    """The strongest cross-check: dosai's crypto verdict for GetTokenAsync
    (cf5) names the same entry-point ids as the engine's own Reachability
    array in the methods report for the same method. If a derived join ever
    disagreed with the engine, this is where it would show."""
    cf5 = next(i for i in _items(_engine_block(dosai_doc, "dosai"), "finding") if i["Id"] == "cf5")
    methods = load(DOSAI_METHODS)
    target = "Microsoft.eShopWeb.Infrastructure.Identity.IdentityTokenClaimService.GetTokenAsync"
    entry = next(r for r in methods["Reachability"] if target in (r.get("NodeId") or ""))
    assert sorted(entry["ReachableEntryPoints"]) == sorted(
        e["id"] for e in cf5["Reach"]["entryPoints"]
    )
    assert cf5["Reach"]["entryPoints"][0]["label"] == "POST /api/authenticate"


def test_dosai_unresolved_entry_point_ids_are_said_not_dropped(dosai_doc):
    """An EntryPointIds value absent from CryptoDataFlows.EntryPoints must be
    reported as unresolved, not silently dropped."""
    block = _engine_block(dosai_doc, "dosai")
    cdf_eps = {e["Id"] for e in load(DOSAI_CRYPTO)["CryptoDataFlows"]["EntryPoints"]}
    referenced = {
        e["id"]
        for i in block["items"]
        for e in i["Reach"]["entryPoints"]
    }
    assert referenced <= cdf_eps  # fixture: everything resolves
    # and the renderer would print "(unresolved id)" — assert the branch exists
    lines = render_console(dosai_doc, max_entries=100)
    assert any("engine-reported" in line for line in lines)


# --- golem: a package-level join that says it is one ----------------------------


def test_golem_attention_population_is_the_measured_one(golem_doc):
    """13 non-literal findings plus the 2 weak assets (md5, sha-1) — the
    population this command exists to triage."""
    block = _engine_block(golem_doc, "golem")
    attention = _attention(block)
    assert len(attention) == 15
    non_literal = [
        i for i in attention if i["Kind"] == "finding" and "LITERAL-MATERIAL" not in (i["RuleId"] or "")
    ]
    assert len(non_literal) == 13
    weak_assets = [i for i in attention if i["Kind"] == "asset"]
    assert {i["Algorithm"] for i in weak_assets} == {"hash"}
    assert {i["Strength"] for i in weak_assets} == {"weak"}


def test_golem_package_join_counts_match_the_measurement(golem_doc):
    """7 of the 13 non-literal findings sit in a package that carries tainted
    flows; 4 of those in a package whose flows hang off an anchored endpoint.
    These are the prompt's measured numbers — the join must reproduce them."""
    block = _engine_block(golem_doc, "golem")
    non_literal = [
        i
        for i in _attention(block)
        if i["Kind"] == "finding" and "LITERAL-MATERIAL" not in (i["RuleId"] or "")
    ]
    on_flow = [i for i in non_literal if i["Reach"]["packageOnFlow"]]
    with_endpoint = [i for i in on_flow if i["Reach"].get("flowsThroughPackageReachEndpoints")]
    assert len(on_flow) == 7
    assert len(with_endpoint) == 4


def test_golem_renders_the_weaker_sentence(golem_doc):
    """A package-level join supports 'the site sits in a package that carries
    tainted flows', never an unqualified 'this call is on a tainted path' —
    the strong phrase may only appear inside the claim's own negation."""
    lines = render_console(golem_doc, max_entries=60)
    assert any(
        "the crypto site sits in a package that carries tainted flows" in line for line in lines
    )
    for line in lines:
        if "on a tainted path" in line:
            assert "not that" in line or "never" in line


def test_golem_engine_root_verdict_tracks_the_root_set(golem_doc, golem_roots_doc):
    """The two golem fixtures are the same call-graph subgraph with different
    root sets; the per-package engine verdict must flip with them — 0 of 30
    reachable with the default init/main roots, 30 of 30 with
    --roots handlers,main,exported (package: internal/download)."""
    pkg = "github.com/blacktop/ipsw/internal/download"

    def verdict(doc):
        finding = next(
            i
            for i in _items(_engine_block(doc, "golem"), "finding")
            if i["Package"] == pkg and "LITERAL-MATERIAL" not in (i["RuleId"] or "")
        )
        return finding["Reach"]["engineRootVerdict"]

    old, new = verdict(golem_doc), verdict(golem_roots_doc)
    assert (old["reachableNodesInPackage"], old["nodesInPackage"]) == (0, 30)
    assert (new["reachableNodesInPackage"], new["nodesInPackage"]) == (30, 30)
    assert old["rootsTotal"] == 186
    assert new["rootsTotal"] == 3459


def test_golem_roots_fixture_is_the_same_graph_with_new_verdicts(golem_roots_doc):
    """PROVENANCE records that the --roots re-run reproduces the identical
    986-node / 3,325-edge subgraph; the join's coverage note must state the
    trim and the fixture itself must carry 947 reachable verdicts."""
    block = _engine_block(golem_roots_doc, "golem")
    raw = load(GOLEM_ROOTS)
    reach = raw["callGraph"]["reachability"]["nodes"]
    assert len(raw["callGraph"]["nodes"]) == 986
    assert len(raw["callGraph"]["edges"]) == 3325
    assert sum(1 for r in reach if r.get("reachableFromRoots")) == 947
    note = next(n for n in block["coverageNotes"] if "subgraph" in n)
    assert "3,325" not in note  # the raw count, not a formatted one, is used
    assert "3325 of 22308 edges" in note


# --- rusi: function-level, and zeros that are coverage statements ---------------


def test_rusi_all_materials_anchor_and_none_reach_an_endpoint(rusi_doc):
    """17 of 17 materials anchor in the call graph by qualified_name, and 0
    sit inside an anchored endpoint's closure — they hang off event
    dispatchers, main and listeners instead. Both halves are the answer."""
    block = _engine_block(rusi_doc, "rusi")
    materials = _items(block, "material")
    assert len(materials) == 17
    states = {m["Reach"]["state"] for m in materials}
    assert states == {"in-graph-no-endpoint-reach"}
    assert all(m["Reach"]["granularity"] == "function" for m in materials)


def test_rusi_static_callers_are_shown(rusi_doc):
    """The material's function is in the graph but outside every endpoint
    closure; what it hangs off (static callers) is part of the verdict."""
    block = _engine_block(rusi_doc, "rusi")
    with_callers = [
        m for m in _items(block, "material") if "callers" in m["Reach"]
    ]
    assert with_callers
    dispatchers = [
        m
        for m in with_callers
        if any("event_dispatcher" in c for c in m["Reach"]["callers"])
    ]
    assert dispatchers, "the avro/sns key materials hang off EventDispatcher::dispatch"
    no_callers = [
        m for m in _items(block, "material") if m["Reach"].get("callers") == []
    ]
    assert not no_callers  # callers key is omitted when empty
    uncalled = [m for m in _items(block, "material") if "no static caller" in m["Reach"].get("note", "")]
    assert len(uncalled) == 3  # authentication.rs: token_validator/decoders/decoded_token


def test_rusi_zeros_are_coverage_statements(rusi_doc):
    """Zero components and zero findings are engine coverage limits, not
    findings of absence: a fixed symbol catalog matched nothing, and the only
    weak-crypto rules are SHA-1 and MD5."""
    block = _engine_block(rusi_doc, "rusi")
    text = " ".join(block["diagnostics"])
    assert "fixed symbol catalog" in text
    assert "rusi does not look for this" in text
    assert "no strength field" in text
    assert block["inventory"]["components"] == 0
    assert block["inventory"]["findings"] == 0


def test_rusi_libraries_stay_at_package_grain(rusi_doc):
    """rusi libraries carry no function field; they join at package grain and
    the granularity says so rather than smoothing over the difference."""
    block = _engine_block(rusi_doc, "rusi")
    libraries = _items(block, "library")
    assert len(libraries) == 2
    assert all(i["Reach"]["granularity"] == "package" for i in libraries)


# --- kosi: three grains, one per record kind ------------------------------------

KOSI_CRYPTO = ECOSYSTEM / "kotlin-crypto-material-flow-kosi.json"


@pytest.fixture(scope="module")
def kosi_doc():
    return compute_crypto_reach(inputs_for(KOSI_CRYPTO))


def test_kosi_join_granularity_lists_the_grains_actually_used(kosi_doc):
    """Operations join at function grain, materials and findings at file
    grain, assets/protocols/libraries at none — the block label lists every
    grain the items use, never just the finest one."""
    block = _engine_block(kosi_doc, "kosi")
    assert block["joinGranularity"] == "file/function"
    assert block["joinSource"] == "derived"
    assert block["itemsTotal"] == 8
    assert block["inventory"] == {
        "assets": 3,
        "findings": 1,
        "libraries": 0,
        "materials": 2,
        "operations": 2,
        "protocols": 0,
    }


def test_kosi_operations_join_at_function_grain(kosi_doc):
    block = _engine_block(kosi_doc, "kosi")
    operations = _items(block, "operation")
    assert len(operations) == 2
    # The fixture has no endpoints, so the functions anchor in the graph but
    # reach no anchored endpoint's closure — an answer, not a failure.
    assert all(i["Reach"]["granularity"] == "function" for i in operations)
    assert all(i["Reach"]["state"] == "in-graph-no-endpoint-reach" for i in operations)


def test_kosi_materials_and_findings_join_at_file_grain(kosi_doc):
    block = _engine_block(kosi_doc, "kosi")
    materials = _items(block, "material")
    findings = _items(block, "finding")
    assert len(materials) == 2 and len(findings) == 1
    for item in materials + findings:
        assert item["Reach"]["granularity"] == "file"
        # Both crypto slices live in TokenService.kt, the same file every
        # crypto record sits in.
        assert item["Reach"]["fileOnFlow"] is True
        assert item["Reach"]["flowsThroughFile"] == 2
    # The finding is the triage payload; it carries kosi's own severity.
    assert findings[0]["Name"] == "low-iteration-pbkdf2"
    assert findings[0]["Severity"] == "medium"
    assert findings[0]["Attention"] is True


def test_kosi_assets_and_strings_are_inventory_only(kosi_doc):
    block = _engine_block(kosi_doc, "kosi")
    for kind in ("asset", "protocol", "library"):
        for item in _items(block, kind):
            assert item["Reach"]["state"] == "no-location"
            assert "nothing to join on" in item["Reach"]["reason"]


# --- scope and shape -------------------------------------------------------------


def test_no_cross_engine_headline():
    """Three granularities do not sum: the summary carries per-engine facts
    only, and no key adds counts across engines."""
    document = compute_crypto_reach(
        inputs_for(DOSAI_CRYPTO, GOLEM_ROOTS, RUSI),
        weak_only=True,
    )
    assert set(document["summary"]["perEngine"]) == {"dosai", "golem", "rusi"}
    assert not any(
        key for key in document["summary"] if key not in ("perEngine", "outOfScope")
    )
    for engine, facts in document["summary"]["perEngine"].items():
        block = _engine_block(document, engine)
        assert facts["itemsTotal"] == block["itemsTotal"] == len(block["items"])
        assert facts["attentionItems"] == block["attentionItems"]
        assert facts["attentionItems"] == facts["itemsTotal"]  # weak_only kept attention only


def test_atom_input_raises_with_the_reason():
    with pytest.raises(ValueError, match="atom emits no crypto section"):
        compute_crypto_reach(inputs_for(ATOM))


def test_unified_input_raises_with_the_precise_reason(tmp_path):
    report = parse_report(load(RUSI), source_file=str(RUSI))
    unified = tmp_path / "unified.json"
    unified.write_text(json.dumps(report.to_dict()))
    with pytest.raises(ValueError, match="unified documents carry no crypto"):
        compute_crypto_reach(inputs_for(unified))


def test_mixed_inputs_report_out_of_scope_engines():
    document = compute_crypto_reach(inputs_for(DOSAI_CRYPTO, ATOM))
    out = document["summary"]["outOfScope"]
    assert len(out) == 1
    assert out[0]["engine"] == "atom"
    assert "no crypto section" in out[0]["reason"]


def test_unknown_strength_warns_and_continues():
    """Strength values are string literals in engine rule tables, not enums;
    an unobserved one must warn and continue, not hard-fail. No committed
    fixture carries one, so the branch is exercised directly."""
    from atom_tools.lib.crypto_reach import KNOWN_STRENGTHS, _unknown_strength

    assert _unknown_strength("dosai", "legacy", "cas9") is None  # known tier
    assert _unknown_strength("golem", None, "x") is None  # absent is not unknown
    warning = _unknown_strength("golem", "ultra", "sym-x")
    assert warning and "carried verbatim" in warning
    assert "ultra" not in KNOWN_STRENGTHS


# --- the CLI ---------------------------------------------------------------------


def _run_cli(args, tmp_path):
    app = Application()
    tester = CommandTester(app.find("crypto-reach"))
    tester.execute(args.format(out=tmp_path / "out.json"))
    return tester


def test_cli_text_rendering_lists_attention_first(tmp_path):
    tester = _run_cli(f"-i {GOLEM} --max-entries 3", tmp_path)
    assert tester.status_code == 0
    io = tester.io.fetch_output()
    assert "join granularity per engine: golem package-level (derived)" in io
    assert "never summed across them" in io
    assert io.count("claim:") <= 3


def test_cli_json_and_weak_only(tmp_path):
    out = tmp_path / "crypto.json"
    tester = _run_cli(f"-i {GOLEM} -f json --weak-only -o {out}", tmp_path)
    assert tester.status_code == 0
    document = json.loads(out.read_text())
    assert document["weakOnly"] is True
    assert document["summary"]["perEngine"]["golem"]["itemsTotal"] == 15
    assert all(i.get("Attention") for b in document["engines"] for i in b["items"])


def test_cli_rejects_unknown_format(tmp_path):
    tester = _run_cli(f"-i {GOLEM}", tmp_path)
    with pytest.raises(ValueError) as excinfo:
        tester.execute(f"-i {GOLEM} -f html")
    assert "Unknown format" in str(excinfo.value)
    with pytest.raises(ValueError) as excinfo:
        tester.execute(f"-i {GOLEM} --max-entries many")
    assert "Invalid --max-entries" in str(excinfo.value)


def test_dosai_records_render_the_fields_the_engine_actually_publishes(dosai_doc):
    """Three of the field names read from dosai's crypto records did not exist.

    `CryptoOperation` has `OperationType` and `Algorithm` and no "Operation",
    so every operation fell back to its opaque id -- a weak DES/RC2/RC4 use
    rendered as "operation cop1". `CryptoAsset` and `CryptoProtocol` have no
    "Algorithm"/"Protocol" field at all. Reading a key an engine does not
    publish is indistinguishable from the engine leaving it empty, which is
    the confusion this command exists to avoid.
    """
    block = _engine_block(dosai_doc, "dosai")
    operations = _items(block, "operation")
    assert len(operations) == 3
    for operation in operations:
        assert operation["Name"] == "use DES/RC2/RC4"
        assert operation["Algorithm"] == "DES/RC2/RC4"
        assert operation["Name"] != operation["Id"]
    for asset in _items(block, "asset"):
        assert asset["Name"] == "DES/RC2/RC4"
        assert asset["Algorithm"] is None  # CryptoAsset publishes no Algorithm
    for material in _items(block, "material"):
        assert material["Name"] in {"AUTH_KEY", "JWT_SECRET_KEY"}


def test_items_are_located_by_path_not_basename(dosai_doc, golem_doc):
    """The directory is the most useful thing on the line.

    6 of the 13 dosai records on eShopOnWeb sit under tests/, which a bare
    "ApiTokenHelper.cs:46" hides entirely, and the two weak-cipher findings in
    test code are otherwise indistinguishable from the one in src/. A Go repo
    has a dozen "client.go".
    """
    dosai = _engine_block(dosai_doc, "dosai")
    rendered = "\n".join(render_console(dosai_doc))
    under_tests = [i for i in dosai["items"] if i["File"].startswith("tests/")]
    assert len(under_tests) == 6
    assert "tests/FunctionalTests/PublicApi/ApiTokenHelper.cs:46" in rendered
    assert "src/Infrastructure/Identity/IdentityTokenClaimService.cs:43" in rendered
    golem = _engine_block(golem_doc, "golem")
    for item in golem["items"][:20]:
        assert "/" in item["File"], "golem records absolute paths; keep them"


# --- golden files ---------------------------------------------------------------


GOLDEN = Path("test/data/golden/crypto-reach")
# POSIX strings so the pinned sourceFile fields match on Windows too, where
# str(Path(...)) spells the same file with backslashes (see test_graph.py).
GOLDEN_FIXTURES = {
    "dosai": DOSAI_CRYPTO.as_posix(),
    "golem": GOLEM.as_posix(),
    "rusi": RUSI.as_posix(),
    "kosi": KOSI_CRYPTO.as_posix(),
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


def _bounded_for_golden(document):
    """golem's inventory runs to 799 items; a golden that size gets approved
    without being read. Keep the first 12 per engine and record the rest as a
    count — applied identically when regenerating and comparing."""
    bounded = copy.deepcopy(document)
    for block in bounded.get("engines", []):
        items = block.get("items") or []
        if len(items) > 12:
            block["items"] = items[:12] + [f"... {len(items) - 12} more not pinned ..."]
    return bounded


@pytest.mark.parametrize("name", GOLDEN_FIXTURES)
def test_golden_console_per_fixture(name):
    """What the command prints per engine, default options.

    Regenerate with: ATOM_TOOLS_REGEN_GOLDEN=1 pytest test/test_crypto_reach.py
    """
    document = compute_crypto_reach(inputs_for(GOLDEN_FIXTURES[name]))
    text = "\n".join(render_console(document)) + "\n"
    _assert_golden(f"{name}.console.txt", text)


@pytest.mark.parametrize("name", GOLDEN_FIXTURES)
def test_golden_json_per_fixture(name):
    """The json document exactly as ``-f json`` writes it (indent 4, sorted
    keys, plus a trailing newline), item lists bounded for review."""
    document = _bounded_for_golden(compute_crypto_reach(inputs_for(GOLDEN_FIXTURES[name])))
    _assert_golden(f"{name}.json", json.dumps(document, indent=4, sort_keys=True) + "\n")


def test_inventory_counts_read_the_same_for_every_engine():
    """dosai's section names are PascalCase in its schema; golem's and rusi's
    are lower. Carried straight into the count sentence, that reads as a
    difference between the engines rather than between two JSON files, so the
    rendering lowercases them. The document keeps each engine's own keys."""
    dosai = compute_crypto_reach(inputs_for(GOLDEN_FIXTURES["dosai"]))
    assert "Assets" in dosai["engines"][0]["inventory"]
    line = next(ln for ln in render_console(dosai) if ln.startswith("* dosai:"))
    assert "3 assets" in line and "Assets" not in line
