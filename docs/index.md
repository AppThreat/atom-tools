# atom-tools lessons

This is a hands-on course for [atom-tools](https://github.com/AppThreat/atom-tools),
the command line toolkit that post-processes the reports of the AppThreat analysis
ecosystem. Every lesson runs real commands against a real target: this repository's
own neighbour, [cdxgen](https://github.com/CycloneDX/cdxgen), the CycloneDX SBOM
generator. The outputs you see in these pages are captured from actual runs on the
cdxgen source tree, not invented for the documentation.

By the end of the course you will be able to do the following, and understand what
each step honestly does and does not claim:

- Generate data flow slices from a JavaScript project with the atom engine, driven
  by `atom-tools analyze`.
- Read the slice formats (reachables, usages) and know which fields are load bearing.
- Triage a slice with `stats`, narrow it with `filter`, and answer the question
  "is this dependency actually used?" with `check-reachable`.
- Draw the flows with `visualize`, including the SBOM reachability review against a
  cdxgen-generated CycloneDX document.
- Extract an OpenAPI document and a SARIF report from slices, and understand what
  each conversion preserves and what it cannot.
- Fold reports from five different engines (atom, dosai, golem, rusi, kosi) into one
  unified flow model with `ingest`, then review that model with `attack-surface`,
  `drift`, `graph`, `explain` and `crypto-reach`.
- Assemble the whole thing into a CI pipeline with gates that fail the build.

## How the course is organised

The lessons are ordered so that each one builds on the previous. The first block
generates the material and teaches the file formats. The second block works the
material by hand. The third block produces artefacts for humans and tools. The
fourth block widens the view from one engine to five. The last lesson assembles
everything into CI.

```text
    Lesson 1      ecosystem, engines, where atom-tools sits
        |
    Lesson 2-3    generate slices on cdxgen, read the formats
        |
    Lessons 4-6   triage: stats, filter, check-reachable, merge, validate
        |
    Lessons 7-9   outputs: visualize, OpenAPI, SARIF
        |
    Lessons 10-15 federation: ingest, attack-surface, drift, graph,
                             explain, crypto-reach
        |
    Lesson 16     the CI assembly line
```

## Following along

You need three things installed: Python 3.10 or newer, Node.js, and git. The
course material was produced with the versions below; later versions should work.

```console
$ python3 --version
Python 3.13.2

$ node --version
v24.16.0
```

Install the tools:

```console
$ pip install atom-tools
$ npm install -g @appthreat/atom
```

atom-tools reads and writes reports. It deliberately never runs an analysis engine
itself, with two exceptions (`analyze` and `apk-analysis`) that drive an engine as
a documented convenience. So atom, the engine that slices JavaScript, Java, Python,
Ruby and friends, is installed separately. The other engines (dosai for .NET,
golem for Go, rusi for Rust, kosi for Kotlin) are only needed for the federation
lessons, and those lessons use the committed fixtures from the atom-tools
repository instead, so nothing else has to be installed to follow along.

Clone the two repositories side by side, then check that both tools answer:

```console
$ git clone https://github.com/AppThreat/atom-tools.git
$ git clone https://github.com/CycloneDX/cdxgen.git
$ atom-tools list
$ atom --help
```

The lessons assume the cdxgen checkout lives at `~/work/cdxgen/cdxgen`. Substitute
your own path wherever you see it. Create a scratch directory for the artefacts,
because the course generates plenty:

```console
$ mkdir -p atom-tools-docs && cd atom-tools-docs
```

## A note on honesty

atom-tools has strong opinions about not inventing facts, and the outputs in this
course show those opinions at work. When a piece of evidence is missing, the tool
says so: reach is reported as "not computed" rather than zero, exposure tiers say
"unknown-auth" rather than guessing "anonymous", a truncated witness is flagged
rather than passed off as complete. Several lessons pause on these moments, because
reading them correctly is the difference between a useful report and a misleading
one.

## Conventions used in the lessons

Console blocks show the command prefixed with `$` and the output below it, exactly
as produced (long outputs are trimmed with a `...` marker). File paths in prose are
relative to the scratch directory. When a lesson uses a committed fixture from the
atom-tools repository, the path starts with `test/data/` and the
[fixtures reference](reference/fixtures.md) records where each fixture came from.
