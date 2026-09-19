"""Crypto-reach Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command

logger = logging.getLogger(__name__)

FORMATS = ("text", "json")


class CryptoReachCommand(Command):
    """
    This command joins a report's crypto inventory to entry-point
    reachability — the question cdxgen's CBOM cannot answer: is this weak
    algorithm on a path an entry point reaches? The join runs per engine at
    the granularity each engine's evidence supports (dosai record-level
    engine verdicts, rusi function-level, golem package-level), and every
    rendering states which one it is using. No cross-engine headline: three
    granularities do not sum.
    """

    name = "crypto-reach"
    description = (
        "Join crypto inventory (weak algorithms, key material, findings) to"
        " entry-point reachability, per engine, at the granularity each"
        " engine's evidence supports."
    )
    options = [
        option(
            "input-slice",
            "i",
            "Report file(s): dosai crypto, golem analyze (--dataflow"
            " crypto|all), rusi analyze, or mixed. Atom slices and unified"
            " documents carry no crypto section and are reported as out of"
            " scope. Comma separated lists and globs are supported.",
            flag=False,
            value_required=True,
        ),
        option(
            "format",
            "f",
            f"Output format: {', '.join(FORMATS)}. 'text' lists the triage"
            " population with per-item reach verdicts; 'json' carries the"
            " whole inventory.",
            flag=False,
            default="text",
            value_required=True,
        ),
        option(
            "output-file",
            "o",
            "Write the output here instead of the console.",
            flag=False,
            default="",
            value_required=True,
        ),
        option(
            "weak-only",
            None,
            "Keep only the triage population: weak/legacy-strength items and"
            " findings that are not literal-material inventory.",
        ),
        option(
            "max-entries",
            None,
            "Maximum items listed in the text rendering (the remainder is"
            " counted in a 'truncated' marker; json carries everything).",
            flag=False,
            default="40",
            value_required=True,
        ),
    ]
    help = """Is this weak algorithm actually reachable?

golem can tell you MD5 is present (crypto.findings), dosai can tell you a
weak cipher hangs off POST /api/authenticate, and rusi can tell you where key
material is constructed. What no engine tells you in one view is which of
those crypto sites sit behind an entry point — attack-surface ∩ crypto — and
that join is only honest per engine, because the engines leave it at three
different granularities:

  dosai   record-level, engine-reported. The crypto command carries
          ReachableFromEntryPoint and EntryPointIds on every record; they are
          rendered verbatim, the way attack-surface takes dosai's
          AttackSurface array rather than recomputing it worse.
  rusi    function-level, derived. Materials carry their enclosing function;
          it is anchored in the call graph (the attack-surface anchor chain,
          reused) and tested against every anchored endpoint's closure. On
          the committed fixture 0 of 17 materials sit in an endpoint closure
          — they hang off event dispatchers, main and background listeners —
          and the static callers are printed so the reader sees why.
  golem   package-level at best, derived. Its crypto items carry no
          enclosing-function field, so the claim supported is 'this site
          sits in a package that carries tainted flows' — never 'this call
          is on a tainted path'. Every golem rendering says the weaker
          sentence.

rusi's zero components/findings are reported as what they are — a fixed
symbol catalog (SHA-2, MD5, BLAKE3, ring, AES-GCM, ChaCha20-Poly1305, JWT,
TLS, RSA, Ed25519) matched nothing, and its only weak-crypto rules are SHA-1
and MD5; DES/RC4/ECB are not modeled. 'rusi does not look for this', not
'rusi found nothing'.

atom inputs are out of scope (atom emits no crypto section), and unified
documents carry no crypto payload by design — both are said out loud rather
than silently producing an empty report."""
    loggers = [
        "atom_tools.lib.adapters",
        "atom_tools.lib.attack_surface",
        "atom_tools.lib.crypto_reach",
        "atom_tools.lib.unified",
        "atom_tools.lib.utils",
    ]

    def handle(self):
        """Executes the crypto-reach command."""
        import json

        from atom_tools.lib.adapters import parse_report
        from atom_tools.lib.attack_surface import SurfaceInput, is_usages_slice
        from atom_tools.lib.crypto_reach import compute_crypto_reach, render_console
        from atom_tools.lib.reachables import expand_inputs, load_json_report

        output_format = self.option("format")
        if output_format not in FORMATS:
            raise ValueError(f"Unknown format: {output_format}. Known: {', '.join(FORMATS)}")
        try:
            max_entries = max(1, int(self.option("max-entries")))
        except ValueError:
            raise ValueError(f"Invalid --max-entries: {self.option('max-entries')}") from None

        files = expand_inputs(self.option("input-slice"))
        if not files:
            # expand_inputs has already warned about every unmatched part.
            return 1
        inputs = []
        for path in files:
            content = load_json_report(path)
            if is_usages_slice(content):
                inputs.append(SurfaceInput(report=None, raw=content, path=path))
                continue
            inputs.append(
                SurfaceInput(
                    report=parse_report(content, source_file=path),
                    raw=content,
                    path=path,
                )
            )

        document = compute_crypto_reach(inputs, weak_only=bool(self.option("weak-only")))
        if self.option("output-file"):
            with open(self.option("output-file"), "w", encoding="utf-8") as f:
                if output_format == "json":
                    json.dump(document, f, indent=4, sort_keys=True)
                    f.write("\n")
                else:
                    f.write("\n".join(render_console(document, max_entries)) + "\n")
            self.line(
                f"<info>Crypto reach over {len(files)} input(s) written to"
                f" {self.option('output-file')}.</info>"
            )
            return 0
        if output_format == "json":
            self.line(json.dumps(document, indent=4, sort_keys=True))
        else:
            for line in render_console(document, max_entries):
                self.line(line)
        return 0
