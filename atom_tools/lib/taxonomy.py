"""Shared classification vocabulary for flow engines.

This module owns the tag/severity vocabulary that used to live (as two sets)
in ``sarif.py`` and is now the single taxonomy every engine adapter maps onto:

- ``HIGH_RISK_SINKS`` / ``RULE_TAGS``: chen's tag vocabulary. A flow ending in
  a high risk sink is worth SARIF "error"; any other recognised tag a
  "warning"; everything else "note".
- ``CATEGORY_TO_TAG``: maps the source/sink category names emitted by dosai
  (``Secret``, ``Xxe``, ``Command``, ...), golem (``http-input``,
  ``external-service``, ...), rusi (``param-0``, ``network-request``, ...) and
  kosi (``process-exec``, ``crypto-asset``, ...) onto that same tag
  vocabulary. The vocabulary was taken from the real fixtures in
  ``test/data/ecosystem/`` (see PROVENANCE.md there).
- severity normalisation: engines that emit an explicit severity use
  differing scales (dosai info/low/medium/high/critical, golem lower-case
  medium/high); everything is folded onto the SARIF levels error/warning/note.

``sarif.py`` imports the two sets from here, so derived behaviour is defined
once for atom slices, engine compat slices and the unified model alike.
"""

from typing import Optional, Tuple

# Sink tags that describe a dangerous taint sink. A flow ending in one of these
# is worth an "error" level; other tagged flows get "warning"; untagged flows
# are informational ("note").
HIGH_RISK_SINKS = {
    "sql",
    "code-execution",
    "shell-exec",
    "command-injection",
    "unsafe-deserialization",
    "path-traversal",
    "ssrf",
    "xxe",
    "template-injection",
}

# Sink/source oriented tags (from chen's ChennaiTagsPass vocabulary) used to
# derive a rule id. Everything else still shows up as a plain reachable flow.
RULE_TAGS = HIGH_RISK_SINKS | {
    "http",
    "file-io",
    "reflection",
    "framework-input",
    "framework-output",
    "framework-route",
    "sensitive-data",
    "pii",
    "service-ingress",
    "service-egress",
    "on-device-ai",
    "tracker",
    "adware",
    "ai-prompt",
    "ai-invoke",
    "mcp-input",
}

# Engine category names observed in real dosai/golem/rusi output mapped onto
# the tag vocabulary above. Categories without a natural chen equivalent
# (golem ``panic``, dosai ``redos``, ...) are intentionally absent: they keep
# their engine category on the flow and fall through to the "note" level
# rather than being force-fitted onto a wrong tag.
CATEGORY_TO_TAG = {
    # sources
    "secret": "sensitive-data",
    "pii": "pii",
    "http-input": "framework-input",
    "http-request": "framework-input",
    "framework-route": "framework-route",
    "cli": "cli-source",
    "input": "framework-input",
    "message": "framework-input",
    "parameter": "framework-input",
    "configuration": "framework-input",
    "env": "framework-input",
    "mcp": "mcp-input",
    # sinks
    "sql": "sql",
    "sql-query": "sql",
    "xxe": "xxe",
    "command": "command-injection",
    "command-exec": "command-injection",
    "shell-exec": "shell-exec",
    "process": "code-execution",
    "deserialization": "unsafe-deserialization",
    "unsafe-deserialization": "unsafe-deserialization",
    "path-traversal": "path-traversal",
    "filesystem": "file-io",
    "filesystem-path": "file-io",
    "filesystem-write": "file-io",
    "file-io": "file-io",
    "ssrf": "ssrf",
    "network": "http",
    "network-request": "http",
    "external-service": "service-egress",
    "http": "http",
    "http-response": "framework-output",
    "crypto": "crypto",
    # kosi (Kotlin/JVM) sink/source categories from security-pack-v0 that have
    # an honest home in this vocabulary. The rule used, the same one that
    # keeps rusi's ``param-N`` categories unmapped: map when the existing
    # tag's meaning covers the category's meaning, never when it would
    # re-label the risk or assert a sink where kosi asserts a passthrough.
    # ``code-execution`` and ``template-injection`` need no entry — they are
    # already tags, matched by name in ``category_to_tag``.
    "process-exec": "shell-exec",  # ProcessBuilder/Runtime.exec is the JVM's process-spawn surface
    "crypto-asset": "crypto",  # a crypto API use, exactly what the crypto tag marks
    "hardcoded-secret": "sensitive-data",  # literal secret material (a source category)
    "js-injection": "code-execution",  # its only sink, WebView.evaluateJavascript, executes the JS
    "log-injection": "log",  # the tag the log category exists for
    "prompt-injection": "ai-prompt",  # untrusted text into an LLM prompt sink
}

# Tags that exist in the shared vocabulary but not in chen's set. Adding them
# here (rather than to RULE_TAGS) keeps atom-slice rule derivation identical
# to before; they are only reachable through engine category mapping.
EXTENDED_RULE_TAGS = RULE_TAGS | {"crypto", "cli-source", "log", "xss"}

# dosai (info/low/medium/high/critical) and golem (lower-case) severity words
# folded onto SARIF levels.
ENGINE_SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "moderate": "warning",
    "low": "note",
    "info": "note",
    "informational": "note",
    "error": "error",
    "warning": "warning",
    "note": "note",
}


def normalise_engine_severity(value) -> Optional[str]:
    """Fold an engine severity word onto error/warning/note (case-insensitive)."""
    if not value or not isinstance(value, str):
        return None
    return ENGINE_SEVERITY_TO_LEVEL.get(value.strip().lower())


def category_to_tag(category) -> Optional[str]:
    """Map an engine source/sink category onto the shared tag vocabulary."""
    if not category or not isinstance(category, str):
        return None
    lowered = category.strip().lower()
    if lowered in EXTENDED_RULE_TAGS:
        return lowered
    return CATEGORY_TO_TAG.get(lowered)


def derive_level_and_tag(source_category, sink_category) -> Tuple[str, Optional[str]]:
    """
    Derive a (level, tag) pair from engine categories for engines that do not
    emit a severity (atom, rusi).

    Same semantics as ``sarif.rule_for``: a high risk sink tag is an error,
    any other recognised tag a warning, everything else a note. The sink
    category wins over the source category, mirroring how ``rule_for`` treats
    the terminal node of a flow.
    """
    for category in (sink_category, source_category):
        tag = category_to_tag(category)
        if tag and tag in HIGH_RISK_SINKS:
            return "error", tag
    for category in (sink_category, source_category):
        tag = category_to_tag(category)
        if tag:
            return "warning", tag
    return "note", None
