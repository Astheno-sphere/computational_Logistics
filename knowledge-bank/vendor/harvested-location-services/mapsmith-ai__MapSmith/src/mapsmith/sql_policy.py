"""Refuse agent-written SQL that carries a credential, instead of redacting it.

Issue #18 started from a manifest leak: ``run_sql`` records the query verbatim,
manifests are meant to be shared, so ``CREATE SECRET (... SECRET 'AKIA…')``
ended up in an artifact this project encourages people to attach to a bug
report. The first fix was redaction — mask the value, keep the statement
readable — and an adversarial audit took it apart in minutes. Measured against
the shipped 0.2.1 matcher, all four of these left the secret in the manifest:

    CREATE SECRET t (TYPE http, EXTRA_HTTP_HEADERS MAP{'Authorization': 'Bearer X'})
    CREATE SECRET s (TYPE S3, SECRET E'shh\\'x')      -- escaped-string literal
    CREATE SECRET s (TYPE S3, SECRET $$shh$$)         -- dollar quoting
    CREATE SECRET s (TYPE S3, SECRET /* c */ 'shh')   -- comment between the two

The second one is worse than a miss: the ``E'`` prefix desynchronises the quote
pairing, so the matcher redacted a *different* argument and kept the secret —
a manifest that is both wrong and leaky. That is the shape of the problem:
redaction is a text scan without a SQL parser, and every dialect has one more
way to write a string. Chasing them one at a time is a losing race, so the
statement itself is refused before it runs and there is nothing left to redact.

What that costs: nothing documented. No README, doc page or notebook shows
credentials being configured through ``run_sql``, and in MapSmith's sandbox
exactly one secret type is even constructible (``http`` — extension autoloading
is off, so ``TYPE s3``/``azure``/``postgres`` fail with "does not exist"). What
it protects is the case that matters: a credential the *user* pasted into the
chat, which the model then writes into SQL, which MapSmith writes into a file
meant to be published.

Redaction stays in ``provenance.redact_secrets`` as a second layer, because a
credential can reach a manifest through a parameter that is not SQL at all.
"""

from __future__ import annotations

import re

# `--` to end of line, and `/* ... */` including newlines. Removed before
# matching so `CREATE /*x*/ SECRET` cannot walk past the check — the audit used
# exactly that trick against the redaction matcher.
_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)

# Fragments that make a setting name credential-bearing. Kept as fragments
# rather than a fixed list of settings: DuckDB moves these between releases
# (in 1.5.5 the s3_* settings are gone from duckdb_settings() and live in the
# secrets manager instead), and a stale allow-list fails open.
_CREDENTIAL_WORDS = (
    "secret", "password", "passwd", "pwd", "passphrase", "token", "key_id",
    "access_key", "credential", "authorization", "sas", "signature",
    "client_secret", "private_key", "connection_string", "conninfo",
)
_WORDS = "|".join(_CREDENTIAL_WORDS)

#: A credential word is allowed a trailing component, from a closed list. Without
#: it `SET s3_secret_key = '...'` passed this layer: the prefix could not eat
#: `s3_secret_` because `key` alone is not a credential word, and `secret` was
#: not followed by a word boundary. `s3_secret_access_key` -- the setting that
#: actually exists -- was caught, so this is depth rather than a live hole; but
#: the redaction matcher in `provenance.py` has the same allowance for the same
#: reason, and two layers written from one idea should not disagree about which
#: names are credentials.
_TAIL = r"(?:[_.\-]?(?:key|keys|value|values|pem|der|jwt|base64|b64))*"

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # CREATE [OR REPLACE] [PERSISTENT|TEMPORARY] SECRET [IF NOT EXISTS] name (...)
    (re.compile(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:PERSISTENT\s+|TEMPORARY\s+|TEMP\s+)?SECRET\b"),
     "a DuckDB secret"),
    # SET / PRAGMA of a credential-bearing setting, in any of DuckDB's spellings
    # The optional quoting character before the name is load-bearing: DuckDB
    # accepts a quoted identifier, and without it the opening quote broke the
    # contiguity with the credential word, so `SET "s3_secret_access_key" = '…'`
    # passed BOTH layers — neither refused nor redacted. Fifth escape found by
    # an audit, and it fell under neither documented limit: the name was
    # perfectly recognisable, the statement did configure a credential.
    (re.compile(rf"""(?i)\b(?:SET|PRAGMA)\s+(?:GLOBAL\s+|SESSION\s+|LOCAL\s+)?(?:VARIABLE\s+)?["`\[]?[A-Za-z0-9_.]*(?:{_WORDS}){_TAIL}\b"""),
     "a credential setting"),
    # ATTACH with credentials, either as an option or as URI userinfo
    (re.compile(rf"(?i)\bATTACH\b[^;]*?(?:\b(?:{_WORDS})\b\s*(?::=|=)|://[^\s:/@]+:[^\s@/]+@)"),
     "an ATTACH carrying credentials"),
)


#: The environment variable that allows named extensions to be installed and
#: loaded from a statement. Named extensions, not a boolean: "yes, everything"
#: is how a caller ends up with the `aws` extension and a credential reader in a
#: process that was supposed to do geoprocessing.
ALLOW_EXTENSIONS = "MAPSMITH_ALLOW_EXTENSIONS"

#: `INSTALL name` / `LOAD name`, in DuckDB's spellings. `FORCE INSTALL` is one,
#: and the name can be quoted or a path to a local `.duckdb_extension` file.
#: Anchored to STATEMENT position — start of input, or after a semicolon. The
#: first version matched the word anywhere, so `SELECT load FROM sediment` came
#: back refused as loading an extension called "FROM", and so did `ORDER BY load
#: DESC` and a string literal mentioning INSTALL. `load` is an everyday column
#: name: sediment load, nutrient load, traffic load. A guard that refuses
#: ordinary work teaches its reader to route around it, which costs more than
#: the guard is worth — and the test that stated exactly that principle had four
#: cases, none of which exercised it.
_EXTENSION_STATEMENT = re.compile(
    r"""(?im)(?:^|;)\s*(?:FORCE\s+)?(INSTALL|LOAD)\s+(?:["'`]?)([A-Za-z0-9_.:/\-]+)"""
)


def allowed_extensions() -> frozenset[str]:
    """The extensions this process may install or load, from the environment.

    Empty by default. Set `MAPSMITH_ALLOW_EXTENSIONS=postgres,azure` to allow
    exactly those two, in the environment of the process that starts the server
    — which is outside the agent's reach, and that is the point.
    """
    import os

    raw = os.environ.get(ALLOW_EXTENSIONS, "")
    return frozenset(
        name.strip().lower() for name in raw.split(",") if name.strip()
    )


def _extension_statements(query: str) -> list[tuple[str, str]]:
    """Every INSTALL/LOAD in this SQL, as (verb, extension name).

    Uses **DuckDB's own parser**, not a scan, because a scan lost twice on the
    same statement in one day. The first version was a regex over
    `strip_comments(query)`, and an audit walked past it two ways:

        LOAD $$aws$$                          the name class had no `$`
        SELECT '--' AS x; LOAD aws; SELECT 1  strip_comments saw the `--` INSIDE
                                              the string literal, deleted the
                                              rest, and handed the scanner
                                              "SELECT ' " while DuckDB executed
                                              all three statements

    The second one is the deeper hole and it is not fixable by a better regex:
    finding statement boundaries in SQL that has string literals and dollar
    quoting is parsing, and there is a parser right here. `extract_statements`
    classifies both cases as `StatementType.LOAD` and leaves
    `SELECT load FROM sediment` a SELECT, which is the false positive a scan
    also produced.

    Fails CLOSED. If the parser cannot read the SQL, the statement will fail in
    DuckDB anyway, but a regex backstop still runs — an unparseable query is not
    a reason to stop looking.
    """
    import duckdb

    found: list[tuple[str, str]] = []
    try:
        statements = duckdb.extract_statements(query)
    except Exception:  # noqa: BLE001 - unparseable SQL: fall back, do not pass
        statements = None

    if statements is not None:
        for statement in statements:
            # DuckDB reports INSTALL and LOAD under one statement type.
            if not str(statement.type).endswith("LOAD"):
                continue
            match = _EXTENSION_NAME.search(statement.query)
            if match:
                found.append((match.group(1).upper(), _unquote(match.group(2))))
        return found

    for match in _EXTENSION_STATEMENT.finditer(strip_comments(query)):
        found.append((match.group(1).upper(), _unquote(match.group(2))))
    return found


def _unquote(name: str) -> str:
    """The extension name without whatever was wrapped around it."""
    stripped = name.strip()
    for opening, closing in (("$$", "$$"), ("'", "'"), ('"', '"'), ("`", "`")):
        if stripped.startswith(opening) and stripped.endswith(closing) and len(
            stripped
        ) > len(opening) + len(closing) - 1:
            return stripped[len(opening) : -len(closing)]
    return stripped


#: The name inside a single INSTALL/LOAD statement the parser has already
#: isolated. Wider than the scanning pattern on purpose: the statement boundary
#: is no longer this expression's problem, so it can accept dollar quoting.
_EXTENSION_NAME = re.compile(
    r"""(?i)\b(?:FORCE\s+)?(INSTALL|LOAD)\s+(\$\$[^$]*\$\$|["'`][^"'`]*["'`]|[A-Za-z0-9_.:/\-]+)"""
)


def refuse_extension_loading_in_sql(query: str) -> None:
    """Raise if the statement would install or load a DuckDB extension.

    An `INSTALL` is an HTTPS fetch of a **native binary** from
    `extensions.duckdb.org`, executed in this process. It was allowed by default
    in unconfined mode, and `SECURITY.md` said in the same artifact that what
    remained unconfined was file access "and nothing else". An audit used it to
    make `run_sql` return this machine's real cloud credentials:

        INSTALL aws; LOAD aws; LOAD httpfs;
        SELECT * FROM load_aws_credentials()

    None of the existing layers saw it. `autoinstall_known_extensions=false`
    stops *implicit* loading only; `lock_configuration=true` does not stop an
    explicit `INSTALL`; and the remote-path scan looks for `://` and `/vsi`,
    which `INSTALL postgres` does not contain.

    So the answer is not a better scan but a decision that belongs to a person:
    either the extension is already loaded, or somebody says which ones may be.
    `spatial` is unaffected — MapSmith loads it through the Python API before
    the configuration is locked, so no statement has to ask for it.
    """
    allowed = allowed_extensions()
    for verb, name in _extension_statements(query):
        if name.lower() in allowed:
            continue
        raise ValueError(
            f"this SQL would {verb} the DuckDB extension {name!r}, which MapSmith "
            f"refuses. An INSTALL downloads a native binary and runs it in this "
            f"process, and the statement was written by a model rather than by "
            f"you. "
            f"If you want it, say so where the agent cannot: start the server with "
            f"{ALLOW_EXTENSIONS}={name} in its environment (comma-separated for "
            f"more than one). Extensions already loaded keep working — this "
            f"refuses acquiring new ones, not using what is there."
        )


def strip_comments(query: str) -> str:
    """SQL with comments replaced by a space, so tokens cannot be split by one."""
    return _COMMENTS.sub(" ", query)


def refuse_credentials_in_sql(query: str) -> None:
    """Raise if the statement would set a credential. Silent otherwise.

    Keyed on the *shape* of the statement, never on what a value looks like: an
    honest ``SELECT secret_count FROM audit`` is not refused, and a credential
    that happens to look innocuous is still refused. Value-shaped detection is
    what made the redaction matcher lose.
    """
    # imported here, not at module level: provenance imports the package root,
    # and this module is pulled in early by the engines
    from .provenance import redact_secrets

    # Both the comment-stripped text AND the raw text, because stripping
    # comments cannot be done by a scan without a parser: a `--` inside a
    # STRING LITERAL made this scanner see `"SELECT ' "` for a query that went
    # on to create a secret, so `SELECT '--' AS x; CREATE SECRET ...` was not
    # refused. Fail closed — if either reading matches, refuse. The raw text can
    # produce a false positive on a credential word inside a comment, which
    # costs a caller one rewritten comment; the other direction costs a
    # credential.
    for text in (strip_comments(query), query):
        for pattern, what in _RULES:
            match = pattern.search(text)
            if not match:
                continue
            # The ATTACH rule matches through the URI userinfo, so the quoted
            # fragment carried the password into the error message — and from
            # there onto disk, since a plan manifest records step errors. The
            # message that refuses a credential must not be how it escapes.
            quoted = redact_secrets(match.group(0).strip())
            raise ValueError(
                f"this SQL configures {what} ({quoted!r}), which MapSmith "
                "refuses: the statement is written by the model and recorded verbatim in "
                "the provenance manifest, which is meant to be shared. Configure "
                "credentials outside the agent's reach — in the environment of the process "
                "that starts the server — rather than in a statement a tool call can carry."
            )
