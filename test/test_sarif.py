"""Tests for the SARIF export of reachable slices."""

from collections import Counter

from atom_tools.lib.sarif import Sarif, flow_fingerprint, node_tags, normalise_path, rule_for

CHUNKED = "test/data/chunked/js-juiceshop-reachables.json"
PETCLINIC = "test/data/java-petclinic-reachables.json"
JUICESHOP = "test/data/js-juiceshop-reachables.json"


def test_normalise_path():
    assert normalise_path("routes\\likeProductReviews.ts") == "routes/likeProductReviews.ts"
    assert normalise_path("a/b.py") == "a/b.py"


def test_node_tags_drops_purls_and_framework():
    tags = node_tags({"tags": "framework-input, pkg:npm/express@4.18.2, framework"})
    assert tags == ["framework-input"]


def test_rule_for_sink_and_source_tags():
    # High risk sink tags win regardless of order.
    assert rule_for(["sql"]) == ("atom:sql", "error")
    assert rule_for(["framework-input", "ssrf"]) == ("atom:ssrf", "error")
    # Source-side tags alone still produce a warning rule: atom frequently
    # tags only the source end of a flow.
    assert rule_for(["pii"]) == ("atom:pii", "warning")
    assert rule_for(["framework-input"]) == ("atom:framework-input", "warning")
    assert rule_for(["unheard-of"]) == ("atom:reachable-flow", "note")
    assert rule_for([]) == ("atom:reachable-flow", "note")


def _results(fixture):
    doc = Sarif(fixture, "js").convert()
    return doc["runs"][0]


def test_convert_reachables_to_sarif():
    run = _results(CHUNKED)
    assert run["tool"]["driver"]["name"] == "atom-tools"
    results = run["results"]
    assert results, "chunked fixture should produce SARIF results"
    rule_ids = {r["ruleId"] for r in results}
    assert all(r.startswith("atom:") for r in rule_ids)
    # Rules referenced by results are all declared on the driver.
    declared = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert rule_ids <= declared
    for result in results:
        assert result["level"] in ("error", "warning", "note")
        assert result["message"]["text"].startswith("Data flows from")
        assert result["partialFingerprints"]["atomToolsFlow/v1"]
        if "locations" in result:
            uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            assert "\\" not in uri
            assert "startLine" in result["locations"][0]["physicalLocation"]["region"]
        if "codeFlows" in result:
            thread = result["codeFlows"][0]["threadFlows"][0]["locations"]
            assert thread, "code flows must trace the source to sink path"


def test_source_tags_drive_rules_on_real_atom_output():
    # Regression: the latest atom tags the source end of Java flows
    # (framework-input, pii-*) and leaves sinks untagged, so sink-only tag
    # collection produced 163 undifferentiated notes.
    run = _results(PETCLINIC)
    rules = Counter(r["ruleId"] for r in run["results"])
    assert "atom:framework-input" in rules
    assert "atom:sensitive-data" in rules
    assert rules["atom:reachable-flow"] < len(run["results"])
    levels = Counter(r["level"] for r in run["results"])
    assert levels["warning"] > 0


def test_fingerprints_unique_on_real_fixtures():
    for fixture in (PETCLINIC, JUICESHOP):
        run = _results(fixture)
        fingerprints = [
            r["partialFingerprints"]["atomToolsFlow/v1"] for r in run["results"]
        ]
        duplicates = [f for f, c in Counter(fingerprints).items() if c > 1]
        # Remaining duplicates must be genuinely identical flows (atom emits
        # the same flow twice with different CPG node ids); GitHub should
        # merge those alerts.
        entries = Sarif(fixture).entries
        by_fingerprint = {}
        for entry in entries:
            by_fingerprint.setdefault(flow_fingerprint(entry), []).append(entry)
        for fp in duplicates:
            normalised = [
                tuple(
                    (n.get("parentFileName"), n.get("lineNumber"), n.get("code"))
                    for n in e.get("flows", [])
                )
                for e in by_fingerprint[fp]
            ]
            assert len(set(normalised)) == 1, f"fingerprint {fp} merges distinct flows"


def test_fingerprint_distinguishes_same_location_flows():
    # Flows on the same file:line that differ only by purls or column must
    # not share a fingerprint - GitHub would silently merge the alerts.
    def entry(code, column, purls):
        return {
            "flows": [
                {
                    "parentFileName": "a.ts",
                    "lineNumber": 1,
                    "columnNumber": column,
                    "name": "x",
                    "code": code,
                }
            ],
            "purls": purls,
        }

    fps = {
        flow_fingerprint(entry("a()", 1, ["pkg:npm/a@1"])),
        flow_fingerprint(entry("a()", 1, ["pkg:npm/b@1"])),
        flow_fingerprint(entry("b()", 1, ["pkg:npm/a@1"])),
        flow_fingerprint(entry("a()", 2, ["pkg:npm/a@1"])),
    }
    assert len(fps) == 4


def test_convert_chunked_sees_all_chunks():
    doc = Sarif(CHUNKED, "js").convert()
    single = Sarif("test/data/chunked/js-juiceshop-reachables_1.json", "js").convert()
    assert len(doc["runs"][0]["results"]) > len(single["runs"][0]["results"])


def test_convert_empty_slice(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text('{"reachables": []}')
    doc = Sarif(str(empty), "js").convert()
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []
