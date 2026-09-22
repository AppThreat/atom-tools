# Lesson 10: Ingest and the unified flow model

So far every command has worked on atom's own slices. This lesson widens the
aperture to the whole ecosystem: dosai, golem, rusi and kosi reports, plus atom,
all normalised into one document that every report-taking command accepts.

## The problem ingest solves

Each engine has its own vocabulary. dosai says `SinkCategory` and
`ReachableFromEntryPoint`, golem says `endpoints` and `callGraph`, atom says
`reachables` and tags them `sql`, `ssrf`, `framework-input`. If you run different
engines across a polyglot estate, comparing their findings means writing a
translator per engine, per schema version. `ingest` is that translator, written
once and tested against committed fixtures from every engine.

The unified flow model is one JSON document with a `flows` array. Every flow,
wherever it came from, carries the same fields: `source_category`,
`sink_category`, `severity`, `severity_source`, `taint_kinds`, `sanitized`,
`path_truncated`, `purls`, `nodes` with `role` markers, and the engine's own
record verbatim under `raw` as an escape hatch.

```text
    dosai dataflows ──┐
    golem analyze  ───┤
    rusi analyze   ───┼──>  atom-tools ingest  ──>  unified-flows.json
    kosi analyze   ───┤         (engine detected         │
    atom reachables ──┘          from the envelope)       ├──> stats
                                                          ├──> explain
                                                          ├──> attack-surface
                                                          ├──> drift
                                                          └──> crypto-reach (out of scope, says so)
```

## Ingesting one report

Start with the dosai report that sits in the cdxgen checkout (a real artefact of
a real run):

```console
$ atom-tools ingest -i ~/work/cdxgen/cdxgen/data-flow.slices.json -o unified-flows.json
Unified report with 74 flow(s) from 1 file(s) written to unified-flows.json.
```

One line of output, but the document is worth reading. The top level records
where everything came from:

```json
{
  "schema_version": "...",
  "engine": "mixed",
  "analysis_mode": "dataflows",
  "provenance": { "sources": [ { "engine": "dosai", "engine_version": "5.0.0.0", "file": ".../data-flow.slices.json", "generated_at": "2026-09-19T13:10:54.398773+00:00", "severity": "engine" } ] },
  "diagnostics": [ "Resolved 22 package purl(s) from paket.lock paket.lock.", "PURL version ambiguity for bootstrap: packages.config says 3.3.7; keeping 3.4.1.", "..." ],
  "endpoints": [],
  "packages": [],
  "flows": [ ... ]
}
```

And here is the first flow, trimmed to the load-bearing fields:

```json
{
  "id": "dfs1",
  "engine": "dosai",
  "severity": "error",
  "severity_source": "engine",
  "source_category": "message",
  "sink_category": "file",
  "taint_kinds": ["message"],
  "path_truncated": false,
  "sanitized": false,
  "purls": ["pkg:nuget/Microsoft.NETCore.App@2.1.0"],
  "nodes": [
    { "role": "source", "code": "request", "file": "nuget.exe", "line": 1, "function": ".ctor", "tags": ["message"] },
    { "role": "sink", "code": "System.IO.Path.Combine(string,string):string", "file": "nuget.exe", "line": 73, "function": "GetAssetsFilePath", "purl": "pkg:nuget/Microsoft.NETCore.App@2.1.0", "tags": ["file"] }
  ],
  "raw": { "Id": "dfs1", "Severity": "high", "SinkCategory": "file", "Summary": "Assembly IL data flows from dfn1556 to Combine argument 0.", "...": "..." }
}
```

Three things to notice. `severity_source` says `"engine"`, meaning dosai itself
emitted the severity and ingest passed it through; when an engine emits none, the
taxonomy derives one and the field says so. `path_truncated` is false here; when
an engine truncated a witness path, the flag is true, and downstream commands
render such flows differently rather than presenting them as complete. And `raw`
keeps the engine's original record untouched, so anything the model dropped is
still reachable.

## Mixing engines in one invocation

The interesting invocation takes several reports at once, engines mixed freely.
Feed it the cdxgen dosai report plus the committed golem (Go, ipsw) and rusi
(Rust, kafka microservices) fixtures:

```console
$ atom-tools ingest \
    -i "~/work/cdxgen/cdxgen/data-flow.slices.json,\
test/data/ecosystem/go-ipsw-golem.json,\
test/data/ecosystem/rust-microservices-kafka-rusi.json" \
    -o unified-mixed.json
Unified report with 476 flow(s) from 3 file(s) written to unified-mixed.json.
```

The provenance section now has three sources, and the flows are tagged by engine:

```json
{
  "provenance": {
    "sources": [
      { "engine": "dosai", "engine_version": "5.0.0.0", "analysis_mode": "dataflows", "...": "..." },
      { "engine": "golem", "engine_version": "3.2.0", "analysis_mode": "all", "callgraph_mode": "static", "dataflow_truncated": true, "...": "..." },
      { "engine": "rusi", "engine_version": "3.2.0", "analysis_mode": "security", "...": "..." }
    ]
  }
}
```

That `dataflow_truncated: true` on the golem source is the honesty habit again:
golem's dataflow witness is a capped sample, so every flow it contributed is
marked truncated, and any command rendering those flows will say so.

476 flows, three engines, one document. Every report-taking command now works on
the mixture exactly as it worked on a single-engine report.

## Emitting reachables instead

The unified model is atom-tools' own schema. Some tooling in the wider ecosystem
expects atom's reachables shape (the `{"reachables": [...]}` document), so ingest
can emit that instead:

```console
$ atom-tools ingest -i test/data/ecosystem/go-ipsw-golem.json --emit reachables -o golem-as-reachables.json
Reachables document with 397 flow group(s) written to golem-as-reachables.json.
```

The point of this form is that the atom-native commands, the ones you learned in
lessons 4 to 9, work on any engine's report through it. `stats` on the golem
emission, trimmed:

```console
$ atom-tools stats -i golem-as-reachables.json
Slice type: reachables
flow_groups: 397
flow_nodes: 2171
sources: 393
sinks: 160
unique_files: 66
top_files:
  /Users/prabhu/sandbox/ipsw/cmd/ipsw/cmd/diff.go: 585
  /Users/prabhu/sandbox/ipsw/api/server/routes/idev/idev.go: 376
  ...
purls:
  count: 21
  list: ['pkg:golang/cloud.google.com/go/auth', 'pkg:golang/crypto/x509', 'pkg:golang/github.com/blacktop/ipsw', ..., 'pkg:golang/net/http']
tags:
  framework-input: 393
  panic: 143
  http-input: 141
  configuration: 131
```

A Go report rendered by a command that was written for atom slices, with no
translation work on your side. The same trick works with `visualize`,
`convert -f sarif`, `check-reachable` and `filter`.

## Engine detection and the escape hatch

The engine is detected from the report envelope: dosai reports carry a `Tool` and
PascalCase tables, golem and rusi carry their schema URLs, atom slices have their
own shape. When a report is ambiguous or a new engine version changes its
envelope, `--engine` forces the interpretation, for example
`--engine rusi`. Use it as a precision tool, not a habit: forcing the wrong
engine on a report produces a confidently wrong document.

## What can go wrong

Ingest never invents severity, reach or sanitiser facts, but it does resolve
package purls from whatever the report carries, and where the report is
internally inconsistent it says so in `diagnostics` and picks a value. The dosai
report above produced diagnostics like "PURL version ambiguity for bootstrap:
packages.config says 3.3.7; keeping 3.4.1." Those strings are part of the
document; when a downstream number surprises you, read them first.

## Exercises

Run the kosi fixture through both emissions and compare what survives:

```console
$ atom-tools ingest -i test/data/ecosystem/kotlin-command-exec-kosi.json -o kosi-unified.json
$ atom-tools ingest -i test/data/ecosystem/kotlin-command-exec-kosi.json --emit reachables -o kosi-reachables.json
$ atom-tools stats -i kosi-reachables.json
```

Then feed the unified document of the three-engine mixture to `explain` and read
one flow from each engine. Lesson 14 does this in anger.

!!! note "Where the fixtures come from"
    Every `test/data/ecosystem/` fixture is a real engine run against a real
    repository, recorded in `test/data/ecosystem/PROVENANCE.md`. The summary is on
    the [fixtures reference](../reference/fixtures.md) page.
