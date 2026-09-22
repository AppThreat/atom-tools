# Lesson 6: Merge slices and validate lines

Two housekeeping commands that make big and messy analyses tractable. One folds
many slice files into one; the other checks that the line numbers a slice
reports actually point at the code they claim.

## merge-slices: chunked output, polyglot projects

atom chunks large reachable slices: 1,000 flow groups per file, written as bare
JSON arrays named `reachables.json`, `reachables_1.json`, `reachables_2.json`
and so on. Polyglot projects produce one slice family per language on top of
that. The merge-slices command folds any number of them into a single
`{"reachables": [...]}` document that every other atom-tools command accepts.

The committed juice shop fixture is exactly this shape, three chunks of twenty
flow groups each:

```console
$ ls test/data/chunked/
js-juiceshop-reachables.json
js-juiceshop-reachables_1.json
js-juiceshop-reachables_2.json

$ atom-tools merge-slices -i test/data/chunked/js-juiceshop-reachables.json \
      -o merged.juice.json
Merged 60 reachable flow group(s) into merged.juice.json.
```

Only the first chunk was named; the `_1` and `_2` siblings were picked up
automatically, because sibling chunks of each input file are always collected.
That convention means passing one file per run is enough, and it also means
naming two chunks of the same run loads some of them twice. Watch what
deduplication does with that:

```console
$ atom-tools merge-slices \
      -i "test/data/chunked/js-juiceshop-reachables.json,test/data/chunked/js-juiceshop-reachables_1.json" \
      -o dup-check.json --no-dedupe
Merged 80 reachable flow group(s) into dup-check.json.

$ atom-tools merge-slices \
      -i "test/data/chunked/js-juiceshop-reachables.json,test/data/chunked/js-juiceshop-reachables_1.json" \
      -o dedupe-check.json
Merged 60 reachable flow group(s) into dedupe-check.json.
```

Four loads (two named, two collected as siblings) total 80 flow groups with
`--no-dedupe`, and the default mode collapses them back to the 60 unique ones.
Flow groups identical across input files are dropped; entries repeated within
one file keep their historical counts. When you genuinely want every group,
including duplicates, `--no-dedupe` is the switch.

Globs work too, which is the natural shape for a CI job that collects one
merged artefact per language family:

```console
$ atom-tools merge-slices -i 'reachables*.json' -o merged.reachables.slices.json
```

## validate-lines: do the line numbers point at real code

Every claim in a slice is anchored by a file and a line number. Those anchors
come from a parser, and parsers drift: a pretty-printer changes, a frontend
version bumps, and suddenly the slice says line 567 where the interesting call
actually sits on 570. The validate-lines command re-checks the slice against
your source files.

Its options encode the two judgement calls you make. `-d/--base-path` points at
the source tree, which must be the same tree atom analysed (the paths inside the
slice are relative to what atom was given). `-l/--interval` widens the match:
with the default interval of 5, a slice line 567 is searched in the window 562
to 572; an interval of 0 demands exact matches.

Run it against the usages slice of cdxgen from lesson 2, from inside the cdxgen
checkout:

```console
$ cd ~/work/cdxgen/cdxgen
$ atom-tools validate-lines -t js \
      -i ~/atom-tools-docs/cdxgen-reports/cdxgen.usages.json \
      -d . -l 5 -j validate-report.json -r validate-summary.txt
```

The JSON report lists the invalid lines (add `-v` to include the valid ones),
and the text report carries the summary. The output tells you what fraction of
anchors survived checking and which files concentrate the misses. A miss does
not mean the finding is wrong; it means the anchor drifted, and the finding
needs a human look before it is cited in a review or uploaded anywhere.

A good discipline is to run validate-lines whenever a slice is produced by a
different atom version than the one that produced the code's baseline, and
before converting to SARIF in lesson 9, since a SARIF upload pins findings to
lines in the viewer.

## Where these fit in the pipeline

```text
    atom reachables            atom reachables (lang 2)
        |   chunks                 |   chunks
        v                         v
    merge-slices  <--------------> merge-slices
        |                             |
        '--------- merged.json ------'
                      |
                  validate-lines  (anchors still true?)
                      |
                 lessons 4 onward
```

Merge first, validate once, then every downstream command runs on a single
trustworthy artefact instead of N raw chunks.

## Exercises

Merge the juiceshop chunks with `--no-dedupe` and compare `stats` output
against the deduplicated merge; observe which counts double and which do not.
Then run validate-lines with an interval of 0 on a small slice and see how many
anchors survive exact matching.
