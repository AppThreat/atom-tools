# Lesson 15: Crypto reach

A CycloneDX Cryptography Bill of Materials (CBOM) inventories what crypto a system
uses: algorithms, key material, certificates. It cannot answer the question that
follows naturally: is this weak algorithm on a path an entry point reaches? The
crypto-reach command joins a report's crypto inventory to entry-point
reachability, per engine, at the granularity each engine's evidence supports.

## The granularity ladder

The join can only be as precise as the evidence. The four engines that carry
crypto sections support different claims, and every rendering states which one it
is making:

```text
    dosai    record-level     the engine's own ReachableFromEntryPoint verdicts,
                             quoted verbatim
    rusi     function-level   for materials, anchored in the call graph;
                             package-level for libraries
    kosi     mixed by kind    operations join at function grain, materials and
                             findings at file grain, assets, protocols and
                             libraries carry no location and render as
                             inventory only
    golem    package-level    crypto items carry no enclosing function, so the
                             claim is "this site sits in a package that carries
                             tainted flows", never "this call is on a tainted
                             path"
```

There is deliberately no cross-engine total. Four granularities do not sum, and
counts are per engine. The header of every output repeats this before a single
number appears.

## dosai: record level, verdicts quoted

The dosai crypto fixture from eShopOnWeb shows the strongest join in the
ecosystem:

```console
$ atom-tools crypto-reach -i test/data/ecosystem/dotnet-eshoponweb-dosai-crypto.json
Crypto reach: dosai — join granularity per engine: dosai record-level (engine)
reachability means a different thing at each granularity; counts are per engine
and are never summed across them.

* dosai: 13 item(s) (3 assets, 5 findings, 2 materials, 3 operations, 0 protocols)
  triage population (weak/legacy strength or a weak-crypto rule): 8 item(s)
  1. finding Weak or legacy symmetric cipher was detected. (DOSAI-CRYPTO-WEAK-CIPHER),
     severity High, CWE-327  tests/FunctionalTests/PublicApi/ApiTokenHelper.cs:46
     reach: engine-reported · not reachable from any entry point (engine verdict)
     witness slices: dfs1
  ...
  5. finding Weak or legacy symmetric cipher was detected. (DOSAI-CRYPTO-WEAK-CIPHER),
     severity High, CWE-327  src/Infrastructure/Identity/IdentityTokenClaimService.cs:43
     reach: engine-reported · reachable from an entry point (engine verdict)
     entry point: POST /api/authenticate
     entry point: ANY /AuthenticateEndpoint/Handle
     witness slices: dfs3
  ...
```

Item 1 and item 5 are the same finding in different files, and the join separates
them cleanly. The test copy is not reachable from any entry point: dead test
code, low priority. The production copy in `IdentityTokenClaimService.cs` is
reachable from `POST /api/authenticate`: a weak symmetric cipher minting tokens
on a live route. Same finding, same severity, opposite triage outcome, and the
difference is entirely the reach line. The verdicts are dosai's own, quoted
verbatim, with witness slice ids for follow-up in the dataflows report.

## kosi: kind decides the grain

The kosi fixture mixes granularities in one output, and prints the exact claim
each line supports:

```console
$ atom-tools crypto-reach -i test/data/ecosystem/kotlin-crypto-material-flow-kosi.json
Crypto reach: kosi — join granularity per engine: kosi file/function-level (derived)
...
* kosi: 8 item(s) (3 assets, 1 findings, 0 libraries, 2 materials, 2 operations, 0 protocols)
  triage population (weak/legacy strength or a weak-crypto rule): 1 item(s)
  1. finding low-iteration-pbkdf2, severity medium  src/main/kotlin/fixtures/cryptoflow/TokenService.kt:30
     reach: file-level · 2 tainted flow(s) through this file
     claim: the crypto site sits in a file that carries tainted flows — not that
     the crypto call itself is on a tainted path
  ...
  7. operation Mac HmacSHA256  src/main/kotlin/fixtures/cryptoflow/TokenService.kt:25
     reach: function-level · in the call graph, in no anchored endpoint's closure ·
     static callers: none
  8. operation SecretKeyFactory PBKDF2WithHmacSHA256  .../TokenService.kt:31
     reach: function-level · in the call graph, in no anchored endpoint's closure ·
     static callers: none
  coverage: endpoint closures from the attack-surface join: 0 of 0 endpoint(s)
  anchored in this input's call graph
```

The finding and the materials join at file grain, so their lines carry the
"claim" sentence spelling out what a file-level reach does and does not mean. The
operations carry an enclosing function, so they join at function grain: both sit
in the call graph with no static callers at all, which is itself a finding worth
a look. The assets (`EC`, `HmacSHA256`, `PBKDF2WithHmacSHA256`) carry no location
fields whatsoever, so they render as inventory with an explicit "nothing to join
on", not as unreachable.

## golem: package level, and a second signal

The golem fixture (ipsw again) demonstrates the coarsest join plus a bonus
signal:

```console
$ atom-tools crypto-reach -i test/data/ecosystem/go-ipsw-golem.json --weak-only
Crypto reach: golem — join granularity per engine: golem package-level (derived)
...
* golem: 15 item(s) (9 assets, 146 findings, 106 libraries, 320 materials, 323
  operations, 1 protocols)
  triage population (weak/legacy strength or a weak-crypto rule): 15 item(s)
  1. finding GOLEM-CRYPTO-TLS-INSECURE-SKIP-VERIFY, severity critical
     .../internal/download/transport_apple.go:31
     reach: package-level · 59 tainted flow(s) through package
     claim: the crypto site sits in a package that carries tainted flows — not
     that the crypto call itself is on a tainted path
     engine roots: 0 of 30 call-graph node(s) in this package are reachable from
     the engine's root set
  2. finding GOLEM-CRYPTO-TLS-INSECURE-SKIP-VERIFY, severity critical
     .../pkg/tss/tss.go:192
     reach: package-level · no analysed flow runs through this item's package
  ...
```

Note the parenthetical counts in the inventory line: 15 items listed but 146
findings, 320 materials and 323 operations exist in the report. The triage
population (weak or legacy strength items plus findings) is what `--weak-only`
keeps, and the text rendering caps at `--max-entries` items with a counted
remainder; the json format carries everything.

The `engine roots` line on item 1 is the call graph root signal from lesson 13
surfacing here: none of the thirty call-graph nodes in that package are
reachable from golem's root set for this run. Read together with lesson 13's
root-set caveats, it reframes the critical finding: the insecure TLS transport
sits in a package that carries tainted flows, but the engine's own root
reachability says the code may not be live from where it roots reachability.

## Out of scope, stated plainly

Atom slices and unified documents carry no crypto section. The command refuses
to produce an empty report that would read as "no crypto found":

```console
$ atom-tools crypto-reach -i test/data/java-petclinic-reachables.json
no input carries a crypto section (golem analyze --dataflow crypto|all, rusi
analyze, dosai crypto). atom emits no crypto section of any kind; there is
nothing to join for this input
```

An empty inventory and an unsupported input are different facts, and only one of
them is a finding.

## Exercises

Run the json format on the dosai fixture and inspect what each item carries that
the text rendering trims. Then feed a mixed input, the dosai crypto fixture plus
the golem fixture, and read how the output keeps the two engines' counts apart:

```console
$ atom-tools crypto-reach -i test/data/ecosystem/dotnet-eshoponweb-dosai-crypto.json -f json -o crypto.json
$ atom-tools crypto-reach -i "test/data/ecosystem/dotnet-eshoponweb-dosai-crypto.json,test/data/ecosystem/go-ipsw-golem.json"
```
