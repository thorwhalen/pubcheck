"""The detectors: what in a text a public reader may not see.

A detector is a callable ``(text, ctx) -> [(category, term)]``. ``ctx`` carries what the
check knows about the post: ``repo`` (the target), ``surface`` (``git commit``, ``gh issue
create``, ``correspond send``…), ``terms`` (the registry's terms for that repo) and
``private_slugs`` (repos known to be private). Whitespace is normalised before any detector
runs, so a name wrapped across lines still matches. ``term`` is what a local author needs
to reword the text; it never leaves the machine (the CLI prints it only with ``--terms``,
and the log never holds it). A credential's term is its pattern name, never the secret.

- ``registry``: a term of an acquaint record a public reader may not see;
- ``owner-relation``: "the operator stated", "the owner's preference", "my agents"…
  (text inside double quotes, curly quotes or backticks is skipped: a quoted phrase is an
  example, not a claim);
- ``private-ref``: a repo known to be private, a private companion
  (``<private_owner>/_<name>``), this machine's home folder, and the operator's
  ``private_patterns`` (``ctx["private_patterns"]``, from the settings);
- ``session-link``: ``claude.ai/code/session_…`` (not on commits, whose session links a
  commit hook strips);
- ``credential``: a credential-shaped string (:func:`openloops.egress.find_credentials`),
  and, when the operator sets ``credential_scanner``, what that external scanner finds
  (:func:`scanner_credential`);
- ``mention``: an ``@login`` or ``@org/team`` outside code, which notifies a person:
  sending it is messaging them. Only in :data:`UNATTENDED_DETECTORS`, since an attended
  author chose to notify.

>>> findings(["As the owner asked, we fixed it"], {})
[('owner-relation', 'the owner asked')]
>>> findings(["ping @octocat about it"], {}, detectors=UNATTENDED_DETECTORS)
[('mention', '@octocat')]
>>> findings(["write to me@example.org or see `@octocat`"], {}, detectors=UNATTENDED_DETECTORS)
[]
"""

from __future__ import annotations

import getpass
import json
import os
import re
import shlex
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from pubcheck.base import Budget, log_event

Finding = tuple[str, str]
Detector = Callable[[str, Mapping], list]

DICTIONARY = "/usr/share/dict/words"
DICTIONARY_ENV = "PUBCHECK_DICTIONARY"  # another word list, one word per line
STOP_WORDS = frozenset(
    "admin bot candidate client contact dev hello info operator owner support team user".split()
)
MIN_TERM_LEN = 3

_VERB = (
    r"(?:stated|states|said|says|asked|asks|wants|wanted|prefers|preferred|requested|"
    r"told|tells|instructed|insisted|corrected|decided|noticed|complained|approved|"
    r"objected|wrote|mentioned|pointed out)"
)
# "the user" is also ordinary product talk ("the user types a query"), so it gets the narrow lists.
_USER_VERB = r"(?:stated|asked|requested|instructed|insisted|corrected)"
_OWNER = r"(?:operator|owner)"
OWNER_RELATION = [
    re.compile(rf"\bthe {_OWNER} {_VERB}\b", re.I),
    re.compile(rf"\bthe user {_USER_VERB}\b", re.I),
    re.compile(r"\bper the (?:operator|owner)\b", re.I),
    re.compile(
        rf"\bthe {_OWNER}['’]s (?:preference|correction|request|instruction|feedback|words|"
        r"rule|decision|complaint|correspondence)s?\b",
        re.I,
    ),
    re.compile(
        r"\bthe user['’]s (?:preference|correction|instruction|feedback|rule)s?\b", re.I
    ),
    re.compile(r"\bmy (?:agents?|fleet|clients?)\b", re.I),
]
_QUOTED = re.compile(r"```.*?```|\"[^\"]*\"|“[^”]*”|`[^`]*`", re.S)
_CODE = re.compile(r"```.*?```|`[^`]*`", re.S)

SESSION_LINK = re.compile(r"claude\.ai/code/session_\w+")
# GitHub logins: alphanumerics and single hyphens, up to 39; a team is @org/team. GitHub
# notifies after any non-word character, so only a word character (an address,
# me@example.org; a version, pkg@1.2) or another @ rules a mention out. A URL's /@name
# counts: holding it costs a review, missing it costs a notification.
MENTION = re.compile(
    r"(?<![\w@`])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:/[A-Za-z0-9_.-]+)?)(?![\w-])"
)


@lru_cache(maxsize=1)
def _local_paths():
    """This machine's home folder and user name, as patterns (never other people's paths)."""
    out = []
    home = str(Path.home())
    if home not in ("", "/"):
        out.append(re.compile(rf"(?<![\w.]){re.escape(home)}(?=/|\b)"))
    try:
        user = getpass.getuser()
    except Exception:
        user = ""
    if user and user != "root":
        out += [re.compile(rf"(?<![\w.])/(?:Users|home)/{re.escape(user)}\b")]
    return out


@lru_cache(maxsize=1)
def dictionary_words() -> frozenset:
    """Lowercased words of the system dictionary; empty when the machine has none."""
    try:
        with open(
            os.environ.get(DICTIONARY_ENV) or DICTIONARY,
            encoding="utf-8",
            errors="ignore",
        ) as f:
            return frozenset(w.strip().lower() for w in f)
    except OSError:
        return frozenset()


def is_common(word: str) -> bool:
    """A stop word or a dictionary word (any case)."""
    return word.lower() in STOP_WORDS or word.lower() in dictionary_words()


@lru_cache(maxsize=4096)
def _term_pattern(term):
    body = r"\s+".join(re.escape(w) for w in term.split())
    single = len(term.split()) == 1
    if single and term.isalpha() and term.islower() and not dictionary_words():
        return re.compile(
            rf"(?<=[@/]){body}(?![\w-])", re.I
        )  # no dictionary: handles only
    flags = 0 if single and term[:1].isupper() and is_common(term) else re.I
    return re.compile(rf"(?<![\w-]){body}(?![\w-])", flags)


def registry(text, ctx):
    """The registry's terms for this repo (``ctx["terms"]``) found in the text."""
    return [
        ("registry", t) for t in ctx.get("terms", ()) if _term_pattern(t).search(text)
    ]


def owner_relation(text, ctx):
    """Phrases that relay the owner's own preferences, corrections or relations."""
    bare = _QUOTED.sub(" ", text)
    return [
        ("owner-relation", m.group(0)) for p in OWNER_RELATION for m in p.finditer(bare)
    ]


@lru_cache(maxsize=256)
def _compiled(pattern):
    return re.compile(pattern)


def private_ref(text, ctx):
    """Private repos, companions, the operator's private patterns and this machine's paths."""
    patterns = [_compiled(p) for p in ctx.get("private_patterns", ())]
    if ctx.get("private_owner"):
        patterns.append(_compiled(rf"\b{re.escape(ctx['private_owner'])}/_[\w.-]+"))
    if ctx.get("surface") != "unparsed command":
        patterns += _local_paths()
    out = [("private-ref", m.group(0)) for p in patterns for m in p.finditer(text)]
    target = (ctx.get("repo") or "").lower()
    for slug in ctx.get("private_slugs", ()):
        if slug.lower() != target and re.search(
            rf"(?<![\w.-]){re.escape(slug)}(?![\w.-])", text, re.I
        ):
            out.append(("private-ref", slug))
    return out


def session_link(text, ctx):
    """Claude session links (not on commits, whose session links a commit hook strips)."""
    if ctx.get("surface") == "git commit":
        return []
    return [("session-link", m.group(0)) for m in SESSION_LINK.finditer(text)]


def credential(text, ctx):
    """Credential-shaped strings, named by pattern; the secret itself is never returned."""
    from openloops.egress import find_credentials  # lazy: the CLI starts without it

    return [("credential", name) for name, _ in find_credentials(text)]


#: The arguments of a gitleaks-compatible scanner's ``stdin`` command (betterleaks 1.x and
#: gitleaks 8 share them): a JSON report on stdout, the secret redacted, exit 0 on a find.
#: Never a validation flag: checking whether a credential is live sends it to its vendor.
SCANNER_ARGS = (
    "stdin",
    "--report-format",
    "json",
    "--report-path",
    "-",
    "--no-banner",
    "--redact",
    "--exit-code",
    "0",
)
#: Environment variables that would switch a scanner's live validation on; never passed.
SCANNER_ENV_DROPPED = ("BETTERLEAKS_VALIDATE", "BETTERLEAKS_ANALYZE")
#: Seconds the scanner may take, within what is left of the check's budget.
SCANNER_TIMEOUT = 5.0


class ScannerUnavailable(RuntimeError):
    """A configured scanner did not run; an unattended check must not pass without it."""


def scanner_credential(text, ctx):
    """What an external secret scanner finds, named ``<scanner>:<rule id>``.

    Off unless the operator sets ``credential_scanner`` (``betterleaks`` is the one
    weighed in thorwhalen/pubcheck#3; any gitleaks-compatible ``stdin`` command works,
    with ``credential_scanner_args`` for another argument list). It adds the long tail of
    vendor formats to the built-in :func:`credential`, which stays.

    It runs once per check, over every text of the post together (``whole_batch``). The
    text goes on stdin, never in argv; the report is redacted; validation is never asked
    for; the scanner runs from a neutral folder, so a repo's own scanner config is not
    read, and only from an absolute path outside the current folder.

    A scanner that is missing, fails or runs out of time is a gap, logged every time. An
    attended check carries on with the built-in patterns (and says so once on stderr);
    an **unattended** one raises :class:`ScannerUnavailable`, so the check is
    ``unavailable`` and the text is held, as any other lookup that cannot be made.

    >>> scanner_credential("AKIA...", {})  # no scanner configured
    []
    """
    conf = ctx.get("settings") or {}
    scanner = conf.get("credential_scanner")
    if not scanner:
        return []
    try:
        report = _run_scanner(scanner, conf, text, ctx)
    except ScannerUnavailable as gap:
        log_event(writer="pubcheck", event="credential_scanner_gap", reason=str(gap))
        if ctx.get("unattended"):
            raise
        _say_once(str(gap))
        return []
    name = Path(scanner).name
    return [
        ("credential", f"{name}:{f.get('RuleID') or 'unknown'}")
        for f in report
        if isinstance(f, Mapping)
    ]


scanner_credential.whole_batch = True


def _run_scanner(scanner, conf, text, ctx) -> list:
    """The scanner's findings for ``text``; raises :class:`ScannerUnavailable` on any gap."""
    if not isinstance(scanner, str):
        raise ScannerUnavailable("credential_scanner must be a command name or path")
    args = conf.get("credential_scanner_args") or SCANNER_ARGS
    if isinstance(args, str):
        args = shlex.split(args)
    if not all(isinstance(a, str) for a in args):
        raise ScannerUnavailable("credential_scanner_args must be a list of strings")
    exe = shutil.which(scanner)
    if exe is None:
        raise ScannerUnavailable(f"credential_scanner {scanner!r} not found")
    exe = os.path.realpath(exe)
    here = os.path.realpath(os.getcwd())
    if exe.startswith(here + os.sep):
        raise ScannerUnavailable(
            f"credential_scanner {scanner!r} resolves inside the current folder; refused"
        )
    env = {k: v for k, v in os.environ.items() if k not in SCANNER_ENV_DROPPED}
    budget = ctx.get("budget") or Budget(None)
    done = budget.run(
        [exe, *args], cap=SCANNER_TIMEOUT, stdin=text, env=env, cwd=tempfile.gettempdir()
    )
    if done is None:
        raise ScannerUnavailable(
            f"credential_scanner {scanner!r} failed or ran out of time"
        )
    if done.returncode != 0:
        raise ScannerUnavailable(
            f"credential_scanner {scanner!r} exited {done.returncode}"
        )
    try:
        report = json.loads(done.stdout)
    except ValueError:
        raise ScannerUnavailable(
            f"credential_scanner {scanner!r} printed no JSON report"
        ) from None
    if report is None:  # Go encodes an empty slice as null
        return []
    if not isinstance(report, list):
        raise ScannerUnavailable(f"credential_scanner {scanner!r} printed no list")
    return report


def is_scanner_finding(finding) -> bool:
    """True for a credential an external scanner found (its term is ``<scanner>:<rule>``).

    The built-in patterns name their findings without a colon, and only they are known
    to :func:`pubcheck.hold.redact`.

    >>> is_scanner_finding(("credential", "betterleaks:slack-webhook-url"))
    True
    >>> is_scanner_finding(("credential", "github_token"))
    False
    """
    category, term = finding
    return category == "credential" and ":" in term


@lru_cache(maxsize=None)
def _say_once(why: str) -> None:
    """Say once per process, on stderr, that an attended check ran without the scanner."""
    print(f"pubcheck: {why}; built-in credential patterns only", file=sys.stderr)


def mention(text, ctx):
    """``@login`` and ``@org/team`` outside code spans and blocks: each notifies someone."""
    bare = _CODE.sub(" ", text)
    return [("mention", "@" + m.group(1)) for m in MENTION.finditer(bare)]


#: The detectors for an attended writer (a Claude Code session): the seam is this tuple.
DETECTORS: tuple[Detector, ...] = (
    registry,
    owner_relation,
    private_ref,
    session_link,
    credential,
    scanner_credential,
)
#: An unattended writer also holds every @mention: nobody chose to notify that person.
UNATTENDED_DETECTORS: tuple[Detector, ...] = DETECTORS + (mention,)


def findings(texts: Iterable[str], ctx: Mapping, *, detectors=DETECTORS) -> list[Finding]:
    """``[(category, term)]``, each once, found by ``detectors`` in any of ``texts``."""
    seen: list[Finding] = []
    texts = [re.sub(r"\s+", " ", text or "") for text in texts]
    for detect in detectors:
        # a detector that starts a process sees the whole post once, not text by text
        batches = ["\n".join(texts)] if getattr(detect, "whole_batch", False) else texts
        for text in batches:
            for hit in detect(text, ctx):
                if hit not in seen:
                    seen.append(hit)
    return seen
