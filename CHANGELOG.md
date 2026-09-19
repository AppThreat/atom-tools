# Changelog

All notable changes to atom-tools are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-19

atom-tools now reads the reports of the whole AppThreat analysis ecosystem —
atom slices (Java, JavaScript, Python, Ruby, ...), dosai (.NET), golem (Go) and
rusi (Rust) — not only atom slices. Six new analysis commands work on any of
the four, mixed freely, and the pre-existing commands keep their exact
behaviour on atom slices (pinned by digest, see
`test/data/ecosystem/PROVENANCE.md`).

### Added — new commands

- **ingest** — turn dosai, golem, rusi or atom reports into one unified flow
  document (`-f json`), or back into an atom-compatible reachables document
  with `--emit reachables` so every existing command can consume engine
  reports. Unified documents round-trip: every report-taking command also
  accepts a unified document as input.
- **attack-surface** — entry points grouped by exposure tier, with what each
  one reaches. Only dosai classifies authentication; every other engine is
  rendered as unknown-auth, stated as a gap rather than a verdict. Reach is
  computed by anchoring each endpoint handler in the engine's own call graph;
  "reaches nothing" and "not computed" always render differently.
- **drift** — compare two runs of the same engine (`--old`/`--new`) and report
  what changed: flows added, removed, moved (identity is built from analysis
  facts, so a flow whose location moved is reported as moved, never as added
  plus removed) and witness changes. Coverage gates: a run that analysed
  materially fewer files, or that the engine reported as truncated, trips
  `--fail-on` regardless of the selected keys.
- **graph** — call-graph chokepoints and blast radius: the nodes that sit on
  the most source→sink paths. Metrics: `chokepoints` (default), `dead-code`
  (with a root-set verdict), `centrality` (optionally joined with atom's own
  algorithm output via `--algorithms`), `scc`. Reads golem's own reachability
  depths and roots when present, and fills in only the rest as derived.
- **explain** — deterministic, template-driven narratives for every flow
  (text and markdown; every clause maps to a field, absence is stated, never
  filled with a plausible default), a token-budgeted `-f agent` JSON context
  for consuming agents, `--query` with dosai's compact grammar
  (`flows[sink_category=sql && severity=error]`), and `--mcp`: a read-only,
  file-scoped stdio MCP server exposing `atom.explain_flow`,
  `atom.attack_surface`, `atom.drift`, `atom.graph_hotspots` and `atom.query`.
  The server needs the new optional dependency: `pip install atom-tools[mcp]`.
- **crypto-reach** — join a report's crypto inventory to entry-point
  reachability: is this weak algorithm on a path an entry point reaches?
  The join runs per engine at the granularity the engine's evidence supports
  and every rendering states which one it is using (dosai record-level from
  the engine's own verdicts, rusi function-level, golem package-level at
  best). No cross-engine headline: three granularities do not sum.

### Added — existing commands

- **analyze** — drives the atom CLI for any language (reachables first, then
  usages with `--reuse-atom`), merges chunked output, computes stats and can
  extract OpenAPI endpoints and write SARIF. Long-running subprocesses honour
  `ATOM_TOOLS_SUBPROCESS_TIMEOUT` (default 3600 s) and surface timeouts as
  exit code 124 instead of hanging.
- **merge-slices** — merge atom's chunked reachable output
  (`reachables.json`, `reachables_1.json`, ...) or cross-project slices into
  one de-duplicated document. All reachables commands pick up sibling chunks
  automatically, and bare-array chunks are recognised on load.
- **convert -f sarif** — reachables to SARIF 2.1.0 with codeFlows, tag-driven
  rules and stable fingerprints (code, column and purls included, so GitHub
  does not merge distinct flows), ready for code-scanning upload.
- **stats** — slice analytics for usages, reachables, data-flow and parsedeps
  slices, with `--json` output. Engine reports carry an `analysis` block with
  the engine's own provenance, mode and truncation flag — a truncated run no
  longer reads as a complete one.
- **visualize** — rich console report plus a mermaid.js flowchart (`.mmd`) and
  an HTML page; optional `--mermaid-source` embeds mermaid locally for offline
  rendering; an optional cdxgen CycloneDX SBOM adds licenses and an
  "N of M SBOM components proven reachable" coverage stat.

### Changed

- The one behavioural change to existing commands: `ingest --emit reachables`
  makes `stats`, `visualize`, `convert -f sarif`, `check-reachable` and
  `filter` consume dosai/golem/rusi reports, via the atom-compatible
  reachables document `ingest` emits from them. These commands' own behaviour
  on atom slices is unchanged — verified byte-identical at every step and now
  pinned by digest (`test/test_atom_slice_invariance.py`).
- Engine categories map onto the shared tag taxonomy, so tag-driven consumers
  (stats sources/sinks, filter, SARIF rule derivation) see engine flows
  instead of zero. rusi's positional `param-N` categories stay unmapped on
  purpose: calling them framework-input would assert attacker control the
  engine never claimed.

### Fixed

- **convert** — output is now deterministic across runs: Python's per-process
  hash seed leaked set-iteration order into the document for every origin
  type (two different digests in five runs for `-t rb`); pinned by tests that
  convert under several `PYTHONHASHSEED` values in subprocesses. Ruby also no
  longer emits empty `{}` usage placeholders.
- **query-endpoints** — printed an empty listing for Go, Rust and Ruby slices
  (the usages annotation is attached at the operation level there, not the
  path item), and now accepts every origin type the converter supports.
- **check-reachable** — answered a confident False for every package in a
  golem report because versionless Go purls were dropped from the
  enumeration; purls are kept verbatim. A missing package option now says so
  instead of surfacing as a TypeError.
- **explain** — the agent document's token budget now counts itself and is
  asserted against the real serialization; `ingest --emit reachables` from a
  unified document no longer drops the endpoint table.
- **drift** — a dependency-cache path that matched no root is no longer
  rendered as relative (leading-`./`-only strip); repeated identical flows
  collapse to one line with a count in console/markdown (json keeps every
  record). Root alignment reads the separators the *engine* reported rather
  than the host's `os.sep`, so a report of POSIX paths diffed on Windows
  keeps its checkout root instead of rendering every file at full length.
- **graph** — golem diagnostics render the engine's messages instead of
  Python dict reprs, and the derived-depth count no longer includes external
  nodes the rows it describes exclude.
- **crypto-reach** — renders the fields dosai actually publishes (`use
  DES/RC2/RC4`, not `operation cop1`) and locates items by their recorded
  path, not the basename.
- **visualize** — labels carry full paths, package names and purls (they were
  truncated at 44 characters, cutting exactly the sink expression and the
  package coordinates), soft-wrapped across lines without splitting version
  segments; the help text no longer claims a self-contained HTML page.
- **all report-loading commands** — malformed JSON now reports the file and
  its role (`could not read the report x.json: Expecting value: line 5
  column 1 (char 41)`) instead of a bare character offset into a file that is
  never named; exit codes stay non-zero.
- **merge-slices** — stopped printing the merged result twice.
