"""What the check looks up: a repo's visibility, the acquaint registry, private companions.

**Visibility** comes from a visibility cache shared with other tools on the machine
(``~/.cache/priv/repo_visibility/<sanitized remote>.json``, ``$PRIV_VISIBILITY_CACHE_DIR``,
24 h; one JSON file per remote: ``remote``, ``slug``, ``is_private``, ``checked_at``). Every
fresh entry is read, whatever its remote spelling. A miss asks ``gh repo view`` and records
the answer in the same format. Unknown (offline, no ``gh``, no such repo) is ``None``,
which the check treats as public.

**The registry** is acquaint's Do-not-identify vocabulary for a public audience
(``acquaint disclosure --audience '{"scope": "public"}' --json``), cached an hour in
``~/.cache/public-text-guard/`` (``term`` and ``entity`` only, mode 0600). A stale cache
serves when acquaint cannot be asked. ``$PUBLIC_TEXT_GUARD_VOCAB_FILE`` names a JSON list
to use instead (tests).

>>> parse_slug("git@github.com:octo/app.git")
'octo/app'
>>> terms_for([{"term": "Ada Quill", "entity": "person:a"}, {"term": "AQ", "entity": "person:a"}], "o/r")
['Ada Quill']
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

from pubcheck.base import Budget, cache_dir, write_private
from pubcheck.detectors import MIN_TERM_LEN, is_common

VISIBILITY_CACHE_ENV = "PRIV_VISIBILITY_CACHE_DIR"  # the shared cache's own name
VISIBILITY_TTL = 24 * 60 * 60
VOCAB_FILE_ENV = "PUBLIC_TEXT_GUARD_VOCAB_FILE"
VOCAB_TTL = 60 * 60
VOCAB_MAX_AGE = (
    7 * 24 * 60 * 60
)  # an old copy serves when acquaint cannot answer, up to this age
COMPANION_TTL = 24 * 60 * 60
ACQUAINT_CANDIDATES = ("~/.pyenv/shims/acquaint", "~/.local/bin/acquaint")
PUBLIC_AUDIENCE = '{"scope": "public"}'

# ---- visibility ----


def parse_slug(remote_url):
    """``owner/repo`` from a github.com remote URL, else ``None``."""
    url = (remote_url or "").strip()
    m = re.match(r"^[\w.+-]+@([^:/]+):(.+)$", url) or re.match(
        r"^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^@/]*@)?([^/:]+)(?::\d+)?/(.+)$", url
    )
    if not m or m.group(1).lower() != "github.com":
        return None
    path = m.group(2).strip("/")
    path = path[:-4] if path.endswith(".git") else path
    return path if path.count("/") == 1 else None


def _visibility_dir():
    return Path(
        os.environ.get(VISIBILITY_CACHE_ENV) or "~/.cache/priv/repo_visibility"
    ).expanduser()


def cache_key(remote_url):
    """The cache's file name for a remote."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", remote_url)


def cached_visibility(*, now=None, directory=None):
    """``{slug (lowercase): is_private}`` from every fresh entry of the shared visibility cache."""
    now = time.time() if now is None else now
    d = directory or _visibility_dir()
    out = {}
    try:
        files = list(d.glob("*.json"))
    except OSError:
        return out
    for f in files:
        try:
            data = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        slug = data.get("slug") or parse_slug(data.get("remote", ""))
        checked, private = data.get("checked_at"), data.get("is_private")
        if slug and isinstance(private, bool) and isinstance(checked, (int, float)):
            if 0 <= now - checked < VISIBILITY_TTL:
                out[slug.lower()] = private
    return out


def gh_repo_view(slug, *, budget: Budget):
    """``True`` private, ``False`` public, ``"missing"`` no such repo, ``None`` unknown."""
    if not shutil.which("gh"):
        return None
    r = budget.run(
        ["gh", "repo", "view", slug, "--json", "isPrivate", "-q", ".isPrivate"]
    )
    if r is None:
        return None
    if r.returncode == 0:
        return {"true": True, "false": False}.get(r.stdout.strip())
    return "missing" if "Could not resolve to a Repository" in r.stderr else None


def write_visibility(slug, is_private, remote=None):
    """Record a verdict in the shared cache's format."""
    remote = remote or f"https://github.com/{slug}"
    d = _visibility_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{cache_key(remote)}.json.tmp"
        tmp.write_text(
            json.dumps(
                {
                    "remote": remote,
                    "slug": slug,
                    "is_private": is_private,
                    "checked_at": time.time(),
                }
            )
        )
        tmp.replace(d / f"{cache_key(remote)}.json")
    except OSError:
        pass


def lookup_visibility(slug, cache, *, budget: Budget, remote=None):
    """``True`` private, ``False`` public, ``None`` unknown (does not exist, or offline)."""
    if slug.lower() in cache:
        return cache[slug.lower()]
    private = gh_repo_view(slug, budget=budget)
    if isinstance(private, bool):
        cache[slug.lower()] = private
        write_visibility(slug, private, remote)
        return private
    return None


def companion_exists(slug, cache, *, budget: Budget):
    """Whether ``slug`` exists (remembered a day); ``None`` when it cannot be asked."""
    if slug.lower() in cache:
        return True
    store = cache_dir() / "companions.json"
    try:
        known = json.loads(store.read_text())
    except (OSError, ValueError):
        known = {}
    hit = known.get(slug.lower())
    if (
        isinstance(hit, dict)
        and 0 <= time.time() - hit.get("checked_at", 0) < COMPANION_TTL
    ):
        return hit.get("exists")
    answer = gh_repo_view(slug, budget=budget)
    if answer is None:
        return None
    exists = answer != "missing"
    if isinstance(answer, bool):
        cache[slug.lower()] = answer
        write_visibility(slug, answer)
    known[slug.lower()] = {"exists": exists, "checked_at": time.time()}
    write_private(store, json.dumps(known))
    return exists


def origin(directory, *, budget: Budget):
    """``(slug, remote url)`` of ``directory``'s ``origin``, or ``(None, None)``."""
    if not directory:
        return None, None
    r = budget.run(["git", "-C", str(directory), "remote", "get-url", "origin"], cap=5)
    if r is None or r.returncode != 0:
        return None, None
    url = r.stdout.strip()
    return parse_slug(url), url


# ---- the acquaint registry ----


def _acquaint():
    found = shutil.which("acquaint")
    if found:
        return found
    for c in ACQUAINT_CANDIDATES:
        p = Path(c).expanduser()
        if p.exists():
            return str(p)
    return None


def _fetch_vocabulary(budget: Budget):
    exe = _acquaint()
    if not exe:
        return None
    r = budget.run([exe, "disclosure", "--audience", PUBLIC_AUDIENCE, "--json"])
    if r is None or r.returncode != 0:
        return None
    try:
        rows = json.loads(r.stdout).get("vocabulary")
    except (ValueError, AttributeError):
        return None
    if not isinstance(rows, list):
        return None
    return [
        {"term": v.get("term"), "entity": v.get("entity")}
        for v in rows
        if isinstance(v, dict)
    ]


def vocabulary(*, budget: Budget):
    """``(rows, available)``: acquaint's public-audience vocabulary ``[{term, entity}]``, cached ``VOCAB_TTL``.

    When acquaint cannot answer, a copy up to ``VOCAB_MAX_AGE`` old serves. ``available``
    is False when there is nothing usable: no answer, no copy young enough, or an empty
    vocabulary (records not synced to this machine check no name at all).
    """
    override = os.environ.get(VOCAB_FILE_ENV)
    if override:
        try:
            rows = json.loads(Path(override).read_text())
        except (OSError, ValueError):
            return [], False
        return rows, bool(rows)
    cache = cache_dir() / "vocabulary.json"
    old = None
    try:
        old = json.loads(cache.read_text())
        if 0 <= time.time() - old["checked_at"] < VOCAB_TTL and old["vocabulary"]:
            return old["vocabulary"], True
    except (OSError, ValueError, KeyError, TypeError):
        pass
    fresh = _fetch_vocabulary(budget)
    if fresh is None:
        try:
            young = 0 <= time.time() - old["checked_at"] < VOCAB_MAX_AGE
            rows = old["vocabulary"] if young else None
        except (KeyError, TypeError):
            rows = None
        return (rows, True) if rows else ([], False)
    if not fresh:
        return [], False  # never cached: an empty answer is no registry
    write_private(cache, json.dumps({"checked_at": time.time(), "vocabulary": fresh}))
    return fresh, True


def terms_for(vocab, repo):
    """The terms to scan for when posting to ``repo``.

    An org record that the target's owner names is the target itself: all its terms go. A
    person's term equal to the owner goes alone. Short terms and common lowercase words go.
    """
    owner = (repo or "").split("/")[0].lower()
    own_orgs = {
        v.get("entity")
        for v in vocab
        if str(v.get("term", "")).lower() == owner
        and str(v.get("entity", "")).startswith("org:")
    }
    out = []
    for v in vocab:
        term = " ".join(str(v.get("term") or "").split())
        if (
            not term
            or v.get("entity") in own_orgs
            or term.lower() == owner
            or len(term) < MIN_TERM_LEN
        ):
            continue
        if term.isalpha() and term.islower() and is_common(term):
            continue
        if term not in out:
            out.append(term)
    return out
