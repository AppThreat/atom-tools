# Provenance — real ecosystem engine fixtures

Every file in this directory was produced by running the real engine against the
real target repository, on this machine, on **2026-09-18** (the atom graph
fixtures and the crypto-reach additions on **2026-09-19**; the kosi fixtures on
**2026-09-19**). Nothing here is hand-written, hand-edited or duplicated. Where
a full report was too large to commit, the fixture is a **contiguous slice of
real records** with the sibling tables filtered to the ids those records
reference (so id joins stay resolvable); exactly what was trimmed is recorded
per fixture below, and the md5/size of the original untrimmed report is kept
for comparison. The trimming scripts preserved emitted record order and never
touched field values.

If a value in these files looks wrong, it is a finding about the engine — do not
"fix" the JSON.

## Environment

| what | value |
|---|---|
| go | go1.27.1 darwin/arm64 |
| cargo / rustc | cargo 1.98.0 (797e8a9bc 2026-08-05) / rustc 1.98.0 (88d9e12ae 2026-08-18) |
| dotnet | 11.0.100-rc.1.26425.128 |
| node | v26.8.2 |
| jdk (kosi resolved backend) | 21.0.7-tem (`~/.sdkman/candidates/java/21.0.7-tem`) |
| golem + rusi source | https://github.com/CycloneDX/cdxgen-plugins-bin @ `f0eb7677419445e88103c89805589d3318a64278`, built from `thirdparty/golem` / `thirdparty/rusi` |
| dosai source | https://github.com/OWASP/dosai (local clone `~/work/owasp/dosai`) @ `4d5df2619cd6c26323d1e06ec9a32a12e166167f` |
| kosi source | https://github.com/CycloneDX/cdxgen-plugins-bin `thirdparty/kosi` — **pre-1.0, under active development** (repo at P26 on 2026-09-19); the fixtures were produced by the committed binary below, not by a fresh build |

## dotnet-eshoponweb-dosai-dataflows.json

- **Engine**: Dosai, `AnalyzerVersion 5.0.0.0`, `SchemaVersion 5.0.0`, `Tool "Dosai"`
  (from the report's own `Metadata`).
- **Build**: `cd ~/work/owasp/dosai && dotnet build -c Release ./Dosai/Dosai.csproj` (0 errors).
- **Command** (run from `~/work/owasp/dosai`):
  `dotnet run --project ./Dosai/Dosai.csproj -c Release -- dataflows --path ~/sandbox/dosai-corpus/eShopOnWeb --pattern-packs all --o dosai-eshoponweb-dataflows.json`
- **Target**: https://github.com/dotnet/eShopOnWeb @ `4da8212117e87d808d4bbc7da6286fd2147ce606`
- **Generated**: 2026-09-18T10:53:49.593377+00:00 (report `Metadata.GeneratedAt`).
- **Original report**: 53,298,481 bytes, md5 `dbd47b886e9b12deb68e89a9fafcfa46`.
- **Committed fixture**: 2,066,624 bytes, md5 `783594e7c1d981b69a485d24e6f7dcff`.
- **Trimming**: first 60 `Slices[]` (contiguous, emitted order) + the 137 `Nodes[]`
  and 300 `Edges[]` they reference by id (original order, **0 unresolved ids**);
  `WeaknessCandidates` kept for the kept slice ids (60 of 904);
  `DangerousApiReachability` kept where `SliceIds` intersects the kept set (55 of
  810); `MethodSummaries` dropped entirely (3004 entries — engine-internal
  summary table, not id-joined into slices). `Metadata`, `Statistics`,
  `Diagnostics` (151 strings), `EntryPoints` (60), `AttackSurface` (4),
  `PackageReachability` (45), `Patterns`, `SanitizedFlows`, `ExploitChains` kept
  verbatim/whole.
- **Engine's own `Statistics` (verbatim, describes the full untrimmed run — the
  fixture contains fewer records by design):**
  ```json
  {"SourceCount": 3812, "SinkCount": 810, "SliceCount": 904, "NodeCount": 13540, "EdgeCount": 70811, "FilesAnalyzed": 529}
  ```
- **Counts inside the committed fixture (the oracle for trimmed-fixture tests):**
  Slices 60, Nodes 137, Edges 300, EntryPoints 60, AttackSurface 4,
  PackageReachability 45, WeaknessCandidates 60, DangerousApiReachability 55,
  SanitizedFlows 0, ExploitChains 0, Diagnostics 151.
- **Empty sections and why**: `SanitizedFlows` 0 and `ExploitChains` 0 — the run
  found no sanitizer-suppressed flows and no exploit chains on this target
  (eShopOnWeb has no explicit sanitizer patterns shipped in the default packs).
  The dataflows report has **no call-graph section by design** — the call graph
  lives in the `methods` report (see next fixture).
- **Notable diagnostics**: report carries 151 `Diagnostics` strings, including
  skipped-assembly warnings for reference assemblies under `tests/*/bin` (e.g.
  `mscorlib.dll ... Reference assemblies cannot be loaded for execution`).

## dotnet-eshoponweb-dosai-methods.json

- **Engine**: Dosai, same build as above; `AnalyzerVersion 5.0.0.0`,
  `SchemaVersion 5.0.0`.
- **Command** (run from `~/work/owasp/dosai`):
  `dotnet run --project ./Dosai/Dosai.csproj -c Release -- methods --path ~/sandbox/dosai-corpus/eShopOnWeb --o dosai-eshoponweb-methods.json`
- **Target**: https://github.com/dotnet/eShopOnWeb @ `4da8212117e87d808d4bbc7da6286fd2147ce606`
- **Generated**: 2026-09-18T10:56:44.298415+00:00.
- **Original report**: 91,097,756 bytes, md5 `aeffd417fc1345aaee7a158ed30c0e3d`.
- **Committed fixture**: 6,013,889 bytes, md5 `211090f6fef33c54e18ffad2df7d446c`.
- **Trimming**: first 300 `CallGraph.Edges[]` (contiguous) + the 315
  `CallGraph.Nodes[]` they reference (**0 unresolved ids**); `Reachability` kept
  for those node ids (315 of 21,570); `Methods` first 300 of 54,922;
  `MethodCalls` first 300 of 2,489; `DeadCode` 0 of 500 survived the id filter
  (no dead-code method is a node of the first 300 call-graph edges — dropped
  wholesale, recorded here). All other sections kept whole: `Dependencies` 884,
  `AssemblyInformation` 59, `Properties` 307, `Fields` 181, `Events` 3,
  `Constructors` 127, `ApiEndpoints` 53, `EntryPoints` 57, `RecursionClusters` 1,
  `SecurityFindings` 15, `PackageReachability` 81, `SourceAssemblyMapping` 636,
  `Services` 29, `AiComponents` 0, `Frameworks` 2, `Diagnostics` 1.
- **Engine's own counters (original run, verbatim):** Methods 54,922;
  CallGraph.Nodes 21,570; CallGraph.Edges 1,166; Reachability 21,570 entries;
  ApiEndpoints 53; EntryPoints 57; DeadCode 500 (capped, see diagnostic below);
  SecurityFindings 15; PackageReachability 81.
- **Notable diagnostic (verbatim)**: `"Dead-code report truncated at 500 entries;
  query reachability[reachable=false] for the full set."` — the engine itself
  caps the dead-code list at 500.
- **Empty sections and why**: `AiComponents` 0 — no AI-attributed components in
  this target. There are **no data-flow slices in a methods report by design** —
  flows come from the `dataflows` command.

## go-ipsw-golem.json

- **Engine**: golem 3.2.0 (`--version` output `golem 3.2.0`; report `tool.name`
  `"golem"`, `tool.version "3.2.0"`), schema
  `https://cdxgen.github.io/cdxgen-plugins-bin/golem/schema/v6`.
- **Build**: `cd ~/work/cdxgen/cdxgen-plugins-bin/thirdparty/golem && make darwin`
  (there is no `make build` target; `darwin` builds `build/golem-darwin-arm64`
  via `go build -trimpath -ldflags "-s -w -X main.version=3.2.0"`).
- **Command**:
  `~/work/cdxgen/cdxgen-plugins-bin/thirdparty/golem/build/golem-darwin-arm64 analyze --dir ~/sandbox/ipsw --format json --callgraph static --dataflow all --out golem-ipsw.json --progress`
  (run took ~9 min; progress log: `data-flow SEAM engine complete slices=1000
  nodes=1730 edges=1753 elapsed=513901ms`).
- **Target**: https://github.com/blacktop/ipsw @ `e96e74907d5204dc8153f0cf7d7056404fa911dd`
- **Original report**: 257,561,731 bytes, md5 `b3d88c671746acea120be2539d992f01`.
- **Committed fixture**: 11,246,966 bytes, md5 `bc36dce6d4a2ebfa42686f263dae8186`.
  (Re-trimmed on 2026-09-18 for the `attack-surface` phase — see the trimming
  notes; the first commit of this fixture, trimmed around the first 1,000 call
  graph edges, was 8,616,110 bytes, md5 `0d47571ce60f2f513b0498df1b94b7e5`.)
- **Trimming**: `dataFlow` kept **whole** (397 slices, 1,730 nodes, 1,753 edges
  — its own `stats` block is therefore directly assertable);
  `callGraph` re-trimmed to the **subgraph reachable from the endpoint
  handlers** instead of the first 1,000 emitted edges: the seed set anchors
  each of the 57 `apiEndpoints[]` in the call graph (handler id; handler name +
  `packagePath`; falling back to call-graph nodes whose position falls inside
  the endpoint's `range` — gin reports most handlers as the literal string
  `"func literal"`, so the range is the only usable anchor for those), and the
  kept edges are the 3,325 of 22,308 whose source node is in the transitive
  closure of those seeds. 986 of 7,848 nodes and the `reachability.nodes`
  entries for those 986 ids are kept. `roots`, `mode`, `algorithm`,
  `diagnostics`, `stats` kept verbatim — note `callGraph.stats` still reports
  the full run's 7,848 / 22,308, which is how a reader tells the section is a
  subgraph. 31 of the 57 endpoints anchor; the join over this subgraph attaches
  179 flow instances to 16 endpoints. Dropped wholesale (raw evidence tables,
  not id-joined into flows): `packages` (184), `files` (723), `imports` (5,493),
  `declarations` (10,458), `usages` (52,308). Everything else kept whole:
  `rootModules` 1, `modules` 204, `buildDirectives` 120, `nativeArtifacts` 1,
  `nativeBoundary` 82, `buildShapeDeltas` 157, `apiEndpoints` 57,
  `externalUrls` 116, `services` 53, `securitySignals` 1,717, `crypto`,
  `supplyChain`, top-level `stats`.
- **Re-trim determinism check**: the untrimmed report was regenerated with the
  recorded command line and compared section-by-section against the first
  commit of this fixture. Every section is identical except `dataFlow.stats.elapsedMillis`
  (513,901 → 479,994 ms) and two hash-named `dataFlow` node/edge ids whose
  sha256 digests fold differently between runs; all 397 slices are identical.
  The committed `dataFlow` section is the *original* one, untouched; only
  `callGraph` was replaced.
- **Engine's own `stats` (verbatim, whole run):**
  ```json
  {"packageCount": 184, "moduleCount": 204, "fileCount": 723, "generatedFileCount": 9, "importCount": 5493, "declarationCount": 10458, "usageCount": 52308, "runtimeUsageCount": 52308, "testUsageCount": 0, "benchmarkUsageCount": 0, "fuzzUsageCount": 0, "exampleUsageCount": 0, "buildDirectiveCount": 120, "nativeArtifactCount": 1, "nativeBoundaryCount": 82, "buildShapeDeltaCount": 157, "apiEndpointCount": 57, "externalUrlCount": 116, "serviceCount": 53, "securitySignalCount": 1717, "goModReplaceCount": 0, "goModExcludeCount": 0, "vendorModuleCount": 0, "workspaceModuleCount": 0, "privateModuleHintCount": 0, "licenseFileModuleCount": 201, "cryptoLibraryCount": 106, "cryptoAssetCount": 9, "cryptoOperationCount": 323, "cryptoMaterialCount": 320, "cryptoProtocolCount": 1, "cryptoFindingCount": 146, "dataFlowSourceCount": 339, "dataFlowSinkCount": 582, "dataFlowSliceCount": 397, "diagnosticCount": 24}
  ```
- **`dataFlow.stats` (verbatim, kept whole in the fixture — this IS the oracle):**
  ```json
  {"sourceCount": 339, "sinkCount": 582, "sliceCount": 397, "nodeCount": 1730, "edgeCount": 1753, "summaryCount": 0, "functionCount": 78408, "instructionCount": 0, "elapsedMillis": 513901, "truncated": true, "truncationReasons": ["slice limit reached at 1000; further findings were not materialised"], "uniqueFlowCount": 335, "duplicateSliceCount": 62, "duplicateGroupCount": 39, "maxPathLength": 12, "averagePathLength": 4.468513853904282}
  ```
- **Honesty constraints recorded by the engine itself**: `truncated: true` with
  `truncationReasons ["slice limit reached at 1000; further findings were not
  materialised"]` — the SEAM engine produced 1000 slices and the report keeps
  397 after dedupe (62 duplicate slices in 39 groups, `uniqueFlowCount` 335).
  The run also used the default per-slice witness caps (`dataflow-max-trace-nodes
  64`, `dataflow-max-trace-edges 128`); max path length observed is 12, so no
  single slice was path-capped in this run, but the report-level truncation flag
  stands. No slice in this run carries `sanitizerNodeIds`.
- **Empty sections and why**: none — flow (`dataFlow.slices` 397), call-graph
  (`callGraph` 7,848 nodes / 22,308 edges in the original) and endpoint
  (`apiEndpoints` 57) sections are all non-empty.

## go-ipsw-golem-roots.json

The **crypto-reach half of the golem root-set pair**: the same target, binary
and command line as `go-ipsw-golem.json` plus `--roots handlers,main,exported`.
Added 2026-09-19. The old fixture is kept alongside on purpose — the difference
between the two *is* the evidence that the root set drives the engine's
reachability verdict.

- **Engine**: golem 3.2.0, same binary as `go-ipsw-golem.json` (built from
  cdxgen-plugins-bin @ `f0eb767` on 2026-09-18; the clone has since moved to
  `ebd584b`, the binary has not been rebuilt).
- **Command** (the old fixture's command line plus `--roots`):
  `~/work/cdxgen/cdxgen-plugins-bin/thirdparty/golem/build/golem-darwin-arm64 analyze --dir ~/sandbox/ipsw --format json --callgraph static --dataflow all --roots handlers,main,exported --out golem-ipsw-roots.json --progress`
  (13m35s; progress log: `data-flow SEAM engine complete slices=1000
  nodes=1730 edges=1753 elapsed=800962ms`).
- **Target**: https://github.com/blacktop/ipsw @ `e96e74907d5204dc8153f0cf7d7056404fa911dd`
  — the same checkout, unmodified between the two runs.
- **Original report**: 258,664,554 bytes, md5 `9cd43eec656209d24d64f09627403dca`.
- **Committed fixture**: 12,193,102 bytes, md5 `7da0dc57c85dba082a6a3fbb24ccdfde`.
- **Trimming** (the same recipe as `go-ipsw-golem.json`): `dataFlow` kept
  **whole** (397 slices, 1,730 nodes, 1,753 edges); `callGraph` trimmed to the
  subgraph reachable from the endpoint handlers — 31 of 57 `apiEndpoints[]`
  anchor, giving **the identical 986 of 7,848 nodes and 3,325 of 22,308 edges**
  the old fixture keeps, so the two fixtures' call graphs are the same graph.
  `roots`, `mode`, `algorithm`, `diagnostics`, `stats` kept verbatim
  (`callGraph.stats` still reports the full 7,848 / 22,308). Dropped wholesale,
  as before: `packages` (184), `files` (723), `imports` (5,493),
  `declarations` (10,458), `usages` (52,308). Everything else kept whole.
- **Determinism across the two runs**: `dataFlow` is record-identical (all 397
  slices, same ids in the same order, 0 differing records) except
  `dataFlow.stats.elapsedMillis` (513,901 → 800,962 ms); `crypto` and
  `apiEndpoints` are byte-identical; the full run's call graph (7,848 nodes /
  22,308 edges) strictly contains the old fixture's subgraph.
- **What the root set changed, measured**: `callGraph.roots` 186 → 3,459
  (reasons `init 184, main 2` → `exported 3457, main 2`);
  `reachableFromRoots: true` **2 → 947 of 986** in the committed subgraph
  (6,048 of 7,848 in the full run). Call-graph nodes still carry **no
  `range`** (0 of 7,848; only `position`), so range-containment joins stay
  impossible for this engine.
- **Finding about golem, not about ipsw**: the `handlers` root specifier
  contributed **zero** roots — ipsw's HTTP handlers are gin handlers
  (`func(*gin.Context)`), and golem's `looksLikeHandler`
  (`internal/analyzer/callgraph.go`) only recognises the net/http signature
  `func(http.ResponseWriter, *http.Request)`. **0 of the 57 endpoints' handler
  ids appear in the root set**; the verdicts above are the work of `exported`
  (every exported package-level function of the local module is a root, so
  "reachable from roots" here means "reachable from the exported API surface
  or main", a generous — floor-correct — notion of live).

## dotnet-eshoponweb-dosai-crypto.json

The **dosai `crypto` fixture** for `crypto-reach`: the same eShopOnWeb checkout
the other dosai fixtures use, run through the engine's dedicated crypto
command. Every record carries reachability first-class
(`ReachableFromEntryPoint`, `EntryPointIds`, `DataFlowSliceIds`). Added
2026-09-19.

- **Engine**: Dosai, `AnalyzerVersion 5.0.0.0`, `SchemaVersion 5.0.0`, same
  build as the other dosai fixtures (local clone @ `4d5df2619cd6c26323d1e06ec9a32a12e166167f`).
- **Command** (run from `~/work/owasp/dosai`, native `dosai` format):
  `dotnet run --project ./Dosai/Dosai.csproj -c Release -- crypto --path ~/sandbox/dosai-corpus/eShopOnWeb --o dosai-eshoponweb-crypto.json`
- **Target**: https://github.com/dotnet/eShopOnWeb @ `4da8212117e87d808d4bbc7da6286fd2147ce606`.
- **Generated**: 2026-09-19T01:08:14.311543+00:00 (report `Metadata.GeneratedAt`).
- **Original report**: 68,961,970 bytes, md5 `4da2150aa347bc1d3bc57a64b1e692b6`.
- **Committed fixture**: 1,590,696 bytes, md5 `d0340436d989c6ee76e2d3c24b0ed068`.
- **Trimming**: the crypto arrays are the payload and kept **whole** — `Assets`
  3, `Operations` 3, `Materials` 2, `Protocols` 0, `Findings` 5 (13 records).
  Inside `CryptoDataFlows`: the **3 `Slices` the crypto records reference by
  `DataFlowSliceIds`** (`dfs1`, `dfs2`, `dfs3` — the witness paths behind the
  findings; not contiguous in emitted order, which runs dfs1, dfs10, dfs100,
  …) plus the 12 `Nodes` and 18 `Edges` they reference (**0 unresolved ids**);
  `EntryPoints` 60, `AttackSurface` 4, `PackageReachability` 43, `Patterns`,
  `Statistics`, `Diagnostics` 151 kept whole; `WeaknessCandidates` kept for
  the kept slice ids (3 of 629); `DangerousApiReachability` kept where its
  `SliceIds` intersect the kept set (3 of 576); `MethodSummaries` dropped
  entirely (2,898 entries — engine-internal, same call as the dataflows
  fixture). Top-level `Statistics` and `Diagnostics` (0) kept whole.
- **Engine's own `Statistics` (verbatim, describes the full untrimmed run):**
  ```json
  {"FilesAnalyzed": 254, "AssetCount": 3, "OperationCount": 3, "MaterialCount": 2, "ProtocolCount": 0, "FindingCount": 5, "ReachableFindingCount": 1, "CryptoDataFlowSliceCount": 629}
  ```
- **The record this fixture exists for**: `cf5`/`cop3`/`cas3` — a weak
  (`DES/RC2/RC4`) symmetric cipher at `IdentityTokenClaimService.cs:43` with
  `ReachableFromEntryPoint: true` and entry points
  `POST /api/authenticate` + `AuthenticateEndpoint#Handle`. Cross-checked
  against the committed methods fixture: dosai's own `Reachability` entry for
  `IdentityTokenClaimService.GetTokenAsync` names **the same two entry-point
  ids** with `DepthFromEntryPoint: 1` — two independent engine computations
  over the same target agree.
- **Severity vocabulary note**: dosai Pascal-cases crypto severities
  (`"High"`), where golem lower-cases (`"high"`); atom-tools folds both onto
  error/warning/note for ranking and keeps the verbatim spelling beside it.

## rust-microservices-kafka-rusi.json

- **Engine**: rusi 3.2.0 (`--version` output `rusi 3.2.0`; report `tool.name`
  `"rusi"`, `tool.version "3.2.0"`), schema
  `https://appthreat.github.io/rusi/schema/report-0.1`.
- **Build**: `cd ~/work/cdxgen/cdxgen-plugins-bin/thirdparty/rusi && cargo build --release` (finished in 17.89s).
- **Command**:
  `~/work/cdxgen/cdxgen-plugins-bin/thirdparty/rusi/target/release/rusi analyze --dir ~/sandbox/rust-microservices-kafka --callgraph static --dataflow security --out rusi-rust-microservices.json`
- **Target**: https://github.com/cschaible/rust-microservices-kafka @ `4c5596fedcf68673de1e8b0b39d3eb9aca7437db`
- **Runtime (from the report)**: rustc 1.98.0, host aarch64-macos.
- **Original report == committed fixture, untrimmed**: 3,219,424 bytes, md5
  `71a4a2d21b10cfb2429e748e469ed257`. Nothing was removed.
- **Engine's own `stats` (verbatim — this IS the oracle):**
  ```json
  {"package_count": 17, "file_count": 180, "import_count": 1079, "declaration_count": 722, "usage_count": 1984, "security_signal_count": 0, "crypto_library_count": 2, "crypto_component_count": 0, "crypto_material_count": 17, "crypto_finding_count": 0, "call_graph_node_count": 712, "call_graph_edge_count": 2156, "data_flow_node_count": 581, "data_flow_edge_count": 77, "data_flow_slice_count": 5, "api_endpoint_count": 14}
  ```
- **`data_flow.stats` (verbatim):**
  ```json
  {"source_count": 508, "sink_count": 5, "slice_count": 5, "node_count": 581, "edge_count": 77, "summary_count": 371}
  ```
- **Empty sections and why**: `security_signal_count` 0 and `crypto_finding_count`
  0 — no configured security-signal rules fired and no crypto misuse findings on
  this target. Flow (5 slices), call-graph (712 nodes / 2,156 edges) and endpoint
  (14) sections are all non-empty.
- **Honesty constraints (from rusi's documentation, visible in the output shape)**:
  each slice records **one representative witness** (`node_ids`/`edge_ids`);
  diagnostics report unanalysed `doc!` macro bodies (5 files) and
  missing-passthrough taint-loss observations (`axum::extract::Extension`
  observed 60 times, `as_any` 9 times, `ceil` 4 times).

## atom — java-petclinic-reachables.json (referenced, not copied)

- **Engine**: atom (Scala 3 on chen), already exercised by this repo's suite.
- **Fixture**: the pre-existing `test/data/java-petclinic-reachables.json`
  (791,549 bytes, md5 `082c890a0fd84666fd8e30b71dc91ce2`). It is **referenced by
  path, not copied** into this directory — copying would create a duplicate
  digest, which this file exists to prevent. No new atom run was required for
  this round; the existing fixture already covers the atom reachables shape
  (bare-array chunk merging is covered separately by `test/data/chunked/`).

## atom — java-petclinic-atom-cpg.graphml, java-petclinic-atom-centrality.json, java-petclinic-atom-scc.json

The **atom half of the `graph` phase**: a real `atom export --format graphml`
and real `atom algorithms` outputs (centrality and scc). Added 2026-09-19.

- **Engine**: atom **v3.2.0** (tag `v3.2.0`, commit
  `49360b5954677cf3ff380a7615e8efe4c706835b`), the staged universal
  distribution at `~/work/AppThreat/atom/target/universal/stage`, launched
  via `~/work/AppThreat/atom/atom.sh` on openjdk 26.0.2 (darwin/arm64).
  `GITHUB_TOKEN=$(gh auth token)` was exported for the chen GitHub Packages
  resolver per the build instructions.
- **Target**: the petclinic tree at `~/sandbox/java-corpus/petclinic` @
  `818c4136ea971c21674525f9053de0d9c7ad8cfe` — the same corpus family as the
  pre-existing `../java-petclinic-reachables.json` fixture.
- **Commands** (run from a scratch directory; the export builds the atom
  first, the algorithms runs reuse it via `-o petclinic.atom`):
  `bash ~/work/AppThreat/atom/atom.sh export -l java -o petclinic.atom --format graphml --out exports ~/sandbox/java-corpus/petclinic`
  (5.3s; prints `Exported 6010 nodes and 23406 edges to exports` and the
  overflowdb warning `discarded 144 list properties (because they are not
  supported by the graphml spec)` — the engine's own honesty about the
  export, kept here verbatim);
  `bash ~/work/AppThreat/atom/atom.sh algorithms -l java -o petclinic.atom --type centrality -s centrality.json ~/sandbox/java-corpus/petclinic`;
  `bash ~/work/AppThreat/atom/atom.sh algorithms -l java -o petclinic.atom --type scc -s scc.json ~/sandbox/java-corpus/petclinic`.
  Note the command order: scopt takes the subcommand **first**
  (`atom export -l java ... <input>`); `-i` is not an option, the input is
  positional.
- **What the export is**: the **whole CPG** in graphml (all node labels —
  METHOD, CALL, FILE, BLOCK, TAG, LITERAL, IDENTIFIER, ... — 6,010 nodes /
  23,406 edges), not a call graph. A call site is a `CALL` node whose
  outgoing `CALL` edge points at the callee `METHOD`; the caller is the
  nearest `METHOD` ancestor over `AST` edges. Measured on this export:
  every AST chain from a call site to its method traverses only BLOCK,
  CONTROL_STRUCTURE, CALL and RETURN nodes.
- **java-petclinic-atom-cpg.graphml** — committed fixture: **991,979 bytes,
  md5 `f606555f0357ab3c3c317e094a4b7e78`**. Trimmed from the original
  `exports/export.xml` (**10,221,665 bytes, md5
  `bb0345b424402c99eb6b1cce7eaa9b6f`**, regenerable in ~5s with the recorded
  command): kept node labels METHOD (219), CALL (533), FILE (31), BLOCK
  (280), CONTROL_STRUCTURE (43), RETURN (78) and edge labels CALL (533),
  AST (934 of 4,179 — those with both endpoints kept), SOURCE_FILE (118 of
  174 — the METHOD→FILE ones). Every `<key>` declaration is kept verbatim,
  kept records are unedited and in emitted order. **The call-graph view
  itself is complete**: all 219 METHOD nodes and all 533 CALL edges of the
  run are present, so unlike the golem fixture this is not a call-graph
  subgraph — only the non-call-graph CPG furniture (literals, identifiers,
  tags, types) was dropped.
- **Counts inside the committed graphml**: METHOD nodes 219 (121 internal
  `IS_EXTERNAL=false`, 98 external — jdk/library/operator methods, which is
  why `<operator>.fieldAccess` tops the centrality ranking); 533 call sites
  aggregating to 417 (caller, callee, dispatch-type) edges;
  `DISPATCH_TYPE` mix over those edges: STATIC_DISPATCH 244,
  DYNAMIC_DISPATCH 173. 93 methods carry LINE_NUMBER (the internal ones).
- **java-petclinic-atom-centrality.json** — committed **verbatim, untrimmed**:
  41,342 bytes, md5 `7a70ac9b1da87bf4951e5fe9ff16e1d6`. Shape:
  `{"ranking": [{"method", "pageRank", "inDegree"}, ...]}`, 219 entries
  sorted by pageRank desc — atom's own PageRank over `Method -CALL-> Method`
  (see `GraphCommands.centralityReport`), consumed verbatim by
  `atom-tools graph --metric centrality --algorithms`.
- **java-petclinic-atom-scc.json** — committed **verbatim, untrimmed**: 94
  bytes, md5 `9c57889d088e16e65340a8d4eb823f98`. Shape:
  `{"componentCount": 219, "recursiveComponentCount": 0,
  "recursiveComponents": []}` — no recursion cluster in petclinic per the
  engine. (Note: atom's scc counts a singleton self-recursion as a
  "recursive component" only when it has >1 member or a self-loop; the
  derived Tarjan in `atom_tools/lib/callgraph.py` agrees on this target.)
- **Empty-and-why**: none — all three artefacts are non-empty; the scc
  `recursiveComponents` list is empty because the target genuinely has no
  recursive method.

## kotlin-*-kosi.json — the kosi fixtures

Added 2026-09-19 for the kosi (Kotlin/JVM) phase. **Read this section before
regenerating any of these files.** kosi is pre-1.0 and under heavy active
development; `schemaVersion` is pinned at `kosi/1`, but the field-level shape
has already changed under the binary that produced these fixtures (see
"Binary predates the schema sources" below). A report regenerated from a newer
kosi may not match these files, and that is the point of recording the binary
here.

- **Engine**: kosi **0.2.0**, commit
  `2e1f7b53357b003679914fadf95918f02864c9e1` (from the report's own `tool`
  object and `kosi version`), schema `kosi/1`. Native image, host
  `darwin-aarch64` — the shipped binary is
  `build/kosi-darwin-arm64` (99,381,728 bytes, built 2026-09-16). **CI cannot
  run kosi**: darwin-arm64 only and ~99 MB. Fixtures are generated once, by
  hand, on this machine.
- **Binary predates the schema sources**: the `FlowSlice` data class in the
  repo (P22+) declares `pathKind`/`frames`/`framesCutBy` and *replaces*
  `reachableFromRoots`/`rootWitness`; the 0.2.0 binary still emits the old
  fields and none of the new ones. The fixtures therefore carry
  `reachableFromRoots`/`rootWitness`/`elided` and no `pathKind`. Both
  spellings are read when present.
- **`runtime` is never written**: `KosiReport` declares 19 fields but the
  JSON writer emits 18 keys — `runtime` is constructed and silently dropped.
  These fixtures accordingly have no `runtime` key.
- **Determinism**: two runs of the same command produced byte-identical
  reports (verified for `dsl-media-auth`), including the sha256 `flowKey`
  values. `options.jdkHome` embeds the absolute SDKMAN path.
- **Command** (one line per fixture; run from
  `~/work/cdxgen/cdxgen-plugins-bin/thirdparty/kosi`; every fixture is the
  **whole untrimmed report** — no trimming, no edits):

  ```
  ./build/kosi-darwin-arm64 analyze --dir fixtures/<name> --backend resolved \
    --jdk-home ~/.sdkman/candidates/java/21.0.7-tem \
    --dataflow all --callgraph auto --roots all --endpoint-sources \
    --out <tmp>/<name>.json
  ```

  The baseline additionally uses `--backend syntax` (see its section).

### kotlin-dsl-media-auth-kosi.json

- 178,029 bytes, md5 `26feeeec231ceedb6495b401a06289aa`. Committed verbatim,
  untrimmed.
- **What it exists for**: the authentication fixture. 11 `apiEndpoints` — 1
  with `role(ADMIN)`, 1 with `security-constraint(denied)` (a deny rule, not
  an auth requirement), 1 with `security-constraint(admin,auditor)`, 8 with
  `authentication: []` (no declaration — which is not anonymity). `foundBy`
  in two spellings here (`dsl` 8, `descriptor` 3; the third spelling,
  `annotation`, is on the command-exec fixture's endpoint). `exported` is
  `true` on the 3 descriptor endpoints and `null` on the 8 dsl ones. Also
  the `graph` fixture: callGraph 64 nodes / 13 edges, `algorithmUsed: vta`.
- **dataFlow is empty on purpose**: 0 slices despite `--dataflow all` — the
  fixture's routes reach no modelled taint sink. Its claim is endpoints and
  auth, not flows.
- **Wire quirks visible here**: two vertx endpoints (`/secure`, `/token`)
  publish an empty `handlerCanonicalName` and an empty `httpMethod` list —
  the route shape matched but the method/handler registers did not fold.
  `position.filename` is **relative** on all source-derived endpoints.

### kotlin-command-exec-kosi.json

- 32,017 bytes, md5 `90bae035ea7e2f2072187644ce8ecc94`. Committed verbatim,
  untrimmed.
- **What it exists for**: the flow fixture. 2 `dataFlow.slices`
  (`taint/untrusted-input-to-process-exec`), severity `critical`,
  confidence `high`, sink `java.lang.ProcessBuilder` at argument 0, with
  `nodeIds`/`edgeIds` witnesses (15 nodes / 13 edges). 1 endpoint
  (`GET /run`, spring-mvc, `foundBy: annotation` — the third spelling) that
  carries the engine's own flow link: `sliceIds: ["slice-000001"]`.
- callGraph present but degenerate (3 nodes, 0 edges) — the endpoint's reach
  comes from the engine's slice link, not a traversal.

### kotlin-command-exec-kosi-baseline.json

- 19,123 bytes, md5 `20249de5dfcf4570e932416dbf50ca30`. Committed verbatim,
  untrimmed. Same fixture and same command line as the current-side fixture
  **except `--backend syntax`** (no `--jdk-home`, which the syntax backend
  does not use).
- **What it exists for**: the `drift` pair, and the degradation contract.
  The syntax run reports **0 slices, 0 endpoints and no callGraph key** —
  the only trace of why is one `diagnostics` entry
  (`syntax-backend-no-resolution`). Diffed against the current side: +2
  added flows, +1 entry point. This is also the trap the phase brief
  described ("a run without --jdk-home silently degrades"): with this
  binary, `--backend resolved` *without* `--jdk-home` does **not** degrade
  (the native image bundles a JVM and resolves normally); what degrades to
  near-empty output is the syntax backend. Check `diagnostics` before
  concluding kosi found nothing.

### kotlin-android-manifest-app-kosi.json

- 33,785 bytes, md5 `1a4b82878b6672d54c23c19774bb44b1`. Committed verbatim,
  untrimmed.
- **What it exists for**: the `exported` fixture. 5 `apiEndpoints` found by
  `manifest` with `exported` `true` (3) *and* `false` (2) — a positive
  engine statement in both directions. `httpMethod` is empty on all 5 (they
  are android components, not HTTP routes); `pathTemplate` is the intent
  action or the component short name, not a URL path; `purl` is empty on
  all 5.
- **`position.filename` is ABSOLUTE on every manifest endpoint**
  (`/Users/prabhu/work/cdxgen/.../AndroidManifest.xml`), where the
  source-derived endpoints in the other fixtures are relative. Do not
  assume either; the engine emits both.

### kotlin-crypto-material-flow-kosi.json

- 29,005 bytes, md5 `f08049b0d31e34832790e6cf3a05c710`. Committed verbatim,
  untrimmed.
- **What it exists for**: the crypto fixture. `crypto` carries 3 assets, 2
  materials, 2 operations, 1 finding (`low-iteration-pbkdf2`, severity
  `medium`) and 0 libraries/protocols; `dataFlow` carries 2
  `taint/hardcoded-secret-to-crypto-asset` slices (severity `medium`).
  Assets have no location field at all; materials/findings have a file
  position but no enclosing function; operations carry `function` — the
  three join grains crypto-reach distinguishes, one per record kind.

## Digest summary (all distinct)

| file | bytes | md5 |
|---|---|---|
| dotnet-eshoponweb-dosai-crypto.json | 1,590,696 | `d0340436d989c6ee76e2d3c24b0ed068` |
| dotnet-eshoponweb-dosai-dataflows.json | 2,066,624 | `783594e7c1d981b69a485d24e6f7dcff` |
| dotnet-eshoponweb-dosai-methods.json | 6,013,889 | `211090f6fef33c54e18ffad2df7d446c` |
| go-ipsw-golem.json | 11,246,966 | `bc36dce6d4a2ebfa42686f263dae8186` |
| go-ipsw-golem-roots.json | 12,193,102 | `7da0dc57c85dba082a6a3fbb24ccdfde` |
| rust-microservices-kafka-rusi.json | 3,219,424 | `71a4a2d21b10cfb2429e748e469ed257` |
| kotlin-android-manifest-app-kosi.json | 33,785 | `1a4b82878b6672d54c23c19774bb44b1` |
| kotlin-command-exec-kosi.json | 32,017 | `90bae035ea7e2f2072187644ce8ecc94` |
| kotlin-command-exec-kosi-baseline.json | 19,123 | `20249de5dfcf4570e932416dbf50ca30` |
| kotlin-crypto-material-flow-kosi.json | 29,005 | `f08049b0d31e34832790e6cf3a05c710` |
| kotlin-dsl-media-auth-kosi.json | 178,029 | `26feeeec231ceedb6495b401a06289aa` |
| java-petclinic-atom-cpg.graphml | 991,979 | `f606555f0357ab3c3c317e094a4b7e78` |
| java-petclinic-atom-centrality.json | 41,342 | `7a70ac9b1da87bf4951e5fe9ff16e1d6` |
| java-petclinic-atom-scc.json | 94 | `9c57889d088e16e65340a8d4eb823f98` |
| ../java-petclinic-reachables.json (reference) | 791,549 | `082c890a0fd84666fd8e30b71dc91ce2` |

Original untrimmed reports (kept for comparison; not committed):

| original | bytes | md5 |
|---|---|---|
| dosai crypto (eShopOnWeb) | 68,961,970 | `4da2150aa347bc1d3bc57a64b1e692b6` |
| dosai dataflows (eShopOnWeb) | 53,298,481 | `dbd47b886e9b12deb68e89a9fafcfa46` |
| dosai methods (eShopOnWeb) | 91,097,756 | `aeffd417fc1345aaee7a158ed30c0e3d` |
| atom export.xml (petclinic, whole CPG graphml) | 10,221,665 | `bb0345b424402c99eb6b1cce7eaa9b6f` |
| golem analyze (ipsw) | 257,561,731 | `b3d88c671746acea120be2539d992f01` |
| golem analyze with --roots handlers,main,exported (ipsw) | 258,664,554 | `9cd43eec656209d24d64f09627403dca` |
| rusi analyze (rust-microservices-kafka) | == committed fixture | `71a4a2d21b10cfb2429e748e469ed257` |

## rust-microservices-kafka-rusi-baseline.json

The **baseline half of the `drift` pair**: the same target repository, the same
engine and the same command line as `rust-microservices-kafka-rusi.json`, run
against an earlier commit. Added 2026-09-18 for Phase 3.

- **Engine**: rusi 3.2.0 (`tool.name "rusi"`, `tool.version "3.2.0"`), schema
  `https://appthreat.github.io/rusi/schema/report-0.1`. Same binary as the
  current-side fixture.
- **Command** (identical to the current-side fixture except `--dir` and `--out`):
  `~/work/cdxgen/cdxgen-plugins-bin/thirdparty/rusi/target/release/rusi analyze --dir /tmp/claude-501/rust-base --callgraph static --dataflow security --out /tmp/claude-501/rusi-rust-base.json`
- **Target**: https://github.com/cschaible/rust-microservices-kafka @
  `1453f9a` ("Extract avro schema definitions into avsc files"), five commits
  behind the `4c5596fedcf68673de1e8b0b39d3eb9aca7437db` that produced the
  current-side fixture. Checked out with `git worktree add` into
  `/tmp/claude-501/rust-base` so the original clone was left untouched.
  (The clone was shallow at depth 1 and was unshallowed with
  `git fetch --unshallow` to reach the older commit.)
- **Original report == committed fixture, untrimmed**: 3,201,519 bytes, md5
  `549893cf08e9d77b3da5f511cde52cdc`. Nothing was removed, nothing was edited.
  Distinct from the current-side fixture (`71a4a2d21b10cfb2429e748e469ed257`).
- **Engine's own `stats` (verbatim):**
  ```json
  {"package_count": 17, "file_count": 180, "import_count": 1065, "declaration_count": 722, "usage_count": 1984, "security_signal_count": 0, "crypto_library_count": 2, "crypto_component_count": 0, "crypto_material_count": 17, "crypto_finding_count": 0, "call_graph_node_count": 713, "call_graph_edge_count": 2156, "data_flow_node_count": 581, "data_flow_edge_count": 77, "data_flow_slice_count": 5, "api_endpoint_count": 14}
  ```
- **`data_flow.stats` (verbatim):**
  ```json
  {"source_count": 508, "sink_count": 5, "slice_count": 5, "node_count": 581, "edge_count": 77, "summary_count": 371}
  ```
- **Why this pair is worth having**: the two runs differ in ways a naive diff
  gets wrong. Both report 5 slices with the same 5 source→sink identities, but
  two of them (`common_security::load_jwk_decoders`, in `app-user-service` and
  `app-accommodation-service`) sit at **line 38 in the baseline and line 39 in
  the current**, and the engine emits the five slices in a different order.
  The correct answer is therefore **0 added, 0 removed, 2 moved** — which is
  exactly the property `drift` exists to get right, here on real engine output
  rather than a synthetic transformation. The baseline was also produced from a
  different absolute directory (`/tmp/claude-501/rust-base` vs
  `~/sandbox/rust-microservices-kafka`), so the pair exercises path
  normalisation too; rusi happens to emit repo-relative paths, so no rebasing
  is needed for this engine — see `test_drift.py` for the golem path-rebase
  test, where paths are absolute.
- **Other real differences between the two runs** (engine `stats`):
  `import_count` 1065 → 1079 and `call_graph_node_count` 713 → 712. Neither
  changes a flow, which is why both runs report 5 slices.

## go-ipsw-golem-baseline.json

The **baseline half of the golem `drift` pair**: the same target repository, the
same binary and the same command line as `go-ipsw-golem.json`, run against an
earlier commit. Added 2026-09-18 for Phase 3.

- **Engine**: golem 3.2.0 (`tool.name "golem"`, `tool.version "3.2.0"`), schema
  `https://cdxgen.github.io/cdxgen-plugins-bin/golem/schema/v6`. Same binary as
  the current-side fixture.
- **Command** (identical to the current-side fixture except `--dir` and `--out`):
  `~/work/cdxgen/cdxgen-plugins-bin/thirdparty/golem/build/golem-darwin-arm64 analyze --dir /tmp/claude-501/ipsw-base --format json --callgraph static --dataflow all --out /tmp/claude-501/golem-ipsw-base.json --progress`
- **Target**: https://github.com/blacktop/ipsw @ `c48f67241` ("chore(deps): bump
  docker/setup-buildx-action from 3 to 4 (#1108)"), roughly 400 commits behind
  the `e96e74907d5204dc8153f0cf7d7056404fa911dd` that produced the current-side
  fixture. Checked out with `git worktree add` into `/tmp/claude-501/ipsw-base`
  so the original clone was left untouched.
- **Runtime**: 27m46s (the current-side run took ~9 min; this commit's dependency
  set is larger for the SEAM engine). Progress log:
  `data-flow SEAM engine complete slices=1000 nodes=1698 edges=1751 elapsed=1607523ms`.
- **Original report**: 196,984,448 bytes, md5 `55c42722fcdf499912ecc2811959645b`.
- **Committed fixture**: 7,134,682 bytes, md5 `65c020b36b208974f125b14990f70fc0`.
- **Trimming** (the same recipe as the current-side fixture): `dataFlow` kept
  **whole** (343 slices, 1,698 nodes, 1,751 edges — its own `stats` block is
  therefore directly assertable); `callGraph` trimmed to the first 1,000
  `edges[]` (contiguous) plus the 524 `nodes[]` they reference by
  `sourceId`/`targetId` (**0 unresolved ids**) and the `reachability.nodes`
  entries for those ids (524 of 6,090). Dropped wholesale (raw evidence tables,
  not id-joined into flows): `packages` (174), `files` (631), `imports` (4,777),
  `declarations` (8,209), `usages` (40,105). Everything else kept verbatim.
  No field value was edited.
- **`dataFlow.stats` (verbatim, kept whole — this IS the oracle):**
  ```json
  {"sourceCount": 328, "sinkCount": 599, "sliceCount": 343, "nodeCount": 1698, "edgeCount": 1751, "summaryCount": 0, "functionCount": 72503, "instructionCount": 0, "elapsedMillis": 1607523, "truncated": true, "truncationReasons": ["slice limit reached at 1000; further findings were not materialised"], "uniqueFlowCount": 286, "duplicateSliceCount": 57, "duplicateGroupCount": 35, "maxPathLength": 12, "averagePathLength": 4.428571428571429}
  ```
- **Honesty constraint**: this run is **also** truncated (slice limit 1000, 343
  kept after dedupe). Both sides of the pair are truncated, so the coverage gate
  does not trip on truncation for this pair — the `truncated` flag changing from
  false to true is what trips it, and that case is covered synthetically in
  `test_drift.py`.
- **What the pair actually shows** (real, across ~400 commits):
  **+159 added, -105 removed, ~91 moved, 21 witness-changed**, 343 → 397 flows
  over 54 → 66 files, `NewHighSeverityFlows` 67, `NewMediumSeverityFlows` 92,
  `NewEntryPoints` 3 (55 → 57 apiEndpoints). The 91 moves are the point: a diff
  keyed on line numbers would have reported them as 91 more additions and 91
  more removals.
- **Known artefact, not a defect**: golem emits absolute paths, and this pair was
  generated from two different directories (`/tmp/claude-501/ipsw-base` vs
  `~/sandbox/ipsw`). Root alignment recovers the repo root, so repo files compare
  as `pkg/aea/aea.go`; Go module cache paths (`/Users/prabhu/go/pkg/mod/...`)
  are identical on both sides and are left absolute. See `align_roots` in
  `atom_tools/lib/drift.py` for the documented limit.
- **Left untouched by the phase-2 re-trim**: the current-side fixture's call
  graph was later re-trimmed around the endpoint handlers (see its section);
  this baseline keeps the first-1,000-edges recipe. `drift` reads neither call
  graph — every count it asserts comes from `dataFlow` and `apiEndpoints`,
  which are unchanged on both sides — and the pair's documented results were
  re-verified after the re-trim.

## Atom-slice invariance baseline

Every phase of the ecosystem work has promised that the original commands behave
byte-identically on atom slices. That promise is pinned here — the exact commands
and the md5 of their bytes (the output file for `convert`, stdout for the others;
`OUT` is any output path, the document does not embed it). Verified on `3886b19`
at the start of phase 8, and re-derived unchanged at its close after the golden
portability, CI and error-message work.

| command | digest (md5) |
|---|---|
| `convert -i test/data/java-piggymetrics-usages.json -o OUT -t java` (OUT) | `cbdd4c26b11d04efefd6d8db2f2f7942` |
| `convert -i test/data/js-juiceshop-usages.json -o OUT -t js` (OUT) | `c3006109418f023b5755e8ca2ae15429` |
| `stats -i test/data/java-piggymetrics-usages.json` (stdout) | `a52a5e8a2f7d0a3e957e379b1b46d079` |
| `query-endpoints -i test/data/java-piggymetrics-usages.json` (stdout) | `a72277a26c0224b89b687f6f90a10c82` |

These four are also enforced by `test/test_atom_slice_invariance.py`, so a change
anywhere on these paths fails the suite instead of waiting for someone to re-read
this table. If a digest moves, either atom-slice behaviour changed (a regression
for every existing user) or the change is deliberate — re-derive the digest,
update this table, and say so in the changelog.
