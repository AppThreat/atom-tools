"""Tests for the slice statistics module."""

from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.stats import SliceStats


def _stats(path):
    atom_slice = AtomSlice(path)
    return SliceStats(atom_slice.content, atom_slice.slice_type, path).to_dict()


def test_slice_type_detection():
    assert _stats("test/data/py-data-flow.json")["slice_type"] == "data-flow"
    assert _stats("test/data/py-parsedeps.json")["slice_type"] == "parsedeps"
    assert _stats("test/data/js-juiceshop-reachables.json")["slice_type"] == "reachables"
    assert _stats("test/data/js-juiceshop-usages.json")["slice_type"] == "usages"


def test_reachables_stats():
    stats = _stats("test/data/js-juiceshop-reachables.json")
    assert stats["flow_groups"] == 2439
    assert stats["flow_nodes"] > 0
    assert stats["unique_files"] > 0
    assert stats["sources"] > 0
    assert stats["sinks"] > 0
    assert stats["purls"]["count"] == 43
    assert "pkg:npm/express@4.18.2" in stats["purls"]["list"]
    assert stats["top_files"]
    tags = " ".join(stats["tags"])
    assert "framework-input" in tags or "framework-output" in tags


def test_reachables_stats_chunked():
    stats = _stats("test/data/chunked/js-juiceshop-reachables.json")
    first = _stats("test/data/chunked/js-juiceshop-reachables_1.json")
    assert stats["flow_groups"] > first["flow_groups"]


def test_usages_stats():
    stats = _stats("test/data/js-juiceshop-usages.json")
    assert stats["object_slices"] > 0
    assert stats["usages"] > 0
    assert stats["calls"]["external"] + stats["calls"]["internal"] > 0
    assert stats["top_files"]


def test_dataflow_stats():
    stats = _stats("test/data/py-data-flow.json")
    assert stats["nodes"] == 4
    assert stats["edges"] == 4
    assert stats["paths"] == 2
    assert stats["edge_labels"]["REACHING_DEF"] == 2


def test_parsedeps_stats():
    stats = _stats("test/data/py-parsedeps.json")
    assert stats["modules"] == 3
    assert stats["imported_symbols"] == 6
    assert "flask" in stats["top_modules"]
