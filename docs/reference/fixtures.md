# Lesson fixtures

The federation lessons (10 to 15) run against engine reports that are committed in
the atom-tools repository under `test/data/`. This page records where each one came
from. The authoritative source is `test/data/ecosystem/PROVENANCE.md` in the
repository; this page summarises it and adds the course-specific artefacts.

## Committed engine fixtures

Every file in `test/data/ecosystem/` was produced by running the real engine
against the real target repository. Nothing is hand-written or edited. Where a
full report was too large to commit, the fixture is a contiguous slice of real
records with the sibling tables filtered to the ids those records reference, so
id joins stay resolvable.

| fixture | engine | target | used in lesson |
|---|---|---|---|
| `dotnet-eshoponweb-dosai-dataflows.json` | dosai 5.0.0.0 | dotnet/eShopOnWeb @ 4da8212 | 10, 11, 14 |
| `dotnet-eshoponweb-dosai-methods.json` | dosai 5.0.0.0 | dotnet/eShopOnWeb | 13 |
| `dotnet-eshoponweb-dosai-crypto.json` | dosai 5.0.0.0 | dotnet/eShopOnWeb | 15 |
| `go-ipsw-golem.json` | golem | blacktop/ipsw | 10, 11, 12, 13 |
| `go-ipsw-golem-roots.json` | golem, wider root set | blacktop/ipsw | 13 |
| `go-ipsw-golem-baseline.json` | golem, ~400 commits earlier | blacktop/ipsw | 12 |
| `rust-microservices-kafka-rusi.json` | rusi | microservices-rust/kafka | 10, 14 |
| `rust-microservices-kafka-rusi-baseline.json` | rusi, older commit | microservices-rust/kafka | 12 (exercise) |
| `kotlin-command-exec-kosi.json` (+ baseline) | kosi | kosi test corpus | 10 |
| `kotlin-dsl-media-auth-kosi.json` | kosi | kosi test corpus | 11 |
| `kotlin-android-manifest-app-kosi.json` | kosi | kosi test corpus | 11 |
| `kotlin-crypto-material-flow-kosi.json` | kosi | kosi test corpus | 15 |
| `java-petclinic-atom-cpg.graphml` | atom export | spring-petclinic/spring-petclinic | 13 |
| `java-petclinic-atom-centrality.json`, `java-petclinic-atom-scc.json` | atom algorithms | spring-petclinic | 13 |

The `chunked/` directory holds a juice shop reachables slice split the way atom
chunks large outputs (`js-juiceshop-reachables.json` plus `_1` and `_2` siblings),
used in the merge lesson. The `java-petclinic-*` and `py-atom-tools-*` files at
`test/data/` top level are atom slices of spring-petclinic and of atom-tools
itself; `js-cdxgen-usages.json` is an atom usages slice of cdxgen itself.

Two properties of these fixtures matter when reading lesson outputs. First, the
trimmed ones carry fewer records than the engine's own `Statistics` block
describes, and tests use the fixture counts as the oracle. Second, if a value
looks wrong, it is a finding about the engine, and the provenance file asks you
not to fix the JSON.

## Course artefacts (generated in the lessons)

These are the artefacts produced on the cdxgen source tree during the course.
They live in the scratch directory, not in the repository.

| artefact | produced by | lesson |
|---|---|---|
| `cdxgen-reports/cdxgen.reachables.json` | atom reachables via analyze | 2 |
| `cdxgen-reports/cdxgen.usages.json` | atom usages via analyze | 2 |
| `cdxgen-reports/sbom.cdx.json` | cdxgen on itself | 7 |
| `cdxgen.sarif` | convert | 9 |
| `openapi_usages.json` | convert | 8 |
| `unified-flows.json` | ingest | 10 |
