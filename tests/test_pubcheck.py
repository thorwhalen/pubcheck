"""Tests for pubcheck. No network: visibility from a temporary priv-format cache, the vocabulary from a file, no ``gh`` or ``acquaint`` on ``PATH`` (a fake ``gh`` where a test needs one)."""

import getpass
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pubcheck import check, findings
from pubcheck import detectors as d
from pubcheck import sources as s
from pubcheck.base import STATE_DIR_ENV, CACHE_DIR_ENV, settings
from pubcheck.correspond import make_before_send
from pubcheck.hold import file_hold, hold_body

VOCAB = [
    {"term": "Ada Quill", "entity": "person:ada-quill"},
    {"term": "adaq", "entity": "person:ada-quill"},
    {"term": "candidate", "entity": "person:ada-quill"},
    {"term": "AQ", "entity": "person:ada-quill"},
    {"term": "Heronworks", "entity": "org:heronworks"},
    {"term": "heronworks-org", "entity": "org:heronworks"},
    {"term": "miles", "entity": "person:bo-miles"},
    {"term": "octo", "entity": "person:me-twin"},
    {"term": "me.twin@example.org", "entity": "person:me-twin"},
]
PUBLIC, PRIVATE = "octo/app", "octo/secretproj"
CONFIG = """private_owner = "octo"
private_issues = "octo/_private-issues"
private_patterns = ['\\b_agent_work\\b', '\\bwork/proj\\b']
"""
TOKEN = "ghp_" + "A1" * 18


@pytest.fixture
def env(tmp_path, monkeypatch):
    vis, state = tmp_path / "vis", tmp_path / "state"
    vis.mkdir()
    (tmp_path / "vocab.json").write_text(json.dumps(VOCAB))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv(s.VISIBILITY_CACHE_ENV, str(vis))
    monkeypatch.setenv(s.VOCAB_FILE_ENV, str(tmp_path / "vocab.json"))
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    monkeypatch.setenv(CACHE_DIR_ENV, str(tmp_path / "cache"))
    (tmp_path / "config.toml").write_text(CONFIG)
    monkeypatch.setenv("PUBCHECK_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setattr(s, "ACQUAINT_CANDIDATES", ())  # no acquaint: the vocabulary is the file's
    import pubcheck.core as core
    if not d.dictionary_words():  # a runner with no word list: unattended checks need one
        monkeypatch.setattr(core, "dictionary_words", lambda: frozenset({"word"}))

    def set_visibility(slug, private, *, age=0):
        remote = f"git@github.com:{slug}.git"
        (vis / f"{s.cache_key(remote)}.json").write_text(json.dumps(
            {"remote": remote, "slug": slug, "is_private": private, "checked_at": time.time() - age}))

    set_visibility(PUBLIC, False)
    set_visibility(PRIVATE, True)

    class E:
        root = tmp_path
        bin = bin_dir

        @staticmethod
        def events():
            f = state / "events.jsonl"
            return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    E.set_visibility = staticmethod(set_visibility)
    return E


def cats(text, *, detectors=d.DETECTORS, **ctx):
    return {c for c, _ in findings([text], ctx, detectors=detectors)}


# ---- detectors ----


def test_owner_relation():
    for text in ["As the owner asked, we", "the user's correction was", "my agents found",
                 "per the operator", "the owner stated it", "the operator\nstated it"]:
        assert cats(text) == {"owner-relation"}, text
    for text in ["the user types a query", "the user's email address field", "the operator module",
                 "If the human said stop", "our clients reconnect on 503", "the owner's projects",
                 'write "my agents checked" in their register', "`the owner stated`"]:
        assert cats(text) == set(), text


def test_private_refs_and_session_links():
    ctx = {"repo": "octo/dol", "private_slugs": ["octo/vault", "octo/dol"]}
    assert cats("see octo/vault#139", **ctx) == {"private-ref"}
    assert cats("this is octo/dol", **ctx) == set()
    mine = {"private_owner": "octo", "private_patterns": [r"\b_agent_work\b", r"\bwork/proj\b"]}
    for text in ["$PP/_agent_work/x/report.md", f"/Users/{getpass.getuser()}/proj",
                 "octo/_app#3", "~/work/proj/t/x"]:
        assert cats(text, **mine) == {"private-ref"}, text
    assert cats("octo/_app#3 and $PP/_agent_work") == set()  # not configured: not known
    for text in ["File /home/runner/work/acquaint/x.py", "/Users/runner/work", "/root/.cache/pip"]:
        assert cats(text) == set(), text
    link = "https://claude.ai/code/session_01ABC"
    assert cats(link) == {"session-link"}
    assert cats(link, surface="git commit") == set()


def test_registry_terms():
    terms = s.terms_for(VOCAB, "octo/dol")
    assert "Ada Quill" in terms and "AQ" not in terms
    if d.dictionary_words():
        assert "candidate" not in terms and "miles" not in terms
    assert "Heronworks" not in s.terms_for(VOCAB, "heronworks-org/tool")
    ctx = {"terms": terms}
    assert cats("Thanks to Ada Quill", **ctx) == {"registry"}
    assert cats("ping @adaq", **ctx) == {"registry"}
    assert cats("the heronworks pipeline", **ctx) == {"registry"}
    assert cats("thanks Ada\n  Quill", **ctx) == {"registry"}
    assert "octo" not in terms and "me.twin@example.org" in terms


def test_credentials_name_the_pattern_never_the_secret():
    hits = findings([f"token: {TOKEN}"], {})
    assert ("credential", "github_token") in hits
    assert all(TOKEN not in term for _, term in hits)
    assert cats("password: hunter2") == set()


def test_mentions_only_unattended_and_outside_code():
    u = d.UNATTENDED_DETECTORS
    assert cats("thanks @octocat") == set()  # attended: the author chose to notify
    assert cats("thanks @octocat", detectors=u) == {"mention"}
    assert findings(["cc @octo-org/core-team"], {}, detectors=u) == [("mention", "@octo-org/core-team")]
    for text in ["mail me@example.org", "see `@octocat`", "```\n@decorator\n```", "pkg@1.2.3"]:
        assert cats(text, detectors=u) == set(), text
    for text in ["-@octocat", "x/@octocat", "end.@octocat", "(@octocat)"]:  # GitHub notifies these
        assert cats(text, detectors=u) == {"mention"}, text


# ---- the check ----


RELAYED = ("The parser now keeps trailing commas.\n\n"
           "The operator stated this preference after the last release.")


def test_public_flags_private_passes(env):
    v = check(RELAYED, repo=PUBLIC)
    assert (v.decision, v.visibility, v.exit_code) == ("flag", "public", 1)
    assert "owner-relation" in v.categories and "`octo/_private-issues`" in v.destination
    v = check(RELAYED, repo=PRIVATE)
    assert (v.decision, v.visibility, v.findings) == ("pass", "private", [])
    assert check("Fixed the parser.", repo=PUBLIC).decision == "pass"


def test_unknown_visibility_is_public(env):
    v = check("Ada Quill found it", repo="nobody/never-seen")
    assert (v.decision, v.visibility) == ("flag", "unknown")
    assert check("Ada Quill found it").decision == "flag"  # no repo at all


def test_title_is_checked(env):
    assert check("body", title="Ada Quill's bug", repo=PUBLIC).categories == ["registry"]


def test_unattended_fails_closed_without_registry(env, monkeypatch):
    monkeypatch.setenv(s.VOCAB_FILE_ENV, str(env.root / "missing.json"))
    assert check("Fixed it.", repo=PUBLIC).decision == "pass"  # attended: proceeds, logged
    assert env.events()[-1]["decision"] == "registry-unavailable"
    v = check("Fixed it.", repo=PUBLIC, unattended=True)
    assert (v.decision, v.exit_code) == ("unavailable", 2)
    # unattended asks GitHub, never the cache: without gh, the cached "private" is unknown
    assert check("Fixed it.", repo=PRIVATE, unattended=True).decision == "unavailable"
    fake_gh(env)
    assert check("Fixed it.", repo=PRIVATE, unattended=True).decision == "pass"


def test_empty_or_old_registry_is_unavailable(env, monkeypatch):
    (env.root / "empty.json").write_text("[]")
    monkeypatch.setenv(s.VOCAB_FILE_ENV, str(env.root / "empty.json"))
    assert check("Fixed it.", repo=PUBLIC, public=True, unattended=True).decision == "unavailable"
    monkeypatch.delenv(s.VOCAB_FILE_ENV)
    cache = env.root / "cache" / "vocabulary.json"
    cache.parent.mkdir(parents=True)
    old = time.time() - s.VOCAB_MAX_AGE - 5
    cache.write_text(json.dumps({"checked_at": old, "vocabulary": VOCAB}))
    assert check("Fixed it.", repo=PUBLIC, public=True, unattended=True).decision == "unavailable"
    cache.write_text(json.dumps({"checked_at": time.time() - s.VOCAB_TTL - 5, "vocabulary": VOCAB}))
    assert check("Ada Quill", repo=PUBLIC, public=True, unattended=True).decision == "flag"  # young enough


def test_unattended_needs_the_operator_config_and_a_word_list(env, monkeypatch):
    import pubcheck.core as core
    monkeypatch.setenv("PUBCHECK_CONFIG", str(env.root / "none.toml"))
    v = check("Fixed.", repo=PUBLIC, public=True, unattended=True)
    assert v.decision == "unavailable" and "private_owner" in v.reason
    assert check("Fixed.", repo=PUBLIC, public=True).decision == "pass"  # attended: fine
    monkeypatch.setenv("PUBCHECK_CONFIG", str(env.root / "config.toml"))
    monkeypatch.setattr(core, "dictionary_words", lambda: frozenset())
    assert "word list" in check("Fixed.", repo=PUBLIC, public=True, unattended=True).reason


def test_an_empty_cached_vocabulary_is_not_trusted(env, monkeypatch):
    monkeypatch.delenv(s.VOCAB_FILE_ENV)
    cache = env.root / "cache" / "vocabulary.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"checked_at": time.time(), "vocabulary": []}))
    assert s.vocabulary(budget=__import__("pubcheck.base").base.Budget(1)) == ([], False)


def test_unattended_ignores_override_and_caps_length(env):
    assert check("Ada Quill", repo=PUBLIC, public=True, unattended=True, override="x").decision == "flag"
    v = check("a" * 80_000, repo=PUBLIC, public=True, unattended=True)
    assert v.decision == "unavailable" and "longer than" in v.reason


def test_an_error_is_unavailable_and_never_echoes_its_message(env):
    def broken(text, ctx):
        raise RuntimeError(f"cannot parse {text}")

    v = check("Ada Quill", repo=PUBLIC, detectors=(broken,))
    assert (v.decision, v.exit_code) == ("unavailable", 2) and "RuntimeError" in v.reason
    assert "Ada" not in json.dumps(v.to_json()) + (env.root / "state" / "events.jsonl").read_text()


def test_out_of_budget_still_decides(env):
    v = check("Ada Quill", repo="nobody/new", budget=0)
    assert v.decision == "flag"


def test_override_is_logged_with_reason(env):
    v = check("Ada Quill", repo=PUBLIC, override="a public author")
    assert v.decision == "override" and v.exit_code == 0
    (event,) = env.events()
    assert (event["decision"], event["reason"], event["categories"]) == ("override", "a public author", ["registry"])


def test_log_is_private_and_holds_no_text(env):
    check(f"Ada Quill {TOKEN}", repo=PUBLIC)
    f = env.root / "state" / "events.jsonl"
    assert (f.stat().st_mode & 0o777, f.parent.stat().st_mode & 0o777) == (0o600, 0o700)
    assert "Ada" not in f.read_text() and TOKEN not in f.read_text()


def test_json_never_holds_the_text(env):
    v = check(f"Ada Quill {TOKEN}", repo=PUBLIC)
    out = json.dumps(v.to_json())
    assert "Ada" not in out and TOKEN not in out
    assert ["registry", "Ada Quill"] in v.to_json(terms=True)["findings"]


def test_destination_names_the_companion(env):
    env.set_visibility("octo/_app", True)
    assert "`octo/_app`" in check("Ada Quill", repo=PUBLIC).destination


def test_unconfigured_destination_is_generic(env, monkeypatch):
    monkeypatch.setenv("PUBCHECK_CONFIG", str(env.root / "none.toml"))
    assert check("Ada Quill", repo=PUBLIC).destination == "a private repo"


# ---- the CLI ----


def cli(*args, stdin="", env_=None):
    return subprocess.run([sys.executable, "-m", "pubcheck", "check", *args], input=stdin,
                          capture_output=True, text=True, env=env_ or os.environ.copy())


def test_cli_contract(env):
    r = cli("--repo", PUBLIC, stdin="Ada Quill said so")
    out = json.loads(r.stdout)
    assert (r.returncode, out["decision"], out["categories"]) == (1, "flag", ["registry"])
    assert "Ada" not in r.stdout
    assert cli("--repo", PUBLIC, stdin="Fixed the parser.").returncode == 0
    assert cli("--repo", PRIVATE, stdin="Ada Quill").returncode == 0
    r = cli("--repo", PUBLIC, "--unattended", stdin="thanks @octocat")
    assert (r.returncode, json.loads(r.stdout)["categories"]) == (1, ["mention"])
    os.environ[s.VOCAB_FILE_ENV] = str(env.root / "missing.json")
    assert cli("--repo", PUBLIC, "--unattended", stdin="Fixed.").returncode == 2


def test_cli_terms_on_request(env):
    out = json.loads(cli("--repo", PUBLIC, "--terms", stdin="Ada Quill").stdout)
    assert out["findings"] == [["registry", "Ada Quill"]]


# ---- the desk hold ----


def fake_gh(env, *, private="true", fail=False):
    """A ``gh`` that answers ``repo view`` and records ``issue create`` (stdin and argv)."""
    log = env.root / "gh.log"
    script = env.bin / "gh"
    script.write_text(f"""#!/bin/sh
echo "$@" >> {log}
case "$1 $2" in
  "repo view") echo {private} ;;
  "issue list") echo "" ;;
  "issue create") {"exit 1" if fail else "true"}; cat >> {log}; echo https://github.com/octo/_desk/issues/99 ;;
esac
""")
    script.chmod(0o755)
    return log


def test_file_hold_files_in_a_private_repo_without_credentials(env):
    log = fake_gh(env)
    text = f"Ada Quill asked; token: {TOKEN}"
    v = check(text, repo=PUBLIC, unattended=True)
    res = file_hold(v, target=f"github:{PUBLIC}", text=text, title=f"T {TOKEN}", config={"hold_repo": "octo/_desk"})
    assert res == {"filed": True, "url": "https://github.com/octo/_desk/issues/99", "repo": "octo/_desk"}
    calls = log.read_text()
    assert "issue create -R octo/_desk --title held: github:octo/app: T [credential redacted" in calls
    from pubcheck.hold import hold_key
    assert "--label escalate" in calls and "Ada Quill asked" in calls
    assert hold_key(v, f"github:{PUBLIC}") in calls and TOKEN not in calls


def test_file_hold_needs_a_configured_repo(env):
    log = fake_gh(env)
    v = check("Ada Quill", repo=PUBLIC, unattended=True)
    assert file_hold(v, target="x", text="Ada Quill") == {"filed": False, "reason": "no hold_repo is configured"}
    assert "issue create" not in log.read_text()


def test_file_hold_asks_github_not_the_cache(env):
    log = fake_gh(env, private="false")
    env.set_visibility("octo/_desk", True)  # a stale or planted cache entry says private
    v = check("Ada Quill", repo=PUBLIC, unattended=True)
    assert not file_hold(v, target="x", text="Ada Quill", config={"hold_repo": "octo/_desk"})["filed"]
    assert "issue create" not in log.read_text()


def test_file_hold_refuses_a_public_hold_repo(env):
    log = fake_gh(env, private="false")
    v = check("Ada Quill", repo=PUBLIC, unattended=True)
    res = file_hold(v, target="x", text="Ada Quill", config={"hold_repo": "octo/public"})
    assert not res["filed"] and "not known to be private" in res["reason"]
    assert "issue create" not in log.read_text()


def test_hold_body_names_categories():
    from pubcheck.core import Verdict
    from pubcheck.hold import hold_key
    v = Verdict("flag", findings=[("mention", "@x")], text_hash="abc")
    body = hold_body(v, target="t", text="hi", title=None)
    assert "mention" in body and f"pubcheck-hold: {hold_key(v, 't')}" in body and "hi" in body
    assert hold_key(v, "t") != hold_key(v, "u")  # the same text to another target is another item


def test_settings_from_env(env, monkeypatch):
    assert settings()["private_owner"] == "octo"  # the config file
    monkeypatch.setenv("PUBCHECK_HOLD_REPO", "octo/_elsewhere")
    assert settings()["hold_repo"] == "octo/_elsewhere"
    assert settings({"hold_repo": "octo/_kw"})["hold_repo"] == "octo/_kw"


# ---- correspond's before_send ----


try:
    import correspond  # noqa: F401
    HAS_CORRESPOND = True
except ImportError:
    HAS_CORRESPOND = False
needs_correspond = pytest.mark.skipif(not HAS_CORRESPOND, reason="correspond is not installed")


def send(text, *, scope="public", repo=PUBLIC, dry_run=True, title=None, notify=(), native=None, hold=None):
    from correspond.model import ConversationRef, Draft

    holds = []
    check_ = make_before_send(hold=hold or (lambda v, **kw: holds.append(kw) or {"url": "https://desk/1"}))
    ref = ConversationRef.parse(f"github:{repo}")
    draft = Draft(text=text, title=title, notify=tuple(notify), native=native or {})
    audience = type("A", (), {"scope": scope})()
    check_(ref, draft, audience, operation="send", dry_run=dry_run, message_id=None)
    return holds


@needs_correspond
def test_before_send(env):
    from correspond.errors import NeedsApproval

    assert send("Fixed the parser.") == []
    assert send("Ada Quill asked", scope="org", repo=PRIVATE) == []  # private: unchanged
    with pytest.raises(NeedsApproval) as e:
        send("Ada Quill asked")
    assert e.value.details["categories"] == "registry"
    assert e.value.details["desk_item"] == "not filed (dry run)"
    assert "Ada" not in str(e.value) + json.dumps(e.value.details)
    with pytest.raises(NeedsApproval):
        send("thanks @octocat")
    with pytest.raises(NeedsApproval) as e:
        send("Fixed.", native={"assignees": ["copilot"]})
    assert e.value.details["categories"] == "mention"
    with pytest.raises(NeedsApproval) as e:
        send("Fixed.", native={"labels": ["from Ada Quill"]})
    assert e.value.details["categories"] == "registry"
    with pytest.raises(NeedsApproval) as e:
        holds = []
        send("Ada Quill asked", dry_run=False, hold=lambda v, **kw: holds.append(kw) or {"url": "https://desk/7"})
    assert e.value.details["desk_item"] == "https://desk/7" and holds[0]["target"] == f"github:{PUBLIC}"


@needs_correspond
def test_before_send_fails_closed(env, monkeypatch):
    from correspond.errors import NeedsApproval

    monkeypatch.setenv(s.VOCAB_FILE_ENV, str(env.root / "missing.json"))
    with pytest.raises(NeedsApproval) as e:
        send("Fixed the parser.")
    assert e.value.details["decision"] == "unavailable"


@needs_correspond
def test_before_send_through_correspond_check(env):
    """correspond's own ``outbound.check`` runs it and reports needs_approval."""
    from correspond.model import Audience, ConversationRef, Draft
    from correspond import outbound
    from unittest import mock

    ref = ConversationRef.parse(f"github:{PUBLIC}#1")
    public = Audience.unknown("test") if hasattr(Audience, "unknown") else None
    if public is None:
        pytest.skip("this correspond has no Audience.unknown")
    with mock.patch("correspond.ops.audience", return_value=public):
        lines, stopped = outbound.check(ref, Draft(text="Ada Quill asked"), dry_run=True,
                                        before_send=make_before_send())
    assert stopped is not None and stopped.error_kind == "needs_approval"
