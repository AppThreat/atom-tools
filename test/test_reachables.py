"""Tests for chunked reachable slice loading and merging."""

import json
import shutil

from atom_tools.lib.reachables import (
    expand_inputs,
    flow_fingerprint,
    load_reachables,
    parse_reachable_file,
    sibling_chunks,
)
from atom_tools.lib.slices import AtomSlice

CHUNKED = "test/data/chunked/js-juiceshop-reachables"
PETCLINIC = "test/data/java-petclinic-reachables.json"
JUICESHOP = "test/data/js-juiceshop-reachables.json"


def test_parse_bare_array_chunk():
    entries = parse_reachable_file(f"{CHUNKED}.json")
    assert entries and isinstance(entries, list)
    assert "flows" in entries[0] and "purls" in entries[0]


def test_parse_wrapped_document():
    entries = parse_reachable_file(JUICESHOP)
    assert len(entries) == 2439


def test_sibling_chunk_discovery():
    chunks = sibling_chunks(f"{CHUNKED}.json")
    assert chunks == [f"{CHUNKED}_1.json", f"{CHUNKED}_2.json"]


def test_sibling_chunks_ignores_foreign_files():
    # A file without numbered siblings has no chunks.
    assert sibling_chunks(JUICESHOP) == []
    # Files that merely share a prefix must not be picked up.
    assert sibling_chunks("test/data/py-parsedeps.json") == []


def test_load_reachables_merges_chunks():
    # The three chunk fixtures hold distinct real entries (20 each).
    merged = load_reachables(f"{CHUNKED}.json")
    assert len(merged["reachables"]) == 60


def test_load_reachables_no_dedupe():
    merged = load_reachables(f"{CHUNKED}.json", dedupe=False)
    assert len(merged["reachables"]) == 60


def test_load_reachables_dedupes_across_files(tmp_path):
    # Duplicate inputs are a runtime artefact (reruns, copied reports), so the
    # duplicate is created here instead of committing one to git.
    duplicate = tmp_path / "copy.json"
    shutil.copy(f"{CHUNKED}_1.json", duplicate)
    merged = load_reachables(f"{duplicate},{CHUNKED}.json")
    assert len(merged["reachables"]) == 60
    without_dedupe = load_reachables(f"{duplicate},{CHUNKED}.json", dedupe=False)
    assert len(without_dedupe["reachables"]) == 80


def test_load_reachables_glob_and_comma_inputs():
    by_glob = load_reachables(f"{CHUNKED}_*.json")
    assert len(by_glob["reachables"]) == 40
    by_comma = load_reachables(f"{CHUNKED}_1.json,{CHUNKED}_2.json")
    assert len(by_comma["reachables"]) == 40


def test_load_reachables_cross_project_merge():
    # petclinic is a bare array from the latest atom; juiceshop is the older
    # wrapped format. A polyglot merge keeps both intact.
    merged = load_reachables(f"{PETCLINIC},{JUICESHOP}")
    assert len(merged["reachables"]) == 163 + 2439


def test_expand_inputs_missing_pattern():
    assert expand_inputs("test/data/does-not-exist-*.json") == []


def test_flow_fingerprint_distinguishes_entries():
    entries = parse_reachable_file(f"{CHUNKED}.json")
    assert len({flow_fingerprint(e) for e in entries}) == len(entries)


def test_atomslice_sees_merged_chunks():
    # AtomSlice transparently folds sibling chunks in for reachables slices.
    with open(f"{CHUNKED}.json") as f:
        base_count = len(json.load(f))
    slice_obj = AtomSlice(f"{CHUNKED}.json")
    assert slice_obj.slice_type == "reachables"
    assert len(slice_obj.content["reachables"]) > base_count


def test_merge_roundtrip_is_loadable(tmp_path):
    merged = load_reachables(f"{CHUNKED}.json")
    out = tmp_path / "merged.json"
    out.write_text(json.dumps(merged))
    reloaded = parse_reachable_file(out)
    assert len(reloaded) == len(merged["reachables"])
