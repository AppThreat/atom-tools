"""Tests for the generic source analysis pipeline (analyze command)."""

import json
import shutil
import subprocess

from atom_tools.lib.analysis_pipeline import (
    analyze_source,
    merge_chunked_reachables,
    run_atom_slices,
)
from atom_tools.lib.apk_pipeline import run_atom_slices as run_apk_atom_slices

REACHABLES_FIXTURE = "test/data/chunked/js-juiceshop-reachables.json"
USAGES_FIXTURE = "test/data/js-juiceshop-usages.json"


class FakeAtom:
    """Stands in for subprocess.run: records calls and writes slice fixtures."""

    def __init__(self, tmp_path, fail_reachables=False):
        self.tmp_path = tmp_path
        self.fail_reachables = fail_reachables
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        subcommand = args[1]
        out = args[args.index("-s") + 1]
        if subcommand == "reachables":
            if self.fail_reachables:
                return subprocess.CompletedProcess(args, 1, stdout="boom", stderr="")
            entries = json.load(open(REACHABLES_FIXTURE, encoding="utf-8"))
            json.dump(entries[:10], open(out, "w", encoding="utf-8"))
            # Simulate atom's chunking at 1000 entries (chunk 2 duplicates to
            # exercise the deduper).
            chunk = out.replace(".json", "_1.json")
            json.dump(entries[10:15], open(chunk, "w", encoding="utf-8"))
            atom_file = args[args.index("-o") + 1]
            open(atom_file, "w").write("fake-atom")
        elif subcommand == "usages":
            shutil.copy(USAGES_FIXTURE, out)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def test_run_atom_slices_command_construction(tmp_path, monkeypatch):
    fake = FakeAtom(tmp_path)
    monkeypatch.setattr("atom_tools.lib.analysis_pipeline.run_command", fake)
    result = run_atom_slices("atom", "/src/app", "python", str(tmp_path), "app")
    reachables_cmd, usages_cmd = fake.calls[0], fake.calls[1]
    assert reachables_cmd[:2] == ["atom", "reachables"]
    assert "-l" in reachables_cmd and "python" in reachables_cmd
    assert result["reachables"].endswith("app.reachables.json")
    assert usages_cmd[:2] == ["atom", "usages"]
    # The atom produced by the reachables pass is reused for usages.
    assert "--reuse-atom" in usages_cmd
    assert result["usages"].endswith("app.usages.json")


def test_run_atom_slices_skip_usages(tmp_path, monkeypatch):
    fake = FakeAtom(tmp_path)
    monkeypatch.setattr("atom_tools.lib.analysis_pipeline.run_command", fake)
    result = run_atom_slices("atom", "/src/app", "python", str(tmp_path), skip_usages=True)
    assert len(fake.calls) == 1
    assert result["usages"] is None
    assert result["reachables"]


def test_run_atom_slices_failure(tmp_path, monkeypatch):
    fake = FakeAtom(tmp_path, fail_reachables=True)
    monkeypatch.setattr("atom_tools.lib.analysis_pipeline.run_command", fake)
    result = run_atom_slices("atom", "/src/app", "python", str(tmp_path))
    assert result["reachables"] is None
    # usages is independent: it still runs, just without --reuse-atom.
    assert result["usages"]
    assert "--reuse-atom" not in fake.calls[1]


def test_apk_pipeline_delegates(tmp_path, monkeypatch):
    fake = FakeAtom(tmp_path)
    monkeypatch.setattr("atom_tools.lib.analysis_pipeline.run_command", fake)
    result = run_apk_atom_slices("atom", "/apps/demo.apk", str(tmp_path))
    assert fake.calls[0][fake.calls[0].index("-l") + 1] == "apk"
    assert result["reachables"].endswith("demo.apk.reachables.json")


def test_merge_chunked_reachables(tmp_path):
    base = tmp_path / "x.reachables.json"
    base.write_text('[{"flows": [{"parentFileName": "a.py", "lineNumber": 1}],"purls": []}]')
    chunk = tmp_path / "x.reachables_1.json"
    chunk.write_text('[{"flows": [{"parentFileName": "b.py", "lineNumber": 2}],"purls": []}]')
    merged = merge_chunked_reachables(str(base))
    assert merged == str(tmp_path / "x.reachables.merged.json")
    data = json.load(open(merged))
    assert len(data["reachables"]) == 2


def test_merge_chunked_reachables_no_chunks(tmp_path):
    base = tmp_path / "x.reachables.json"
    base.write_text('{"reachables": []}')
    assert merge_chunked_reachables(str(base)) is None


def test_analyze_source_full_pipeline(tmp_path, monkeypatch):
    fake = FakeAtom(tmp_path)
    monkeypatch.setattr("atom_tools.lib.analysis_pipeline.run_command", fake)
    src = tmp_path / "myproject"
    src.mkdir()
    result = analyze_source(
        str(src),
        "js",
        str(tmp_path / "reports"),
        atom_cmd="atom",
        extract_endpoints=True,
        generate_sarif=True,
    )
    assert result.errors == []
    reports = tmp_path / "reports"
    assert result.reachables_file == str(reports / "myproject.reachables.merged.json")
    merged = json.load(open(result.reachables_file))
    assert len(merged["reachables"]) == 15  # 10 + 5, duplicates dropped
    assert result.stats["slice_type"] == "reachables"
    assert result.stats["flow_groups"] == 15
    assert json.load(open(result.stats_file))["flow_groups"] == 15
    openapi = json.load(open(result.openapi_file))
    assert openapi["openapi"].startswith("3.1")
    assert openapi.get("paths"), "endpoints should be extracted from the usages slice"
    sarif = json.load(open(result.sarif_file))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"]


def test_analyze_source_atom_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("atom_tools.lib.analysis_pipeline.resolve_tool", lambda names: None)
    result = analyze_source(str(tmp_path), "js", str(tmp_path / "reports"))
    assert any("atom command not found" in e for e in result.errors)
    assert result.reachables_file is None


def test_analyze_source_reachables_failed(tmp_path, monkeypatch):
    fake = FakeAtom(tmp_path, fail_reachables=True)
    monkeypatch.setattr("atom_tools.lib.analysis_pipeline.run_command", fake)
    result = analyze_source(str(tmp_path), "js", str(tmp_path / "reports"), atom_cmd="atom")
    assert "Reachable slicing failed." in result.errors
