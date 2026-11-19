"""The check: is this text fit for the repo it is about to be published to?

:func:`check` is the one entry point every writer calls (the Claude Code hook through the
CLI, correspond's ``before_send``, hatchway through the CLI). It answers a :class:`Verdict`:

- ``pass``: a private target (nothing is scanned), or nothing found;
- ``flag``: a detector found something; the text must not be published as is;
- ``unavailable``: the check could not be made. For an **unattended** writer (nobody
  reads the post before it goes out) that is a missing registry, a lookup out of time, or
  any error; such a writer must hold the text, never post it. An attended writer proceeds
  without the registry (the gap is logged), and only an error makes the check unavailable;
- ``override``: found something, but the author gave a reason to publish anyway (the
  hook's ``# public-text-ok: <reason>``); logged with the reason.

An unknown visibility (offline, no ``gh``, no such repo, no repo named) is public.

>>> v = check("A neutral release note.", repo="o/r", public=True, log=False)
>>> v.decision, v.exit_code
('pass', 0)
>>> v = check("As the owner asked, we fixed it.", repo="o/r", public=True, log=False)
>>> v.decision, v.categories, v.exit_code
('flag', ['owner-relation'], 1)
>>> check("the owner asked", repo="o/r", public=False, log=False).decision
'pass'
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from pubcheck.base import MAX_TEXT, Budget, log_event, settings, text_hash
from pubcheck.detectors import (
    DETECTORS,
    UNATTENDED_DETECTORS,
    Finding,
    dictionary_words,
    findings,
)
from pubcheck.sources import (
    cached_visibility,
    companion_exists,
    gh_repo_view,
    lookup_visibility,
    origin,
    terms_for,
    vocabulary,
)

EXIT_CODES = {"pass": 0, "override": 0, "flag": 1, "unavailable": 2}

#: One line per category, for the author who has to reword.
HINTS = {
    "registry": "names a person or org from the owner's acquaint records that a public reader may not see",
    "owner-relation": 'relays the owner\'s own preferences, corrections or relations ("the operator stated", "my agents")',
    "private-ref": "points at a private repo, working folder or local path",
    "session-link": "carries a Claude session link (strip it)",
    "credential": "carries a credential-shaped string (a token, a key, a password in a URL)",
    "mention": "@mentions someone, which notifies them: posting it is messaging them",
}


@dataclass
class Verdict:
    """What the check decided about one text, and why; :meth:`to_json` never holds the text."""

    decision: str
    repo: str = ""
    visibility: str = "unknown"  # public | private | unknown
    findings: list[Finding] = field(default_factory=list)
    registry: str = "skipped"  # available | unavailable | skipped
    unattended: bool = False
    destination: str | None = None
    reason: str | None = None
    text_hash: str = ""

    @property
    def categories(self) -> list[str]:
        """The categories found, sorted, each once."""
        return sorted({c for c, _ in self.findings})

    @property
    def exit_code(self) -> int:
        """0 pass (or override), 1 flag, 2 unavailable."""
        return EXIT_CODES[self.decision]

    @property
    def held(self) -> bool:
        """Whether a writer must hold the text instead of publishing it."""
        return self.decision in ("flag", "unavailable")

    def to_json(self, *, terms: bool = False) -> dict:
        """The verdict as JSON: categories, never the text; the matched terms only on request."""
        out = {
            "decision": self.decision,
            "repo": self.repo,
            "visibility": self.visibility,
            "categories": self.categories,
            "registry": self.registry,
            "unattended": self.unattended,
            "destination": self.destination,
            "reason": self.reason,
            "text_hash": self.text_hash,
        }
        if terms:
            out["findings"] = [list(f) for f in self.findings]
            out["explain"] = self.explain()
        return out

    def explain(self) -> str:
        """For the author: what was found, by category, and where the private context goes."""
        if self.decision == "unavailable":
            return f"The publication check could not be made ({self.reason}), so nothing is published."
        lines = [f"{self.repo or 'an unknown (so presumed public) repo'} is public, and the text:"]
        for cat in self.categories:
            found = ", ".join(repr(t) for c, t in self.findings if c == cat)
            lines.append(f"- {HINTS.get(cat, cat)}: {found}")
        lines.append(
            "Public repos carry only what any user of the package could read. Reword it "
            "generically (the rule, the fix, the failing case), and put the incident and the "
            f"owner's own context in {self.destination or 'a private repo'}."
        )
        return "\n".join(lines)


def destination(repo: str, cache: dict, *, budget: Budget, config: Mapping | None = None) -> str:
    """Where the private context goes: the repo's private companion, else ``private_issues``."""
    s = settings(config)
    name = repo.split("/")[-1] if repo else ""
    if name and s["private_owner"]:
        companion = f"{s['private_owner']}/_{name.lstrip('_')}"
        if companion_exists(companion, cache, budget=budget):
            return f"the private companion `{companion}`"
    if s["private_issues"]:
        return f"`{s['private_issues']}`, titled `[{repo or 'owner/repo'}] …`"
    return "a private repo"


def _unattended_gaps(conf: Mapping) -> list[str]:
    """What an unattended check needs and lacks: the operator's settings, a word list."""
    gaps = []
    if not conf.get("private_owner"):
        gaps.append("no private_owner setting (the operator's config file is missing)")
    if not dictionary_words():
        gaps.append("no system word list (install one, e.g. the wamerican package)")
    return gaps


def check(
    text: str,
    *,
    repo: str | None = None,
    title: str | None = None,
    more: Sequence[str] = (),
    unattended: bool = False,
    public: bool | None = None,
    surface: str = "text",
    override: str | None = None,
    repo_dir: str | None = None,
    detectors: Sequence | None = None,
    budget: float | None = None,
    writer: str = "pubcheck",
    log: bool = True,
    context: Mapping | None = None,
) -> Verdict:
    """Check ``text`` (and ``title``) for publication to ``repo``; never raises.

    ``more`` are other strings published with it (labels, a category, file names, the
    people a post notifies as ``@login``). ``public`` skips the visibility lookup when the
    caller already knows (correspond's audience). ``repo_dir`` names a checkout whose
    ``origin`` is the target when ``repo`` is not given. ``detectors`` defaults by
    ``unattended``. ``override`` is ignored when ``unattended``: nobody is there to give a
    reason. ``context`` adds fields to the log event (a session id, a tool name), never text.

    An unattended check asks GitHub for the visibility instead of trusting a cached
    "private" (a repo made public today must not pass unscanned), and holds a text longer
    than ``MAX_TEXT`` as unavailable.
    """
    texts = [t for t in (title, text, *more) if t]
    verdict = Verdict("pass", repo=repo or "", unattended=unattended, text_hash=text_hash(*texts))
    conf = settings({"budget_seconds": budget})
    b = Budget(conf["budget_seconds"])

    def logged(decision_name, **extra):
        if log:
            log_event(
                writer=writer, surface=surface, repo=verdict.repo, decision=decision_name,
                categories=verdict.categories, unattended=unattended,
                text_hash=verdict.text_hash, **extra, **dict(context or {}),
            )
        return verdict

    try:
        cache = cached_visibility()
        remote = None
        if not repo and repo_dir:
            repo, remote = origin(repo_dir, budget=b)
            verdict.repo = repo or ""
        if public is not None:
            private = not public
        elif not repo:
            private = None
        elif unattended:
            private = gh_repo_view(repo, budget=b)  # fresh: never a cached "private"
            private = private if isinstance(private, bool) else None
        else:
            private = lookup_visibility(repo, cache, budget=b, remote=remote)
        if private is True:
            verdict.visibility = "private"
            return verdict
        verdict.visibility = "public" if private is False else "unknown"
        missing = _unattended_gaps(conf) if unattended else []
        if missing:
            verdict.decision = "unavailable"
            verdict.reason = "not set up for an unattended writer: " + "; ".join(missing)
            return logged("unavailable", reason=verdict.reason)
        if unattended and sum(len(t) for t in texts) > MAX_TEXT:
            verdict.decision = "unavailable"
            verdict.reason = f"the text is longer than {MAX_TEXT} characters, which is not checked"
            return logged("unavailable", reason=verdict.reason)
        vocab, available = vocabulary(budget=b)
        verdict.registry = "available" if available else "unavailable"
        ctx = {
            "repo": repo or "",
            "surface": surface,
            "terms": terms_for(vocab, repo),
            "private_slugs": [s for s, p in cache.items() if p],
            "private_owner": conf["private_owner"],
            "private_patterns": conf["private_patterns"],
            "unattended": unattended,
            "settings": conf,
            "budget": b,
        }
        if detectors is None:
            detectors = UNATTENDED_DETECTORS if unattended else DETECTORS
        verdict.findings = findings(texts, ctx, detectors=detectors)
    except Exception as error:  # a check that cannot judge holds the text
        # the type only: an error's message can echo the text
        verdict.decision, verdict.reason = "unavailable", f"the check failed ({type(error).__name__})"
        return logged("unavailable", reason=verdict.reason)
    if not verdict.findings:
        if not available and unattended:
            verdict.decision = "unavailable"
            verdict.reason = "the acquaint registry is unavailable and nobody reads this before it goes out"
            return logged("unavailable", reason=verdict.reason)
        if not available:
            logged("registry-unavailable")
        return verdict
    if override and override.strip() and not unattended:
        verdict.decision = "override"
        return logged("override", reason=override.strip())
    verdict.decision = "flag"
    try:
        verdict.destination = destination(repo or "", cache, budget=b)
    except Exception:
        verdict.destination = "a private repo"
    return logged("block")
