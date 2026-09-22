# Command reference

One row per command, then the full option list for each. Options shown are the
command-specific ones; every command also accepts the global cleo options
(`-h/--help`, `-q/--quiet`, `-V/--version`, `--ansi`, `--no-ansi`,
`-n/--no-interaction`, `-v|vv|vvv`). Run `atom-tools help <command>` to see this
live.

| command | reads | writes | lesson |
|---|---|---|---|
| `analyze` | source tree (drives atom) | reachables, usages, stats, openapi, sarif | [2](../lessons/02-analyze.md) |
| `stats` | any slice | text or json summary | [4](../lessons/04-stats.md) |
| `check-reachable` | reachables | console verdict | [4](../lessons/04-stats.md) |
| `filter` | usages or reachables | filtered slice, or chained command output | [5](../lessons/05-filter.md) |
| `merge-slices` | reachables (chunks, globs) | merged, de-duplicated slice | [6](../lessons/06-merge-validate.md) |
| `validate-lines` | usages or reachables | text and json accuracy report | [6](../lessons/06-merge-validate.md) |
| `visualize` | reachables (+ optional SBOM) | console report, mermaid, html | [7](../lessons/07-visualize.md) |
| `query-endpoints` | usages | console endpoint list | [8](../lessons/08-endpoints.md) |
| `convert` | usages or reachables | openapi or sarif | [8](../lessons/08-endpoints.md), [9](../lessons/09-sarif.md) |
| `ingest` | any engine report | unified flow model or reachables | [10](../lessons/10-ingest.md) |
| `attack-surface` | any engine report | console, json, html | [11](../lessons/11-attack-surface.md) |
| `drift` | two reports, same engine | console, markdown or json delta | [12](../lessons/12-drift.md) |
| `graph` | reports with call graphs | console, json, mermaid, graphml, gexf | [13](../lessons/13-graph.md) |
| `explain` | any engine report | text, markdown, agent json, MCP server | [14](../lessons/14-explain.md) |
| `crypto-reach` | dosai crypto, golem, rusi | text or json triage | [15](../lessons/15-crypto-reach.md) |
| `apk-analysis` | apk, apkm or aab (drives blint and atom) | SBOM, slices, consolidated report | README |

## analyze

```text
  -l, --language=LANGUAGE  atom language code: java, python, jssrc, jssrc/ts, c, ruby, php, jar, apk, scala, ...
  -i, --input=INPUT        Path to the source file or directory to analyse. [default: "."]
  -o, --output=OUTPUT      Directory to write reports to. [default: "reports"]
      --atom-cmd=ATOM-CMD  Path to the atom command; resolved from PATH when omitted.
      --extract-endpoints  Extract an OpenAPI document from the usages slice.
      --sarif              Export the reachable slices to a SARIF document.
      --no-usages          Skip the usages slice; only reachables are generated.
```

## stats

```text
  -i, --input-slice=INPUT-SLICE  Slice file. Usages, reachables, data-flow, parsedeps and semantics slices are supported.
      --json                     Write the summary as a JSON document instead of printing text.
  -o, --output-file=OUTPUT-FILE  Output file used together with --json. [default: "slice-stats.json"]
```

## check-reachable

```text
  -i, --input-slice=INPUT-SLICE  Slice file
  -p, --pkg=PKG                  Package to search for in the format of <package_name>:<version>
  -l, --location=LOCATION        Filename with line number to search for in the format of <filename>:<linenumber>
```

`check-reachable` prints `True` or `False` on stdout. Scripts should read that
value rather than the exit code, which is always 0.

## filter

```text
  -i, --input-slice=INPUT-SLICE          Slice file to filter.
  -c, --criteria=CRITERIA                Filter based on an attribute of the slice. May be a Python regular expression.
  -p, --package-version=PACKAGE-VERSION  Filter a reachables slice based on a package name and version in format package:version. May include multiple separated by a comma.
  -o, --outfile=OUTFILE                  File to re-export filtered slice to.
  -f, --fuzz=FUZZ                        Minimum percentage to match with the given criteria INSTEAD of using a regex. Must be a number between 0 and 100.
  -e, --execute=EXECUTE                  Command to execute after filtering. [default: "export"]
```

## merge-slices

```text
  -i, --input-slice=INPUT-SLICE  Slice file, glob pattern, or comma separated list. Sibling chunks such as reachables_1.json are picked up automatically.
  -o, --output-file=OUTPUT-FILE  Output file [default: "merged.reachables.slices.json"]
      --no-dedupe                Keep duplicate flow groups instead of dropping them.
```

## validate-lines

```text
  -i, --input-slice=INPUT-SLICE  Slice file to validate.
  -t, --type=TYPE                Origin type of source on which the atom slice was generated. [default: "java"]
  -d, --base-path=BASE-PATH      This should be the same path that was used by atom when the slice was generated.
  -l, --interval=INTERVAL        Try matching within a range. Ex. slice has line number 567, with interval of 5, we check lines 562-572. Use 0 for exact matching. [default: "5"]
  -r, --report=REPORT            Output summary to file. Defaults to output.txt in the current directory. [default: "output.txt"]
  -j, --export-json=EXPORT-JSON  JSON report file to store invalid lines. Include valid lines as well using -v flag.
```

## visualize

```text
  -i, --input-slice=INPUT-SLICE        Reachable slice file, glob pattern, or comma separated list. Sibling chunks such as reachables_1.json are picked up automatically.
  -o, --output=OUTPUT                  Base path for the .mmd and .html outputs. [default: "reachables-viz"]
  -b, --bom=BOM                        Optional CycloneDX SBOM (e.g. from cdxgen) used to enrich package nodes with licenses and report reachability coverage.
  -f, --format=FORMAT                  Renderers to run: all, console, mermaid or html. [default: "all"]
      --max-flows=MAX-FLOWS            Maximum number of flows drawn in the mermaid diagram. The most interesting flows (high risk sinks first) are kept. [default: "60"]
      --label-wrap=LABEL-WRAP          Soft width at which long diagram labels (relative paths, purls, sink expressions) are wrapped across lines. Labels are never truncated; pass 0 to keep each on a single line. [default: "48"]
      --mermaid-source=MERMAID-SOURCE  Path to a local mermaid.min.js to embed in the HTML page so it renders offline.
```

## query-endpoints

```text
  -i, --input-slice=INPUT-SLICE    Slice file
  -t, --type=TYPE                  Origin type of source on which the atom slice was generated. [default: "java"]
  -f, --filter-lines=FILTER-LINES  Filter endpoints by line number or range.
  -s, --sparse                     Only display names; do not include path and line numbers.
```

## convert

```text
  -f, --format=FORMAT                    Destination format [default: "openapi3.1.0"]
  -i, --input-slice=INPUT-SLICE          Usages slice file [default: "usages.slices.json"]
  -e, --semantics-slice=SEMANTICS-SLICE  Semantics slice file [default: "semantics.slices.json"]
  -t, --type=TYPE                        Origin type. Supported: go, golang, jar, java, javascript, js, kotlin, kt, py, python, rb, rs, ruby, rust, sbt, scala, ts, typescript [default: "java"]
  -o, --output-file=OUTPUT-FILE          Output file [default: "openapi.json"]
  -s, --server=SERVER                    The server url to be included in the server object.
```

## ingest

```text
  -i, --input-slice=INPUT-SLICE  Report file(s): dosai dataflows/methods, golem analyze, rusi analyze or atom reachables. Comma separated lists and globs are supported, and engines can be mixed freely.
  -o, --output-file=OUTPUT-FILE  Output file for the unified (or reachables) document. [default: "unified-flows.json"]
      --emit=EMIT                Output form: 'unified' (the model document, default) or 'reachables' (an atom-compatible document that stats, visualize, convert, check-reachable and filter already consume). [default: "unified"]
      --engine=ENGINE            Force the producing engine (atom, dosai, golem, rusi, kosi) instead of detecting it from the report envelope.
```

## attack-surface

```text
  -i, --input-slice=INPUT-SLICE    Report file(s): dosai dataflows/methods, golem analyze, rusi analyze, atom reachables or atom usages slices. Comma separated lists and globs are supported, and engines can be mixed freely.
  -o, --output-file=OUTPUT-FILE    Output path: the json document with -f json, or the base path for the .mmd and .html files with -f html. [default: "attack-surface"]
  -f, --format=FORMAT              Output format(s), comma separated: json, console, html. [default: "console"]
      --min-exposure=MIN-EXPOSURE  Only report tiers at least this exposed. One of the documented tier names (anonymous-http is the most exposed). Tiers whose authentication is unknown never match the filter and are counted in a note instead.
      --max-entries=MAX-ENTRIES    Maximum number of entry points listed in the console and diagram renderings. The json output always carries every entry point. [default: "200"]
```

## drift

```text
      --old=OLD                  Baseline report: dosai dataflows, golem analyze, rusi or kosi analyze or atom reachables.
      --new=NEW                  Current report, from the same engine as --old.
  -o, --output-file=OUTPUT-FILE  Output file for the drift document (json format only). [default: "drift.json"]
  -f, --format=FORMAT            Output format: json, console, markdown. [default: "console"]
      --fail-on=FAIL-ON          Comma separated gate keys; exit code 2 when any trips. Known: new-high, new-medium, new-anonymous-endpoint, new-package, new-sink-category, new-entrypoint. A coverage regression trips the gate regardless of this option.
      --engine=ENGINE            Force the producing engine for both inputs instead of detecting it from the report envelope.
```

## graph

```text
  -i, --input-slice=INPUT-SLICE                        Report file(s) carrying a call graph: golem analyze, rusi analyze, dosai methods, or atom export --format graphml. Comma separated lists and globs are supported, and engines can be mixed freely.
      --metric=METRIC                                  One of: chokepoints, centrality, blast-radius, entry-depth, dead-code, cycles. Default: chokepoints.
      --blast-radius=BLAST-RADIUS                      Node to measure the blast radius of (a call-graph node id or a unique function name); selects the blast-radius metric.
      --min-confidence=MIN-CONFIDENCE                  Keep only edges at or above this confidence tier: exact, external, candidate, unknown.
      --include-external                               Include external (out-of-workspace) nodes in rankings. Off by default.
      --algorithms=ALGORITHMS                          atom 'algorithms' JSON output(s) (centrality and/or scc) to join verbatim; only meaningful for atom graphml inputs.
      --top=TOP                                        Ranked entries shown in the console and diagram renderings. The json output always carries every entry. [default: "15"]
      --max-chokepoint-sources=MAX-CHOKEPOINT-SOURCES  Cap on the source nodes whose paths the chokepoint metric enumerates. When the cap binds the output says so and the scores are a lower bound. [default: "64"]
  -f, --format=FORMAT                                  Output format(s), comma separated: json, console, mermaid. [default: "console"]
  -o, --output-file=OUTPUT-FILE                        Output path for the json document, the .mmd diagram, or the base path for --export graphml/gexf. [default: "call-graph"]
      --export=EXPORT                                  Export the unified graph(s) as: graphml, gexf.
```

## explain

```text
  -i, --input-slice=INPUT-SLICE  Report file(s): dosai dataflows/methods, golem analyze, rusi analyze, atom reachables or a unified document from ingest. Comma separated lists and globs are supported.
  -o, --output-file=OUTPUT-FILE  Write the rendering here instead of the console (the natural home for -f agent and -f markdown). [default: ""]
  -f, --format=FORMAT            Output format: text, markdown, agent. [default: "text"]
      --flow=FLOW                Explain one flow by its exact id (text and markdown formats).
      --package=PACKAGE          Explain the flows whose purls contain this string (case-insensitive substring; text and markdown formats).
      --file=FILE                Explain the flows with any node in this file (suffix match on normalised path separators; text and markdown formats).
      --query=QUERY              dosai's compact query grammar over the model: 'flows[sink_category=sql && severity=error]', with 'sort by prop [desc]' and 'count' postfixes. Collections are flows, endpoints, packages; a flow also exposes dotted source./sink. paths.
      --max-flows=MAX-FLOWS      Maximum flow narratives listed in text and markdown renderings. [default: "10"]
      --max-tokens=MAX-TOKENS    Token budget for -f agent, counted as characters/4 of the serialized JSON. [default: "4000"]
      --engine=ENGINE            Force the producing engine (atom, dosai, golem, rusi, kosi) instead of detecting it from the report envelope.
      --old=OLD                  With --mcp only: baseline report for the atom.drift tool, loaded at startup (tools never touch the filesystem).
      --mcp                      Run a read-only stdio MCP server over the loaded report.
```

## crypto-reach

```text
  -i, --input-slice=INPUT-SLICE  Report file(s): dosai crypto, golem analyze (--dataflow crypto|all), rusi analyze, or mixed. Atom slices and unified documents carry no crypto section and are reported as out of scope. Comma separated lists and globs are supported.
  -f, --format=FORMAT            Output format: text, json. [default: "text"]
  -o, --output-file=OUTPUT-FILE  Write the output here instead of the console. [default: ""]
      --weak-only                Keep only the triage population: weak/legacy-strength items and findings that are not literal-material inventory.
      --max-entries=MAX-ENTRIES  Maximum items listed in the text rendering. [default: "40"]
```

## Exit codes

Most commands exit 0 on success and 1 on failure. Two commands use extra codes
worth memorising. `check-reachable` exits 1 when there are no hits, which is a
normal answer, not an error. `drift` exits 2 when a gate trips, so a CI script
can distinguish "the diff tool broke" (1) from "the diff found risk" (2).
