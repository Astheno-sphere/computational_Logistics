"""Credential-bearing SQL is refused before it runs, and the refusal is narrow.

`run_sql` records its query verbatim in a manifest people are invited to share,
so a credential in the statement is a credential in a published artifact
(issue #18). The first fix was to redact the text; an adversarial audit escaped
it four ways in minutes, one of which redacted the *wrong* argument and kept the
secret. So the statement is refused instead, and redaction stays as a second
layer for the things that reach a manifest without being SQL.

Two halves matter equally here. Refusing the credential statements is the
obvious one. Not refusing honest work is the one that decides whether this
policy survives contact with users: a false positive here does not mangle a
record, it blocks the query.
"""

import pytest

from mapsmith import sql_policy

# Each entry is a real syntax from the audit or from DuckDB's own documentation.
MUST_REFUSE = [
    # the one secret type MapSmith's sandbox can actually construct
    "CREATE SECRET t (TYPE http, EXTRA_HTTP_HEADERS MAP{'Authorization': 'Bearer X'})",
    "CREATE SECRET s (TYPE S3, KEY_ID 'AKIA1', SECRET 'shh')",
    "CREATE OR REPLACE PERSISTENT SECRET s (TYPE S3, SECRET 'shh')",
    "CREATE TEMPORARY SECRET s (TYPE S3, SECRET 'shh')",
    # a comment cannot split the keywords: the audit used exactly this trick
    # against the redaction matcher
    "create /* sneak */ secret s (TYPE S3)",
    "CREATE\n\tSECRET s (TYPE S3)",
    # credential settings, in DuckDB's several spellings
    "SET s3_secret_access_key = 'x'",
    "SET s3_access_key_id='AKIA1'",
    "SET GLOBAL s3_session_token = 'x'",
    "PRAGMA http_proxy_password='x'",
    # ATTACH carrying credentials as an option or as URI userinfo
    "ATTACH 'dbname=x password=shh' AS pg (TYPE postgres)",
    "ATTACH 'postgres://user:shh@host/db' AS pg",
]

# Ordinary work. If any of these ever starts raising, the policy is broken in
# the direction users notice.
MUST_ALLOW = [
    "SELECT * FROM read_parquet('roads.parquet') WHERE name = 'via Roma'",
    "SELECT count(*) FROM ST_Read('zones.gpkg')",
    "CREATE TABLE joined AS SELECT * FROM a JOIN b ON a.id = b.id",
    "SET memory_limit = '2GB'",
    "SET threads = 4",
    # columns and tables whose names merely read like credentials
    "SELECT secret_count, token_type FROM audit_log",
    "SELECT * FROM secrets_inventory WHERE password_age > 90",
    # the word in a string literal, not in a credential position
    "INSERT INTO notes VALUES ('remember the password rotation')",
    # DuckDB's own way of reading credentials from the operator's environment:
    # nothing secret appears in the statement, which is the whole point
    "CALL load_aws_credentials()",
]


@pytest.mark.parametrize("query", MUST_REFUSE)
def test_credential_statements_are_refused(query):
    with pytest.raises(ValueError) as excinfo:
        sql_policy.refuse_credentials_in_sql(query)
    message = str(excinfo.value)
    # the message has to say what to do instead, or the agent retries the same
    # statement and the user sees a loop
    assert "outside the agent's reach" in message
    assert "refuses" in message


@pytest.mark.parametrize("query", MUST_ALLOW)
def test_honest_queries_are_not_refused(query):
    sql_policy.refuse_credentials_in_sql(query)


def test_comments_cannot_hide_a_keyword():
    """Comment stripping is what makes the keyword match trustworthy."""
    assert sql_policy.strip_comments("CREATE /* x */ SECRET s") == "CREATE   SECRET s"
    assert sql_policy.strip_comments("SELECT 1 -- CREATE SECRET\nFROM t") == "SELECT 1  \nFROM t"


def test_the_refusal_names_the_offending_fragment():
    """The message quotes what was matched, so a false positive is diagnosable
    from the error alone rather than by reading this module."""
    with pytest.raises(ValueError, match="CREATE SECRET"):
        sql_policy.refuse_credentials_in_sql("CREATE SECRET s (TYPE S3)")


def test_run_sql_refuses_before_touching_the_engine(tmp_path, monkeypatch):
    """The check must sit in front of execution, not after it: a secret that is
    created and then reported as an error is still a created secret."""
    pytest.importorskip("duckdb")
    from mapsmith.engines import duckdb_engine

    monkeypatch.setattr(
        duckdb_engine, "_connect", lambda: pytest.fail("the engine was reached")
    )
    with pytest.raises(ValueError, match="refuses"):
        duckdb_engine.run_sql(
            "CREATE SECRET t (TYPE http, EXTRA_HTTP_HEADERS MAP{'Authorization': 'Bearer X'})"
        )


def test_persistent_secrets_are_disabled_in_the_connection():
    """Defence in depth for the same leak by a different route: a persistent
    secret is written to ~/.duckdb/stored_secrets — outside any workspace and
    beyond the session. Under a workspace the jail already refuses that write;
    unconfined mode would not, so the setting is applied in both."""
    duckdb = pytest.importorskip("duckdb")
    from mapsmith.engines import duckdb_engine

    con = duckdb_engine._connect()
    assert con.sql("SELECT current_setting('allow_persistent_secrets')").fetchone()[0] is False
    assert con.sql("SELECT current_setting('allow_unredacted_secrets')").fetchone()[0] is False
    # and the configuration lock makes it a policy rather than a default
    with pytest.raises(duckdb.Error):
        con.execute("SET allow_persistent_secrets = true")


# --- extensions: an INSTALL is a native binary, not a setting ----------------


EXTENSION_STATEMENTS = [
    "INSTALL aws; LOAD aws; SELECT * FROM load_aws_credentials()",
    "LOAD httpfs",
    "FORCE INSTALL postgres",
    "install ui",
    "INSTALL azure ; SELECT 1",
    "LOAD 'spatial'",
    "-- harmless\nINSTALL aws",
    "INSTALL /tmp/evil.duckdb_extension",
    # The two an audit walked past on the first version of this policy, both
    # confirmed to reach the real INSTALL/LOAD in DuckDB. The suite was green
    # over an exploitable policy because every case used a canonical spelling.
    #
    # Dollar quoting: the name character class had no `$`.
    "LOAD $$aws$$",
    "INSTALL $$inet$$",
    # A `--` inside a STRING LITERAL. `strip_comments` treated it as a comment
    # and deleted the rest, so the scanner saw `"SELECT ' "` while DuckDB
    # executed all three statements. Not fixable by a better regex: finding
    # statement boundaries in SQL with string literals is parsing.
    "SELECT '--' AS x; LOAD aws; SELECT 1",
    "SELECT '/*' AS x; INSTALL aws",
]


@pytest.mark.parametrize("query", EXTENSION_STATEMENTS)
def test_installing_or_loading_an_extension_is_refused(query):
    """An audit turned this into a credential reader in three statements.

        INSTALL aws; LOAD aws; LOAD httpfs;
        SELECT * FROM load_aws_credentials()

    returned the host's real access key id and session token, in the default
    mode, with no opt-in — while `SECURITY.md` said in the same artifact that
    what remained unconfined was file access "and nothing else".

    None of the layers that existed saw it: `autoload_known_extensions=false`
    stops implicit loading only, `lock_configuration=true` does not stop an
    explicit INSTALL, and the remote-path scan looks for `://` and `/vsi`, which
    `INSTALL postgres` does not contain.
    """
    with pytest.raises(ValueError, match="(?i)extension"):
        sql_policy.refuse_extension_loading_in_sql(query)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1",
        "SELECT * FROM duckdb_extensions()",
        "SELECT payload FROM downloads WHERE name = 'installer'",
        "CREATE TABLE loads AS SELECT 1",
        # These four are the ones that mattered, and the first version of this
        # test had none of them: it stated the principle and exercised only
        # cases that never came close. `load` is an everyday column name —
        # sediment load, nutrient load, traffic load — and all four came back
        # refused as loading an extension called "FROM", "DESC" or "IS".
        "SELECT load FROM sediment",
        "SELECT id FROM t ORDER BY load DESC",
        "SELECT a FROM t WHERE b = 1 AND load IS NULL",
        "SELECT * FROM t WHERE note = 'INSTALL aws'",
    ],
)
def test_ordinary_sql_is_not_refused_for_mentioning_a_word(query):
    """Keyed on the statement, not on a word appearing in it. A guard that
    refuses `SELECT load FROM sediment` teaches its reader to work around it,
    which costs more than the guard is worth."""
    sql_policy.refuse_extension_loading_in_sql(query)


def test_an_extension_statement_after_a_semicolon_is_still_caught():
    """Anchoring to statement position must not create a way past it."""
    with pytest.raises(ValueError, match="(?i)extension"):
        sql_policy.refuse_extension_loading_in_sql("SELECT 1; INSTALL aws")


def test_an_extension_named_in_the_environment_is_allowed(monkeypatch):
    """The decision is a person's, and it is made where the agent cannot reach.

    Named extensions rather than a boolean: "yes, everything" is how a caller
    ends up with the `aws` extension and a credential reader in a process that
    was supposed to do geoprocessing.
    """
    monkeypatch.setenv(sql_policy.ALLOW_EXTENSIONS, "postgres, azure")
    sql_policy.refuse_extension_loading_in_sql("INSTALL postgres")
    sql_policy.refuse_extension_loading_in_sql("LOAD azure")
    with pytest.raises(ValueError, match="(?i)extension"):
        sql_policy.refuse_extension_loading_in_sql("INSTALL aws")


def test_the_refusal_says_how_to_allow_it():
    """A refusal a caller cannot act on is an obstacle, not a check."""
    try:
        sql_policy.refuse_extension_loading_in_sql("INSTALL postgres")
    except ValueError as refusal:
        message = str(refusal)
    assert sql_policy.ALLOW_EXTENSIONS in message
    assert "postgres" in message
    assert "already loaded keep working" in message


@pytest.mark.parametrize(
    "query",
    [
        "INSTALL aws",
        "LOAD aws",
        "LOAD 'aws'",
        'LOAD "aws"',
        "LOAD $$aws$$",
        "FORCE INSTALL aws",
    ],
)
def test_an_allowed_extension_is_allowed_in_every_spelling(query, monkeypatch):
    """The half that catches an over-strict unquote.

    Without stripping the quoting, `LOAD $$aws$$` yields the name `$$aws$$`,
    which is not in the allow-list — so it stays refused, and a test that only
    checks refusal cannot tell a correct policy from one that refuses an
    extension the operator explicitly permitted. Sabotaging `_unquote` left the
    first version of these tests green for exactly that reason.
    """
    monkeypatch.setenv(sql_policy.ALLOW_EXTENSIONS, "aws")
    sql_policy.refuse_extension_loading_in_sql(query)


@pytest.mark.parametrize(
    "query",
    [
        # A `--` inside a STRING LITERAL. `strip_comments` treated it as a
        # comment and deleted the rest, so the scanner saw `"SELECT ' "` for a
        # query that went on to create a secret. Sixth escape, same root cause
        # as the extension bypass found the same day: stripping comments from
        # SQL is parsing, and a scan cannot do it.
        (
            "SELECT '--' AS x; CREATE SECRET s (TYPE http, "
            "EXTRA_HTTP_HEADERS MAP{'Authorization':'Bearer LEAK'})"
        ),
        "SELECT '/*' AS x; CREATE SECRET s (TYPE S3, SECRET 'shh')",
    ],
)
def test_a_comment_marker_inside_a_string_literal_does_not_hide_a_secret(query):
    """The rules now run over the raw text as well as the stripped one.

    Fail closed: if either reading matches, refuse. A credential word inside a
    real comment now costs a caller one rewritten comment; the other direction
    cost a credential.
    """
    with pytest.raises(ValueError, match="(?i)refuses"):
        sql_policy.refuse_credentials_in_sql(query)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT secret_count FROM audit",
        "SET memory_limit = '1GB'",
        "CALL load_aws_credentials()",
        "SELECT 1",
    ],
)
def test_honest_work_still_runs_after_the_raw_text_pass(query):
    """Adding a second pass over the raw text must not start refusing work.

    These four are the cases the module header names as the ones that decide
    whether the policy survives contact with users.
    """
    sql_policy.refuse_credentials_in_sql(query)
