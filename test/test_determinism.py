"""Conversion output must be reproducible.

Python hashes strings with a per-process random seed, so any set or dict of
strings whose iteration order reaches the output makes the same slice convert
to a different document on every run. `convert -t rb` produced four distinct
digests in five runs before this was fixed, which makes the output impossible
to diff in CI or to check into a repository.

These tests run the conversion in *subprocesses with different PYTHONHASHSEED
values*, because a single pytest process shares one seed and would pass no
matter how much hash-order leaked through.
"""

import hashlib
import json
import os
import subprocess
import sys

import pytest

# One real fixture per converter dispatch path in convert_usages.
FIXTURES = [
    ("java", "test/data/java-piggymetrics-usages.json"),
    ("js", "test/data/js-juiceshop-usages.json"),
    ("ts", "test/data/ts-custom-router-usages.json"),
    ("py", "test/data/py-breakable-flask-usages.json"),
    ("rb", "test/data/rb-railsgoat-usages.json"),
    ("rs", "test/data/rust-axum-sample-rusi.json"),
    ("go", "test/data/go-gin-sample-golem.json"),
]

# Seeds chosen because they actually discriminate: with the parameter-type set
# left unsorted, seeds 0/1/3 agree with each other and 2/6 disagree with them,
# so a seed list that happened to miss 2 and 6 passed a genuinely broken build.
# "random" is included so CI also samples seeds nobody picked.
SEEDS = ["0", "1", "2", "3", "6", "random"]

CONVERT = (
    "import json, sys;"
    "sys.path.insert(0, '.');"
    "from atom_tools.lib.converter import OpenAPI;"
    "print(json.dumps(OpenAPI('openapi3.1.0', sys.argv[1], sys.argv[2])"
    ".endpoints_to_openapi(''), sort_keys=True))"
)


def convert_under_seed(origin_type: str, fixture: str, seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    result = subprocess.run(
        [sys.executable, "-c", CONVERT, origin_type, fixture],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout


@pytest.mark.parametrize(("origin_type", "fixture"), FIXTURES)
def test_conversion_is_identical_under_different_hash_seeds(origin_type, fixture):
    """
    The same slice must convert to the same document whatever the hash seed.

    `sort_keys=True` in the harness removes dict *key* ordering from the
    comparison, so what this actually pins is list ordering -- line numbers,
    parameters, endpoints, resolved methods -- which is where the leak was.
    """
    outputs = {seed: convert_under_seed(origin_type, fixture, seed) for seed in SEEDS}
    digests = {hashlib.md5(v.encode()).hexdigest() for v in outputs.values()}
    if len(digests) > 1:
        baseline = json.loads(outputs[SEEDS[0]])
        for seed in SEEDS[1:]:
            other = json.loads(outputs[seed])
            differing = [k for k in baseline["paths"] if baseline["paths"][k] != other["paths"].get(k)]
            if differing:
                pytest.fail(
                    f"{origin_type} conversion differs between PYTHONHASHSEED"
                    f" {SEEDS[0]} and {seed}; first differing path {differing[0]!r}:\n"
                    f"  {json.dumps(baseline['paths'][differing[0]])}\n"
                    f"  {json.dumps(other['paths'][differing[0]])}"
                )
    assert len(digests) == 1


def test_line_numbers_are_sorted_and_unique():
    """Line-number lists are gathered from several usages of one endpoint, so
    their arrival order is traversal noise. Sorting them is what makes the
    output stable, and it is also what a reader wants."""
    document = json.loads(convert_under_seed("js", "test/data/js-juiceshop-usages.json", "7"))
    seen = 0
    for item in document["paths"].values():
        for calls in (item.get("x-atom-usages") or {}).get("call", {}).values():
            assert calls == sorted(set(calls))
            seen += 1
    assert seen, "the fixture should carry x-atom-usages call lines"


def test_ruby_usages_carry_no_empty_placeholders():
    """Ruby merged usages through a set of JSON strings, which both randomised
    the order and preserved the `{}` produced by wrapping a missing existing
    method. An empty usage entry is a placeholder, not a usage."""
    document = json.loads(convert_under_seed("rb", "test/data/rb-railsgoat-usages.json", "7"))
    for item in document["paths"].values():
        for operation in item.values():
            if not isinstance(operation, dict):
                continue
            usages = operation.get("x-atom-usages")
            if isinstance(usages, list):
                assert all(u for u in usages), "empty x-atom-usages entry survived"


# --- explain: reproducible narrative and agent context -------------------------
#
# explain's headline property is the same as convert's — "reproducible, citable
# and safe to put in CI" — and its renderers touch far more sets (entry-point
# joins, package and file rollups, tag lists), so hash-order leaks would be
# strictly easier to introduce here. Same harness, same seeds.


EXPLAIN_FIXTURES = [
    "test/data/ecosystem/go-ipsw-golem.json",  # 397 flows: every list bites
    "test/data/ecosystem/dotnet-eshoponweb-dosai-dataflows.json",
    "test/data/java-petclinic-reachables.json",
]

EXPLAIN_RENDERERS = {
    "text": (
        "text = render_text(ctx, max_flows=10)"
    ),
    "agent": (
        "text = json.dumps(build_agent_document(ctx), indent=2, sort_keys=True)"
    ),
}

EXPLAIN = (
    "import json, sys;"
    "sys.path.insert(0, '.');"
    "from atom_tools.lib.adapters import parse_report;"
    "from atom_tools.lib.attack_surface import SurfaceInput;"
    "from atom_tools.lib.explain import build_context, build_agent_document, render_text;"
    "raw = json.load(open(sys.argv[1]));"
    "ctx = build_context([SurfaceInput(report=parse_report(raw, source_file=sys.argv[1]),"
    " raw=raw, path=sys.argv[1])]);"
    "{render};"
    "print(text)"
)


def explain_under_seed(fixture: str, renderer: str, seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    result = subprocess.run(
        [sys.executable, "-c", EXPLAIN.format(render=EXPLAIN_RENDERERS[renderer]), fixture],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout


@pytest.mark.parametrize("fixture", EXPLAIN_FIXTURES)
@pytest.mark.parametrize(("renderer"), sorted(EXPLAIN_RENDERERS))
def test_explain_is_identical_under_different_hash_seeds(fixture, renderer):
    """The narrative and the agent JSON must not depend on the hash seed.

    Golden files inside one pytest process share a single seed and cannot
    catch this; only subprocesses with forced seeds can.
    """
    outputs = {
        seed: explain_under_seed(fixture, renderer, seed) for seed in SEEDS
    }
    digests = {hashlib.md5(v.encode()).hexdigest() for v in outputs.values()}
    assert len(digests) == 1, (
        f"{renderer} rendering of {fixture} varies with PYTHONHASHSEED"
    )


# --- crypto-reach: the join's rollups are set-driven ----------------------------
#
# crypto-reach folds items through per-package and per-endpoint dicts built
# from sets (flow node packages, closure membership), so it has the same
# exposure as explain. The json document is the widest surface; the console
# rendering re-derives its ordering from it.

CRYPTO_REACH_FIXTURES = [
    "test/data/ecosystem/go-ipsw-golem-roots.json",  # 799 items, 46 packages
    "test/data/ecosystem/dotnet-eshoponweb-dosai-crypto.json",
    "test/data/ecosystem/rust-microservices-kafka-rusi.json",
]

CRYPTO_REACH_RENDERERS = {
    "json": "text = json.dumps(compute_crypto_reach(inputs), indent=2, sort_keys=True)",
    "console": "text = '\\n'.join(render_console(compute_crypto_reach(inputs), max_entries=40))",
}

CRYPTO_REACH = (
    "import json, sys;"
    "sys.path.insert(0, '.');"
    "from atom_tools.lib.adapters import parse_report;"
    "from atom_tools.lib.attack_surface import SurfaceInput;"
    "from atom_tools.lib.crypto_reach import compute_crypto_reach, render_console;"
    "raw = json.load(open(sys.argv[1]));"
    "inputs = [SurfaceInput(report=parse_report(raw, source_file=sys.argv[1]),"
    " raw=raw, path=sys.argv[1])];"
    "{render};"
    "print(text)"
)


def crypto_reach_under_seed(fixture: str, renderer: str, seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    result = subprocess.run(
        [sys.executable, "-c", CRYPTO_REACH.format(render=CRYPTO_REACH_RENDERERS[renderer]), fixture],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout


@pytest.mark.parametrize("fixture", CRYPTO_REACH_FIXTURES)
@pytest.mark.parametrize(("renderer"), sorted(CRYPTO_REACH_RENDERERS))
def test_crypto_reach_is_identical_under_different_hash_seeds(fixture, renderer):
    """The join document and its console rendering must not depend on the
    hash seed; per-package rollups and closure membership checks are the
    set-driven parts that would leak."""
    outputs = {
        seed: crypto_reach_under_seed(fixture, renderer, seed) for seed in SEEDS
    }
    digests = {hashlib.md5(v.encode()).hexdigest() for v in outputs.values()}
    assert len(digests) == 1, (
        f"{renderer} rendering of {fixture} varies with PYTHONHASHSEED"
    )


# --- the ecosystem commands' renderings: same exposure as explain ----------------
#
# attack-surface, drift and graph fold sets into their documents (closure
# membership, package rollups, ranking ties) and ingest serialises the whole
# unified model; a hash-order leak would make every golden here flaky in CI
# while passing in the single-seed pytest process. crypto-reach is covered
# above. One fixture per command is enough to exercise the shared serializer;
# the golem fixture is the richest (397 flows, 57 endpoints, a call graph).

ECOSYSTEM_RENDERERS = {
    "attack-surface-console": (
        "from atom_tools.lib.attack_surface import compute_attack_surface, render_console;"
        "doc = compute_attack_surface(inputs());"
        "text = '\\n'.join(render_console(doc))"
    ),
    "attack-surface-json": (
        "from atom_tools.lib.attack_surface import compute_attack_surface;"
        "text = json.dumps(compute_attack_surface(inputs()), indent=4, sort_keys=True)"
    ),
    "drift-console": (
        "from atom_tools.lib.drift import compute_drift, render_console;"
        "old = parse_report(json.load(open('test/data/ecosystem/go-ipsw-golem-baseline.json')), source_file='old');"
        "new = parse_report(json.load(open('test/data/ecosystem/go-ipsw-golem.json')), source_file='new');"
        "text = '\\n'.join(render_console(compute_drift(old, new)))"
    ),
    "drift-json": (
        "from atom_tools.lib.drift import compute_drift;"
        "old = parse_report(json.load(open('test/data/ecosystem/go-ipsw-golem-baseline.json')), source_file='old');"
        "new = parse_report(json.load(open('test/data/ecosystem/go-ipsw-golem.json')), source_file='new');"
        "text = json.dumps(compute_drift(old, new), indent=4, sort_keys=True)"
    ),
    "graph-console": (
        "from atom_tools.lib.callgraph import compute_graph_document, load_call_graph;"
        "raw = json.load(open(sys.argv[1]));"
        "g = load_call_graph(sys.argv[1], raw);"
        "rep = parse_report(raw, source_file=sys.argv[1]);"
        "s, k = flow_functions(rep);"
        "doc = compute_graph_document([g], 'chokepoints', flow_sources=s, flow_sinks=k,"
        " endpoints_by_source={sys.argv[1]: rep.endpoints});"
        "text = '\\n'.join(render_console(doc))"
    ),
    "graph-json": (
        "from atom_tools.lib.callgraph import compute_graph_document, load_call_graph;"
        "raw = json.load(open(sys.argv[1]));"
        "g = load_call_graph(sys.argv[1], raw);"
        "rep = parse_report(raw, source_file=sys.argv[1]);"
        "s, k = flow_functions(rep);"
        "doc = compute_graph_document([g], 'chokepoints', flow_sources=s, flow_sinks=k,"
        " endpoints_by_source={sys.argv[1]: rep.endpoints});"
        "text = json.dumps(doc, indent=4, sort_keys=True)"
    ),
    "ingest-unified": (
        "text = json.dumps(parse_report(raw, source_file=sys.argv[1]).to_dict(),"
        " indent=4, sort_keys=True)"
    ),
}

ECOSYSTEM = (
    "import json, sys;"
    "sys.path.insert(0, '.');"
    "from atom_tools.lib.adapters import parse_report;"
    "from atom_tools.lib.attack_surface import SurfaceInput;"
    "from atom_tools.lib.callgraph import flow_functions, render_console;"
    "raw = json.load(open(sys.argv[1]));"
    "inputs = lambda: [SurfaceInput(report=parse_report(raw, source_file=sys.argv[1]),"
    " raw=raw, path=sys.argv[1])];"
    "{render};"
    "print(text)"
)

# ingest exercises the unified serialiser on a second engine shape (rusi's
# snake_case vendor document) where the flow fields come from different keys.
ECOSYSTEM_FIXTURES = {
    "attack-surface-console": "test/data/ecosystem/go-ipsw-golem.json",
    "attack-surface-json": "test/data/ecosystem/go-ipsw-golem.json",
    "drift-console": "test/data/ecosystem/go-ipsw-golem.json",
    "drift-json": "test/data/ecosystem/go-ipsw-golem.json",
    "graph-console": "test/data/ecosystem/go-ipsw-golem.json",
    "graph-json": "test/data/ecosystem/go-ipsw-golem.json",
    "ingest-unified": "test/data/ecosystem/rust-microservices-kafka-rusi.json",
}


def ecosystem_under_seed(renderer: str, seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            ECOSYSTEM.format(render=ECOSYSTEM_RENDERERS[renderer]),
            ECOSYSTEM_FIXTURES[renderer],
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout


@pytest.mark.parametrize(("renderer"), sorted(ECOSYSTEM_RENDERERS))
def test_ecosystem_renderings_are_identical_under_different_hash_seeds(renderer):
    """The documents and console renderings the golden files pin must not
    depend on the hash seed; the goldens alone cannot prove that."""
    outputs = {seed: ecosystem_under_seed(renderer, seed) for seed in SEEDS}
    digests = {hashlib.md5(v.encode()).hexdigest() for v in outputs.values()}
    assert len(digests) == 1, f"{renderer} rendering varies with PYTHONHASHSEED"
