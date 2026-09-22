# Lesson 4: Stats, triage and check-reachable

Two small commands that carry a disproportionate amount of daily work. `stats`
summarises any slice in one screen; `check-reachable` answers the narrow
yes-or-no question that most consumption of all this analysis reduces to.

## stats on every artefact you have

The stats command works on all five slice types: reachables, usages, data-flow,
parsedeps and semantics. You have seen its reachables and usages renderings on
the cdxgen artefacts in lesson 2. It also reads the dosai report sitting in the
cdxgen checkout, which is a data-flow style report:

```console
$ atom-tools stats -i ~/work/cdxgen/cdxgen/data-flow.slices.json
```

The rendering adapts to the slice type: flow group, node and source file counts
for reachables; object slices and external/internal call counts for usages;
node/edge/path counts for data-flow slices; module counts for parsedeps. The
common tail lists reachable package purls and the most common tags with their
frequencies, which is the triage view: what does this analysis touch, and what
kind of flows dominate.

In CI, take the machine-readable form and archive it next to the slice:

```console
$ atom-tools stats -i cdxgen-reports/cdxgen.reachables.json --json -o stats.json
$ python3 -m json.tool stats.json
{
    "flow_groups": 790,
    "flow_nodes": 30126,
    "purls": { "count": 0, "list": [] },
    "sinks": 315,
    "slice_type": "reachables",
    "sources": 639,
    "tags": {
        "framework-input": 645,
        "flow-summary": 564,
        "framework-output": 315,
        "exported": 166
    },
    "top_files": {
        "lib/stages/postgen/introspection/score.js": 15060,
        ...
    },
    "unique_files": 13
}
```

A useful CI pattern is to diff this JSON between runs; it is the cheapest
possible drift signal (lesson 11 does the same job properly, but this one works
across slice types and engines that drift does not).

## Reading the numbers honestly

Two cautions that come straight from the cdxgen run.

First, `unique_files: 13` does not mean atom read thirteen files. It means
thirteen files host flow groups that survived the source-to-sink filters. The
usages slice covers hundreds of files; the reachables slice is the subset where
a recognised source connects to a recognised sink. Counting files analysed is a
different metric, and the engines report it in their own statistics blocks.

Second, `purls count: 0` on this run while the juiceshop fixture (same command,
different project) reports 31. The purls on a reachables group come from the
engine resolving dependency boundaries as it builds flows. A babel-only
JavaScript run over a workspace without bundled dependencies leaves that join
empty, which propagates to the SBOM reachability number in lesson 7. Zero here
means "this run could not make that join", not "the project has no
dependencies"; the cdxgen SBOM in lesson 7 lists 7,813.

## check-reachable: the yes-or-no command

Everything in the previous lessons exists to support questions of the form "is
this specific thing used". The check-reachable command takes either a
`package:version` or a `filename:linenumber` and prints `True` or `False`.

On the cdxgen reachables, using a line that the stats output already told us
carries flows:

```console
$ atom-tools check-reachable -i cdxgen-reports/cdxgen.reachables.json -l lib/inventory/purl.js:62
True

$ atom-tools check-reachable -i cdxgen-reports/cdxgen.reachables.json -l lib/inventory/purl.js:90
False
```

A range works as an inclusive interval, so a mid-range line with flows is found
(this interval behaviour was repaired while writing this course; versions at
1.0.0 matched only the two endpoints of a range):

```console
$ atom-tools check-reachable -i cdxgen-reports/cdxgen.reachables.json -l lib/inventory/purl.js:60-90
True
```

The package form needs a slice that carries purls, so switch to the juiceshop
fixture for the canonical demonstration:

```console
$ atom-tools check-reachable -i test/data/chunked/js-juiceshop-reachables.json -p "@colors/colors:1.6.0"
True

$ atom-tools check-reachable -i test/data/chunked/js-juiceshop-reachables.json -p "@colors/colors:1.9.0"
False
```

Same package, different version, opposite answers: version 1.6.0 is on a
reachable path and 1.9.0 is not. That pair of lines is the entire point of the
reachability programme: an SBOM says both versions are present; only the slice
can say which one execution actually touches.

The command prints its answer and exits 0 either way, so scripts read stdout
rather than the exit code. For bulk questions, filter with a purl criterion
(lesson 5) or read the visualize report's package table (lesson 7) instead of
looping over this command.

## Exercises

Answer these with stats and check-reachable on the cdxgen artefacts: which file
would you read first to understand the introspection stage's data exposure, and
does line 1526 of `lib/cli/bomAssembly.js` sit on a reachable flow? The console
report in lesson 7 labels that flow's source `context:1526`; check which file
the slice anchors it to before you answer, because flows cross files and the
label alone does not say which one.
