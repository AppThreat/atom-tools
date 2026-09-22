# Lesson 13: Call graph metrics

Flow reports answer "where does data go". The call graph answers "what is
connected to what", and the graph command computes one metric over it at a time:
chokepoints (the default), centrality, blast radius, entry depth, dead code, or
recursion clusters.

It reads the call graph five engines emit. golem writes `callGraph`, rusi writes
`call_graph`, kosi writes `callGraph` with reachability verdicts, dosai's methods
report writes `CallGraph` plus `Reachability`, and atom exports graphml via
`atom export --format graphml`. Engines can be mixed in one invocation.

## Chokepoints: where paths converge

The default metric ranks nodes by how many source-to-sink paths pass through
them. On the golem fixture:

```console
$ atom-tools graph -i test/data/ecosystem/go-ipsw-golem.json
Call graph metric: chokepoints — nodes on the most source→sink paths (golem, 1 input(s))
golem: 986 nodes (833 internal, 153 external), 3325 edges
  call types: static 3325
  engine roots: 0 of 186 in this graph

-- golem (test/data/ecosystem/go-ipsw-golem.json) --
seeds: 13 source(s) → 27 sink(s) via flow-sources→flow-sinks (engine); 48 source→sink pair(s) connected
153 external node(s) excluded from the ranking (--include-external to rank them).
  1. (*github.com/blacktop/ipsw/pkg/img4.Payload).Decompress  .../pkg/img4/payload.go:329  [github.com/blacktop/ipsw/pkg/img4]  betweenness 2.0  (4% of pairs)
  2. (*github.com/blacktop/ipsw/pkg/img4.Payload).GetData  .../pkg/img4/payload.go:446  [github.com/blacktop/ipsw/pkg/img4]  betweenness 2.0  (4% of pairs)
  3. (*github.com/blacktop/ipsw/pkg/kernelcache/cpp.Scanner).batchStaticCallContexts  .../helpers.go:1833  [github.com/blacktop/ipsw/pkg/kernelcache/cpp]  betweenness 2.0  (4% of pairs
)
  ...
```

Two notes at the bottom of that output do a lot of work, and both are worth
reading slowly.

The first says the metric was computed within a subgraph: the committed fixture
carries 3,325 of the run's 22,308 edges, so every number describes that slice.
This is not a caveat about atom-tools being lazy; it is a property of the input.
The note quotes the fixture's own stats block so you can see the ratio.

The second says 13 of 58 flow source functions and 27 of 77 sink functions
anchored in the call graph. Seeds that are not nodes of the graph cannot
contribute paths, and the output says how many, instead of quietly scoring a
smaller graph as if it were the whole one.

External nodes are excluded from rankings by default because most engines'
graphs are dominated by third-party leaf calls, which a ranking should not be.
`--include-external` puts them back.

## Dead code: the engine's verdict, and why the root set is the whole story

The dead-code metric is where the honesty habit pays off most visibly. The
committed pair of golem fixtures is the same call graph (986 nodes, 3,325 edges)
from the same target, differing only in the root set golem was given:

```console
$ atom-tools graph -i test/data/ecosystem/go-ipsw-golem.json --metric dead-code
Call graph metric: dead-code — the engine's own verdict (golem, 1 input(s))
golem: 986 nodes (833 internal, 153 external), 3325 edges
  engine roots: 0 of 186 in this graph

-- golem (test/data/ecosystem/go-ipsw-golem.json) --
source: engine
nodes unreachable from the engine's roots: 984 of 986 with a verdict
note: golem's reachability measures reachability from its own roots (186 root(s),
reasons: init 184, main 2); unreachable-from-roots is the engine's liveness
verdict over its full run, not a deletability claim.
```

984 of 986 nodes unreachable. Now the same graph with the wider root set:

```console
$ atom-tools graph -i test/data/ecosystem/go-ipsw-golem-roots.json --metric dead-code
golem: 986 nodes (833 internal, 153 external), 3325 edges
  engine roots: 294 of 3459 in this graph

-- golem (test/data/ecosystem/go-ipsw-golem-roots.json) --
source: engine
nodes unreachable from the engine's roots: 39 of 986 with a verdict
note: golem's reachability measures reachability from its own roots (3459 root(s),
reasons: exported 3457, main 2); ...
```

Same code, opposite verdicts: 984 dead versus 39 dead. The difference is entirely
the root set: the first run rooted reachability at `init` and `main` functions,
the second at every exported symbol. Every "dead" verdict is relative to the
roots the engine was given, which is why the output calls it "the engine's
liveness verdict, not a deletability claim" and prints the root reasons.

The provenance file records two traps from producing this pair, both worth
knowing before you run golem yourself. Passing `--roots` replaces golem's default
root set entirely (the second run has no `init` roots at all), and
`--roots handlers` contributed zero roots on this target, because golem's handler
detection only recognises the net/http signature and ipsw uses gin.

## Centrality, and joining the engine's own algorithms

Where the engine already computes a metric, the graph command uses its value
verbatim and labels the provenance. The petclinic graphml fixture comes with
atom's own algorithm outputs, joined via `--algorithms`:

```console
$ atom-tools graph -i test/data/ecosystem/java-petclinic-atom-cpg.graphml \
      --algorithms test/data/ecosystem/java-petclinic-atom-centrality.json \
      --metric centrality
Call graph metric: centrality — PageRank and degree (atom, 1 input(s))
atom: 219 nodes (121 internal, 98 external), 417 edges
  call types: DYNAMIC_DISPATCH 173, STATIC_DISPATCH 244

-- atom (test/data/ecosystem/java-petclinic-atom-cpg.graphml) --
98 external node(s) excluded from the ranking (--include-external to rank them).
atom's own algorithms --type centrality ranking joined verbatim for 121 node(s).
  1. ...vet.Vet.getSpecialtiesInternal:java.util.Set()  .../vet/Vet.java:52  pageRank 0.006423  in/out 3/5  atom pageRank 0.006438
  2. ...owner.Owner.getPet:...Pet(java.lang.String,boolean)  .../owner/Owner.java:144  pageRank 0.00624  in/out 3/12  atom pageRank 0.006172
  3. ...model.NamedEntity.getName:java.lang.String()  .../model/NamedEntity.java:37  pageRank 0.00594  in/out 8/1  atom pageRank 0.005716
  ...
```

Two pageRank numbers per row: the one atom-tools computed over the loaded graph,
and the one atom itself computed, joined verbatim. They are close but not
identical (0.006423 versus 0.006438), because the engine ran over the full graph
while the command ranks the internal subgraph. Recomputed values say so; engine
values are labelled with their provenance. You never have to guess which number
you are reading.

## Blast radius

Blast radius answers the compromise question: if this one function is
compromised, what can it reach? Take the ipsw function that decompresses img4
payloads:

```console
$ atom-tools graph -i test/data/ecosystem/go-ipsw-golem.json \
      --blast-radius github.com/blacktop/ipsw/pkg/info.ParseZipFiles
Call graph metric: blast radius — what falls if one node is compromised (golem, 1 input(s))
golem: 986 nodes (833 internal, 153 external), 3325 edges

-- golem (test/data/ecosystem/go-ipsw-golem.json) --
node: github.com/blacktop/ipsw/pkg/info.ParseZipFiles  .../pkg/info/info.go:844
reach (including the node): 88 — 77 internal, 11 external, max depth 8
files: .../go-plist@v1.0.2/decode.go, .../lzss@v0.1.8/lzss.go, ... (+20 more)
packages: pkg:golang/github.com/blacktop/go-plist@v1.0.2, ... (+11 more)
external targets: (*github.com/blacktop/go-plist.Decoder).Decode, ... (+6 more)
```

Eighty-eight nodes reachable, eight call levels deep, across fourteen packages.
For a defender this is the transitive impact of one parsing function; for a
threat modeler it is the list of what a parser bug can touch. A leaf like the
petclinic `OwnerRepository.findById` has a reach of exactly 1, itself, which is
the other end of the spectrum and a useful sanity check that the metric
direction is what you think it is.

## Formats and exports

`-f json` carries every ranked entry where the console shows the top `--top`
(default 15). `-f mermaid` draws the ranked subgraph. `--export graphml` and
`--export gexf` write the unified graph in the vocabulary dosai's own exporters
use, so the artefacts open in yEd, Gephi and NetworkX without translation.

## Exercises

Compute entry depth on the petclinic graph and find the deepest call chain from
an entry point. Then run cycles on it and check whether petclinic has any
recursion clusters. Finally, point chokepoints at the dosai methods fixture and
compare which functions dominate a .NET graph versus the Go one:

```console
$ atom-tools graph -i test/data/ecosystem/java-petclinic-atom-cpg.graphml --metric entry-depth
$ atom-tools graph -i test/data/ecosystem/java-petclinic-atom-cpg.graphml --metric cycles
$ atom-tools graph -i test/data/ecosystem/dotnet-eshoponweb-dosai-methods.json
```
