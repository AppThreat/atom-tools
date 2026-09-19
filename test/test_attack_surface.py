"""Tests for the attack-surface command and the exposure view it computes.

The dosai fixture is the oracle for grouping and tiering: its own
``AttackSurface[]`` array classifies all 60 entry points into
anonymous-http 27 / queue 2 / cli 7 / authenticated-http 24, with per-entry
weakness data. Every ranking key is constant across that fixture, so ranking
itself is asserted on constructed input instead of tuned until the oracle
"looked right" — the oracle's numbers are already right, and they are zero.

The reach numbers for golem and rusi are the real output of the call-graph
join over the committed fixtures; see PROVENANCE.md for what those call
graphs contain and what was trimmed from them.
"""

import copy
import json
import os
import re
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application
from atom_tools.lib.adapters import parse_report
from atom_tools.lib.attack_surface import (
    SURFACE_VERSION,
    TIERS,
    UNKNOWN_AUTH,
    SurfaceInput,
    compute_attack_surface,
    is_usages_slice,
    render_console,
    render_html,
    render_mermaid,
)
from atom_tools.lib.drift import compute_drift

ECOSYSTEM = Path("test/data/ecosystem")
DOSAI = ECOSYSTEM / "dotnet-eshoponweb-dosai-dataflows.json"
DOSAI_METHODS = ECOSYSTEM / "dotnet-eshoponweb-dosai-methods.json"
GOLEM = ECOSYSTEM / "go-ipsw-golem.json"
GOLEM_BASELINE = ECOSYSTEM / "go-ipsw-golem-baseline.json"
RUSI = ECOSYSTEM / "rust-microservices-kafka-rusi.json"
PETCLINIC = Path("test/data/java-petclinic-reachables.json")
PIGGYMETRICS = Path("test/data/java-piggymetrics-usages.json")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def inputs_for(*paths):
    inputs = []
    for path in paths:
        raw = load(path)
        report = None if is_usages_slice(raw) else parse_report(raw, source_file=str(path))
        inputs.append(SurfaceInput(report=report, raw=raw, path=str(path)))
    return inputs


def surface(*paths, min_exposure=""):
    return compute_attack_surface(inputs_for(*paths), min_exposure=min_exposure)


def entries_of(document, tier):
    for tier_doc in document["tiers"]:
        if tier_doc["Exposure"] == tier:
            return tier_doc
    return None


def all_entries(document):
    return [entry for tier in document["tiers"] for entry in tier["EntryPoints"]]


# --- tier ordering ---------------------------------------------------------


def test_tier_order_is_dosai_documentation_order_plus_unknown_auth():
    assert TIERS == (
        "anonymous-http",
        "anonymous-rpc",
        "anonymous",
        "mcp",
        "queue",
        "cli",
        "authenticated-http",
        "authenticated-rpc",
        "internal",
    )
    # unknown-auth sorts after every known tier: nothing about it is known, so
    # it must not be read as outranking or sitting under any of them.
    document = surface(GOLEM)
    assert document["tierOrder"] == [*TIERS, UNKNOWN_AUTH]
    assert [tier["Exposure"] for tier in document["tiers"]] == [UNKNOWN_AUTH]


# --- dosai: the oracle ------------------------------------------------------


@pytest.fixture(scope="module")
def dosai_surface():
    return surface(DOSAI)


def test_dosai_grouping_reproduces_the_engine_oracle(dosai_surface):
    """Tier membership and counts must be exactly dosai's own verdict."""
    oracle = {row["Exposure"]: row for row in load(DOSAI)["AttackSurface"]}
    computed = {tier["Exposure"]: tier for tier in dosai_surface["tiers"]}
    assert set(computed) == set(oracle) == {
        "anonymous-http",
        "queue",
        "cli",
        "authenticated-http",
    }
    for exposure, expected in oracle.items():
        actual = computed[exposure]
        assert actual["EntryPointCount"] == expected["EntryPointCount"]
        assert actual["WeaknessCount"] == expected["WeaknessCount"]
        assert actual["HighSeverityWeaknessCount"] == expected["HighSeverityWeaknessCount"]
        assert {e["EntryPointId"] for e in actual["EntryPoints"]} == {
            e["EntryPointId"] for e in expected["EntryPoints"]
        }
    counts = [computed[t]["EntryPointCount"] for t in
              ("anonymous-http", "queue", "cli", "authenticated-http")]
    assert counts == [27, 2, 7, 24]
    assert dosai_surface["summary"]["entryPoints"] == 60


def test_dosai_tiering_is_the_engines_own_not_rederived(dosai_surface):
    """AllowAnonymous does not decide the tier — 24 of the 27 anonymous entry
    points carry AllowAnonymous: false in the fixture, so any re-derivation
    from that flag would disagree with the engine on most of its verdicts."""
    anonymous = entries_of(dosai_surface, "anonymous-http")["EntryPoints"]
    flags = [entry["AllowAnonymous"] for entry in anonymous]
    assert flags.count(False) == 24
    assert flags.count(True) == 3
    assert all(entry["Exposure"] == "anonymous-http" for entry in anonymous)


def test_dosai_weakness_data_is_taken_verbatim(dosai_surface):
    """The engine's per-entry weakness counts travel through untouched."""
    cli = entries_of(dosai_surface, "cli")
    assert cli["WeaknessCount"] == 81
    carrying = [entry for entry in cli["EntryPoints"] if entry["WeaknessCount"]]
    assert len(carrying) == 1
    assert carrying[0]["HighSeverityWeaknessCount"] == 0
    assert carrying[0]["SinkCategories"] == ["log"]
    assert carrying[0]["Cwes"] == ["CWE-117"]
    assert carrying[0]["WeaknessKinds"] == ["LogInjectionCandidate"]


def test_dosai_reach_state_is_engine_and_headline_is_printed(dosai_surface):
    """The engine classified every entry point, so the headline has a real
    denominator — even though every weakness count on this target is zero."""
    assert dosai_surface["summary"]["reachComputed"] is True
    assert all(entry["Reach"]["state"] == "engine" for entry in all_entries(dosai_surface))
    assert dosai_surface["summary"]["headline"] == (
        "0 of 27 anonymous entry points (0%) reach at least one high-risk sink"
        " (27 of 60 entry points are anonymous)."
    )


def test_json_shape_is_dosai_attack_surface_compatible(dosai_surface):
    tier = dosai_surface["tiers"][0]
    for key in (
        "Exposure",
        "EntryPointCount",
        "ExploitChainCount",
        "WeaknessCount",
        "HighSeverityWeaknessCount",
        "EntryPointsTruncated",
        "EntryPoints",
    ):
        assert key in tier
    entry = tier["EntryPoints"][0]
    for key in (
        "EntryPointId",
        "Exposure",
        "Kind",
        "HttpMethod",
        "Route",
        "FileName",
        "LineNumber",
        "AllowAnonymous",
        "ExploitChainCount",
        "WeaknessCount",
        "HighSeverityWeaknessCount",
        "WeaknessKinds",
        "Cwes",
        "SinkCategories",
    ):
        assert key in entry, key


def test_dosai_methods_input_adds_only_its_extra_entry_points():
    """The methods report carries 57 EntryPoints, 53 of them shared with the
    dataflows fixture; the four extra ones have no AttackSurface record and
    fall back to kind-derived tiers, which is diagnosed, not hidden."""
    document = surface(DOSAI, DOSAI_METHODS)
    assert document["summary"]["entryPoints"] == 64
    assert any(
        "4 dosai entry point(s)" in diagnostic and "kind-derived" in diagnostic
        for diagnostic in document["diagnostics"]
    )
    assert entries_of(document, "cli")["EntryPointCount"] == 11


# --- golem: the call-graph join ----------------------------------------------

@pytest.fixture(scope="module")
def golem_surface():
    return surface(GOLEM)


def test_golem_endpoints_land_in_unknown_auth(golem_surface):
    tier = entries_of(golem_surface, UNKNOWN_AUTH)
    assert tier["EntryPointCount"] == 57
    assert all(entry["AllowAnonymous"] is None for entry in tier["EntryPoints"])


def test_golem_join_coverage_is_reported_honestly(golem_surface):
    """31 of 57 handlers anchor in the (endpoint-reachable) call graph; the
    rest are seed-not-found — a gap, never folded into reaches-nothing."""
    coverage = golem_surface["coverage"]["golem"]
    assert coverage["endpoints"] == 57
    assert coverage["endpointsAnchored"] == 31
    assert coverage["flows"] == 397
    states = [entry["Reach"]["state"] for entry in all_entries(golem_surface)]
    assert states.count("computed") == 31
    assert states.count("seed-not-found") == 26
    assert any("subgraph of the engine's run" in d for d in golem_surface["diagnostics"])
    assert any("seed-not-found" in d for d in golem_surface["diagnostics"])


def test_golem_endpoints_with_no_flows_still_appear(golem_surface):
    """An unreached route is a finding about analysis coverage, not something
    to hide: every endpoint is listed, including the 41 without reach."""
    entries = all_entries(golem_surface)
    assert len(entries) == 57
    with_reach = [entry for entry in entries if entry["Reach"]["flows"]]
    assert len(with_reach) == 16
    without = [entry for entry in entries if not entry["Reach"]["flows"]]
    assert without, "endpoints with no reach must still be listed"
    assert {entry["Reach"]["state"] for entry in without} == {"computed", "seed-not-found"}


def test_golem_reach_attaches_real_flows(golem_surface):
    """The join is not decorative: 179 flow attachments over 16 endpoints, and
    the heaviest endpoint reaches sinks the engine itself categorised."""
    entries = all_entries(golem_surface)
    assert sum(entry["Reach"]["flows"] for entry in entries) == 179
    by_path = {entry["Route"]: entry for entry in entries if entry["Route"]}
    assert by_path["/idev/amfi/dev"]["Reach"]["flows"] == 68
    assert by_path["/idev/amfi/dev"]["Reach"]["sinkCategories"] == [
        "crypto",
        "http-response",
        "panic",
    ]
    assert by_path["/dsc/info"]["Reach"]["sinkCategories"] == [
        "filesystem",
        "http-response",
        "logging",
    ]


def test_retrimmed_fixture_does_not_disturb_drift():
    """The fixture's call graph is trimmed around the endpoint closure now;
    the dataFlow section the drift oracle asserts must be untouched."""
    baseline = parse_report(load(GOLEM_BASELINE), source_file="baseline")
    current = parse_report(load(GOLEM), source_file="current")
    drift = compute_drift(baseline, current)
    assert drift["coverage"]["new"]["flows"] == 397
    assert drift["RiskDelta"]["NewEntryPoints"] == 3
    # the baseline fixture is untouched by the re-trim and keeps its own view
    assert surface(GOLEM_BASELINE)["summary"]["entryPoints"] == 55


# --- rusi: the join on an untrimmed call graph --------------------------------

@pytest.fixture(scope="module")
def rusi_surface():
    return surface(RUSI)


def test_rusi_every_handler_anchors_but_most_reach_nothing(rusi_surface):
    """rusi's call graph is complete, and every qualified handler anchors in
    it — yet only two endpoints reach any analysed flow. That is the honest
    answer: the five slices in this fixture sit outside the endpoint closures."""
    coverage = rusi_surface["coverage"]["rusi"]
    assert coverage["endpointsAnchored"] == 14
    states = [entry["Reach"]["state"] for entry in all_entries(rusi_surface)]
    assert states.count("computed") == 14
    assert states.count("seed-not-found") == 0
    reaching = [entry for entry in all_entries(rusi_surface) if entry["Reach"]["flows"]]
    assert [(entry["Route"], entry["Reach"]["flows"], entry["Reach"]["sinkCategories"])
            for entry in reaching] == [
        ("/users", 1, ["network-request"]),
        ("/users/search", 1, ["network-request"]),
    ]


def test_rusi_five_handlers_need_the_name_fallback(rusi_surface):
    """Five endpoints carry a package_path that disagrees with the call
    graph's node for the same qualified handler; they anchor by name alone and
    say so, because that reach may belong to a same-named function in another
    package — a quirk of the engine's endpoint table, reported not patched."""
    noted = [entry for entry in all_entries(rusi_surface) if entry["Reach"].get("note")]
    assert len(noted) == 5
    assert all("anchored by handler name alone" in entry["Reach"]["note"] for entry in noted)


# --- atom ---------------------------------------------------------------------


def test_atom_usages_entry_points_are_the_real_conversion_output():
    """query-endpoints prints 18 paths for piggymetrics; as entry points they
    are path × operation pairs, which is 21 — each a distinct exposure."""
    document = surface(PIGGYMETRICS)
    assert document["summary"]["entryPoints"] == 21
    assert document["summary"]["byTier"] == {UNKNOWN_AUTH: 21}
    entries = document["tiers"][0]["EntryPoints"]
    assert len({entry["Route"] for entry in entries}) == 18
    assert {entry["Reach"]["state"] for entry in entries} == {"not-computed"}
    assert all("not computed" in (entry["Reach"].get("note") or "") for entry in entries)


def test_atom_reachables_route_tags_produce_one_joinable_entry_point():
    """petclinic's reachables document carries exactly two framework-route
    marker nodes, both terminating flows in OwnerController.showOwner — one
    entry point, reached by two flows through the source-location join."""
    document = surface(PETCLINIC)
    assert document["summary"]["entryPoints"] == 1
    entry = document["tiers"][0]["EntryPoints"][0]
    assert entry["Reach"]["state"] == "computed"
    assert entry["Reach"]["flows"] == 2
    assert entry["Handler"] == "showOwner"
    assert entry["File"].endswith("OwnerController.java")
    assert document["coverage"]["atom"]["note"].startswith("atom emits no call graph")


# --- ranking (constructed input; the oracle cannot exercise it) -----------------


def dosai_like(entry_points, surface_rows):
    """A minimal dosai dataflows document with just the sections read here."""
    return {
        "Metadata": {"Tool": "Dosai", "SchemaVersion": "5.0.0"},
        "Slices": [],
        "Nodes": [],
        "Edges": [],
        "EntryPoints": entry_points,
        "AttackSurface": surface_rows,
    }


def surface_of(raw):
    report = parse_report(raw, source_file="constructed")
    return compute_attack_surface([SurfaceInput(report=report, raw=raw, path="constructed")])


def test_ranking_within_a_tier_follows_dosai_ordering():
    """High-severity weaknesses, then weaknesses, then chains — all
    descending; ties break deterministically. dosai's fixture cannot exercise
    this: every ranking key on it is constant."""
    raw = dosai_like(
        [
            {"Id": "ep1", "Kind": "HttpController", "Route": "/a", "HttpMethod": "GET"},
            {"Id": "ep2", "Kind": "HttpController", "Route": "/b", "HttpMethod": "GET"},
            {"Id": "ep3", "Kind": "HttpController", "Route": "/c", "HttpMethod": "GET"},
            {"Id": "ep4", "Kind": "HttpController", "Route": "/d", "HttpMethod": "GET"},
        ],
        [
            {
                "Exposure": "anonymous-http",
                "EntryPoints": [
                    {"EntryPointId": "ep1", "WeaknessCount": 3, "HighSeverityWeaknessCount": 0},
                    {"EntryPointId": "ep2", "WeaknessCount": 1, "HighSeverityWeaknessCount": 2},
                    {
                        "EntryPointId": "ep3",
                        "WeaknessCount": 5,
                        "HighSeverityWeaknessCount": 0,
                        "ExploitChainCount": 1,
                    },
                    {"EntryPointId": "ep4", "WeaknessCount": 0, "HighSeverityWeaknessCount": 0},
                ],
            }
        ],
    )
    document = surface_of(raw)
    ids = [entry["EntryPointId"] for entry in document["tiers"][0]["EntryPoints"]]
    # ep2 outranks ep3 on high-severity count despite fewer total weaknesses;
    # ep3 outranks ep1 on total weaknesses; ep4's all-zero key sorts last.
    assert ids == ["ep2", "ep3", "ep1", "ep4"]


def test_tier_summaries_aggregate_their_entries():
    raw = dosai_like(
        [{"Id": "ep1", "Kind": "HttpController", "Route": "/a", "HttpMethod": "GET"}],
        [
            {
                "Exposure": "anonymous-http",
                "EntryPoints": [
                    {
                        "EntryPointId": "ep1",
                        "WeaknessCount": 4,
                        "HighSeverityWeaknessCount": 2,
                        "ExploitChainCount": 1,
                    }
                ],
            }
        ],
    )
    document = surface_of(raw)
    tier = document["tiers"][0]
    assert tier["WeaknessCount"] == 4
    assert tier["HighSeverityWeaknessCount"] == 2
    assert tier["ExploitChainCount"] == 1
    assert document["summary"]["headline"] == (
        "1 of 1 anonymous entry points (100%) reach at least one high-risk sink"
        " (1 of 1 entry points are anonymous)."
    )


def test_kind_derived_families_for_cli_and_queue_but_never_auth():
    raw = dosai_like(
        [
            {"Id": "ep1", "Kind": "Cli"},
            {"Id": "ep2", "Kind": "MessageConsumer"},
            {"Id": "ep3", "Kind": "GrpcService"},
        ],
        [],
    )
    document = surface_of(raw)
    tiers = {entry["EntryPointId"]: entry["Exposure"] for entry in all_entries(document)}
    assert tiers == {"ep1": "cli", "ep2": "queue", "ep3": UNKNOWN_AUTH}


# --- the honesty rules ----------------------------------------------------------


def test_headline_is_suppressed_when_no_engine_knows_authentication(golem_surface):
    assert golem_surface["summary"].get("headline") is None
    assert golem_surface["summary"]["anonymousReach"]["computed"] is False
    lines = render_console(golem_surface)
    assert any("headline suppressed" in line for line in lines)


def test_min_exposure_filters_and_counts_what_it_hid(dosai_surface, golem_surface):
    filtered = compute_attack_surface(inputs_for(DOSAI), min_exposure="anonymous-http")
    assert [tier["Exposure"] for tier in filtered["tiers"]] == ["anonymous-http"]
    assert entries_of(filtered, "anonymous-http")["EntryPointCount"] == 27
    assert any("filtered out 33" in diagnostic for diagnostic in filtered["diagnostics"])

    everything = compute_attack_surface(inputs_for(GOLEM), min_exposure="anonymous")
    # unknown-auth never matches a minimum-exposure bar: claiming it does
    # would be exactly the guess this command exists to avoid.
    assert everything["tiers"] == []
    assert any("filtered out 57" in diagnostic for diagnostic in everything["diagnostics"])


def test_min_exposure_rejects_unknown_tiers(dosai_surface):
    with pytest.raises(ValueError) as excinfo:
        compute_attack_surface(inputs_for(DOSAI), min_exposure="superuser")
    assert "Unknown exposure" in str(excinfo.value)


def test_console_renders_unknown_auth_as_a_gap_not_a_tier(golem_surface):
    lines = render_console(golem_surface)
    assert any("unknown-auth" in line and "auth unknown" in line for line in lines)
    assert any("reach: seed-not-found" in line for line in lines)
    assert any("reach: computed — reaches no analysed flow" in line for line in lines)


def test_console_states_cover_all_four_reach_states(dosai_surface, golem_surface, rusi_surface):
    assert any("reach: engine" in line for line in render_console(dosai_surface))
    assert any(
        "reach: not computed" in line for line in render_console(surface(PIGGYMETRICS))
    )
    assert any("reach: seed-not-found" in line for line in render_console(golem_surface))
    assert any(
        "reach: computed — reaches no analysed flow" in line
        for line in render_console(rusi_surface)
    )


def test_console_listing_truncates_honestly(golem_surface):
    lines = render_console(golem_surface, max_entries=5)
    assert any("listing truncated at --max-entries 5" in line for line in lines)
    # the json document itself is never truncated
    assert golem_surface["summary"]["entryPoints"] == 57


def test_mermaid_groups_by_tier_and_html_embeds_it(golem_surface):
    diagram = render_mermaid(golem_surface)
    assert diagram.startswith("flowchart TB")
    assert 'subgraph tier0["unknown-auth — 57 (auth unknown)"]' in diagram
    # every endpoint draws a node; only reached sink categories draw edges
    assert diagram.count(":::entry") == 57
    assert '"crypto"]:::sinkHigh' in diagram
    html = render_html(golem_surface, diagram, str(GOLEM))
    assert "Attack surface" in html
    assert "auth unknown" in html
    assert "Anonymous reach not reported" in html


def test_document_carries_version_engines_and_sources():
    document = surface(DOSAI, RUSI)
    assert document["attackSurfaceVersion"] == SURFACE_VERSION
    assert document["engine"] == "dosai+rusi"
    assert len(document["sources"]) == 2
    assert document["summary"]["byEngine"] == {"dosai": 60, "rusi": 14}


# --- the command -----------------------------------------------------------------


def test_command_writes_json_and_exits_zero(tmp_path):
    app = Application()
    tester = CommandTester(app.find("attack-surface"))
    out = tmp_path / "surface.json"
    tester.execute(f"-i {RUSI} -f json -o {out}")
    assert tester.status_code == 0
    document = json.loads(out.read_text())
    assert document["attackSurfaceVersion"] == SURFACE_VERSION
    assert document["summary"]["entryPoints"] == 14


def test_command_accepts_mixed_engines_and_globs(tmp_path):
    app = Application()
    tester = CommandTester(app.find("attack-surface"))
    out = tmp_path / "surface.json"
    tester.execute(f"-i '{DOSAI},{RUSI}' -f json -o {out}")
    assert tester.status_code == 0
    document = json.loads(out.read_text())
    assert document["summary"]["byEngine"] == {"dosai": 60, "rusi": 14}
    # a glob: both rusi fixtures share one endpoint table, which de-duplicates
    tester.execute(f"-i '{ECOSYSTEM}/rust-microservices-kafka-rusi*.json' -f json -o {out}")
    document = json.loads(out.read_text())
    assert document["summary"]["entryPoints"] == 14
    assert document["engine"] == "rusi"


def test_command_console_output_goes_through_cleo_io():
    """query-endpoints prints with bare print(), which bypasses cleo's io and
    hid an empty-listing regression from every test; this command must be
    capturable."""
    app = Application()
    tester = CommandTester(app.find("attack-surface"))
    tester.execute(f"-i {GOLEM}")
    output = tester.io.fetch_output()
    assert "57 entry point(s)" in output
    assert "seed-not-found" in output
    assert "headline suppressed" in output


def test_command_accepts_comma_separated_formats(tmp_path):
    """The spec's own example invocation is --format console,html."""
    app = Application()
    tester = CommandTester(app.find("attack-surface"))
    out = tmp_path / "surface"
    tester.execute(f"-i {RUSI} -f console,html -o {out}")
    assert tester.status_code == 0
    output = tester.io.fetch_output()
    assert "14 entry point(s)" in output
    assert "Written to" in output
    assert (tmp_path / "surface.mmd").exists()
    assert (tmp_path / "surface.html").exists()


def test_command_rejects_unknown_format_and_bad_max_entries():
    app = Application()
    tester = CommandTester(app.find("attack-surface"))
    with pytest.raises(ValueError) as excinfo:
        tester.execute(f"-i {RUSI} -f yaml")
    assert "Unknown format" in str(excinfo.value)
    with pytest.raises(ValueError) as excinfo:
        tester.execute(f"-i {RUSI} --max-entries many")
    assert "Invalid --max-entries" in str(excinfo.value)


def test_command_writes_html_and_mermaid(tmp_path):
    app = Application()
    tester = CommandTester(app.find("attack-surface"))
    tester.execute(f"-i {RUSI} -f html -o {tmp_path / 'surface'}")
    assert tester.status_code == 0
    assert (tmp_path / "surface.mmd").exists()
    html = (tmp_path / "surface.html").read_text()
    assert "Attack surface" in html


def test_headline_counts_high_risk_sinks_not_only_engine_weakness_counts():
    """
    The headline says "reach at least one high-risk sink", so it must read the
    reach. Counting only the engine's HighSeverityWeaknessCount made it claim
    one thing and measure another, and reported 0 for every engine that emits
    no weakness counts at all -- which is every engine except dosai.

    `command` maps onto `command-injection` through the shared taxonomy, the
    same mapping `unified.py` uses; `logging` maps onto nothing high-risk.
    """
    def one(sink_category, high=0):
        raw = dosai_like(
            [{"Id": "ep1", "Kind": "HttpController", "Route": "/a", "HttpMethod": "GET"}],
            [
                {
                    "Exposure": "anonymous-http",
                    "EntryPoints": [
                        {
                            "EntryPointId": "ep1",
                            "HighSeverityWeaknessCount": high,
                            "SinkCategories": [sink_category],
                        }
                    ],
                }
            ],
        )
        return surface_of(raw)["summary"]

    assert one("command")["anonymousReach"]["reachingHighSeveritySink"] == 1
    assert one("logging")["anonymousReach"]["reachingHighSeveritySink"] == 0
    # The engine's own count still counts on its own, for engines that emit it.
    assert one("logging", high=3)["anonymousReach"]["reachingHighSeveritySink"] == 1


# --- kosi: tiers only as far as the declarations go ----------------------------

KOSI_DSL = ECOSYSTEM / "kotlin-dsl-media-auth-kosi.json"
KOSI_ANDROID = ECOSYSTEM / "kotlin-android-manifest-app-kosi.json"
KOSI_FLOWS = ECOSYSTEM / "kotlin-command-exec-kosi.json"


@pytest.fixture(scope="module")
def kosi_surface():
    return surface(KOSI_DSL)


def test_kosi_declared_requirements_lift_the_tier(kosi_surface):
    """A non-empty ``authentication`` list is a positive statement. The two
    endpoints with declared requirements land in authenticated-http with
    ``tier_source`` "engine", and the evidence names the field they came
    from."""
    tier = entries_of(kosi_surface, "authenticated-http")
    assert tier["EntryPointCount"] == 2
    assert tier["TierSource"] == ["engine"]
    by_route = {e["Route"]: e for e in tier["EntryPoints"]}
    assert by_route["/admin"]["AllowAnonymous"] is False
    assert by_route["/admin"]["ExposureEvidence"] == "declares role(ADMIN)"
    assert by_route["/legacy/*"]["ExposureEvidence"] == (
        "declares security-constraint(admin,auditor)"
    )


def test_kosi_deny_rule_is_internal_not_authenticated(kosi_surface):
    """``security-constraint(denied)`` refuses every caller; matching the
    "security-constraint" substring would call a closed route
    "authenticated". It is the least-exposed tier instead, with the deny rule
    spelled out in the evidence."""
    tier = entries_of(kosi_surface, "internal")
    assert tier["EntryPointCount"] == 1
    entry = tier["EntryPoints"][0]
    assert entry["Route"] == "/denied"
    assert entry["AllowAnonymous"] is False
    assert "deny rule" in entry["ExposureEvidence"]
    assert "security-constraint(denied)" in entry["ExposureEvidence"]


def test_kosi_empty_declaration_is_not_anonymous(kosi_surface):
    """The heart of the honesty question: ``authentication: []`` means no
    requirement was declared at a site kosi models — a filter kosi does not
    model may still guard the route. Those eight endpoints stay in
    unknown-auth, and no anonymous tier exists anywhere in the document."""
    unknown = entries_of(kosi_surface, UNKNOWN_AUTH)
    assert unknown["EntryPointCount"] == 8
    assert all(e["AllowAnonymous"] is None for e in unknown["EntryPoints"])
    assert all(
        t["Exposure"] != "anonymous-http" for t in kosi_surface["tiers"]
    )
    assert kosi_surface["summary"]["anonymousReach"]["computed"] is False


def test_kosi_unresolved_method_is_not_labelled_any(kosi_surface):
    """An empty httpMethod list means no method was resolved at a site kosi
    models — printing our own "ANY" would assert every method over a route
    whose method kosi could not name."""
    unknown = entries_of(kosi_surface, UNKNOWN_AUTH)
    secure = next(e for e in unknown["EntryPoints"] if e["Route"] == "/secure")
    assert secure["HttpMethod"] is None
    assert secure["MethodUnresolved"] is True
    # The dsl routes carry kosi's unattributed-route finding; kind stays the
    # honest "http-route" the adapter records for them.
    assert secure["Kind"] == "http-route"
    # The label prints the path alone; the text rendering must agree.
    text = "\n".join(render_console(kosi_surface))
    assert "├── /secure " in text
    assert "ANY /secure" not in text


def test_kosi_exported_false_is_internal_and_true_is_not_anonymous():
    """``exported: false`` is a positive statement (not externally
    launchable) and maps to internal; ``exported: true`` says reachable,
    which is not anonymous — those endpoints stay in unknown-auth."""
    document = surface(KOSI_ANDROID)
    internal = entries_of(document, "internal")
    assert internal["EntryPointCount"] == 2
    assert all(e["AllowAnonymous"] is None for e in internal["EntryPoints"])
    assert all("not exported" in e["ExposureEvidence"] for e in internal["EntryPoints"])
    unknown = entries_of(document, UNKNOWN_AUTH)
    # The exported-true components (per the manifest itself) stay unknown.
    assert {e["Route"] for e in unknown["EntryPoints"]} == {
        "MetaProvider",
        "android.intent.action.MAIN",
        "android.intent.action.VIEW",
    }
    assert all(t["Exposure"] != "anonymous-http" for t in document["tiers"])


def test_kosi_engine_slice_link_is_the_reach_verdict():
    """The one endpoint whose record names its slices carries the engine's
    own reach (state "engine"), not a traversal result — and the note says
    so. No other engine except dosai supplies its verdicts like this."""
    document = surface(KOSI_FLOWS)
    entry = all_entries(document)[0]
    assert entry["Route"] == "/run"
    assert entry["Reach"]["state"] == "engine"
    assert entry["Reach"]["flows"] == 1
    assert entry["Reach"]["flowIds"] == ["slice-000001"]
    assert "sliceIds" in entry["Reach"]["note"]
    assert document["coverage"]["kosi"]["endpointsEngineLinked"] == 1


# --- golden files ---------------------------------------------------------------


GOLDEN = Path("test/data/golden/attack-surface")
# POSIX strings so the pinned sourceFile fields match on Windows too, where
# str(Path(...)) spells the same file with backslashes (see test_graph.py).
GOLDEN_FIXTURES = {
    "dosai": DOSAI.as_posix(),
    "golem": GOLEM.as_posix(),
    "rusi": RUSI.as_posix(),
    "kosi": KOSI_DSL.as_posix(),
    "atom": PETCLINIC.as_posix(),
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
    """The dosai/golem documents carry 60/57 entry points; a golden that size
    gets approved without being read. Keep the first 8 per tier and record the
    rest as a count — applied identically when regenerating and comparing, so
    the pinned prefix is exact and the tail is consciously not."""
    bounded = copy.deepcopy(document)
    for tier in bounded["tiers"]:
        eps = tier.get("EntryPoints") or []
        if len(eps) > 5:
            tier["EntryPoints"] = eps[:5] + [
                f"... {len(eps) - 5} more entry point(s) not pinned ..."
            ]
    return bounded


@pytest.mark.parametrize("name", GOLDEN_FIXTURES)
def test_golden_console_per_fixture(name):
    """What the command prints per engine, default options.

    Regenerate with: ATOM_TOOLS_REGEN_GOLDEN=1 pytest test/test_attack_surface.py
    """
    text = "\n".join(render_console(surface(GOLDEN_FIXTURES[name]))) + "\n"
    _assert_golden(f"{name}.console.txt", text)


@pytest.mark.parametrize("name", GOLDEN_FIXTURES)
def test_golden_json_per_fixture(name):
    """The json document exactly as ``-f json`` writes it (indent 4, sorted
    keys, plus a trailing newline), entry-point lists bounded for review."""
    document = _bounded_for_golden(surface(GOLDEN_FIXTURES[name]))
    _assert_golden(f"{name}.json", json.dumps(document, indent=4, sort_keys=True) + "\n")


def test_a_path_that_names_its_own_method_is_not_labelled_any():
    """golem records Go 1.22 ServeMux patterns whole as the path.

    ``"GET /static/"`` arrives with an empty method, and labelling it ``ANY``
    puts our own assertion -- that the route answers every method -- directly
    beside a path that already says GET. Print such a path alone; a route that
    really has no method still gets the ``ANY`` hedge.
    """
    lines = render_console(surface(GOLEM))
    static = [ln.strip() for ln in lines if "ent/ui.go:58" in ln]
    assert static and static[0].startswith("\u251c\u2500\u2500 /GET /static/")
    assert not any("ANY /GET " in ln for ln in lines)
    # A route reported with neither a method nor a method-bearing path keeps
    # the hedge, so this is not a blanket removal of the word. dosai's razor
    # pages are that case.
    assert any(re.search(r"ANY /[A-Za-z]", ln) for ln in render_console(surface(DOSAI)))
