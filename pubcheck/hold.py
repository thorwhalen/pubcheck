"""A held post becomes a desk item: an issue in a private repo, labelled for the desk.

When an unattended writer's text is held (flagged, or the check unavailable), nothing is
lost and nothing is refused silently: :func:`file_hold` opens one issue in the hold repo
(setting ``hold_repo``, by default the desk's own private repo) with the label the desk
reads (``hold_label``, by default ``escalate``), carrying the target, the title, the text
and the categories, so the owner can publish it as is, edit it, or drop it.

The hold repo receives the text, so it must be private: :func:`file_hold` asks GitHub
(never a cache) just before filing, and files nothing when it is public or unknown, or
when no ``hold_repo`` is configured. Credential-shaped strings are redacted from the copy
(:func:`redact`). The same text held twice (a retry) is filed once: the body carries the
text's hash, and an open issue with that hash is reused.

>>> redact("token: ghp_" + "A1" * 18)
'token: [credential redacted: github_token]'
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping, Sequence

from pubcheck.base import Budget, settings, text_hash
from pubcheck.core import HINTS, Verdict
from pubcheck.sources import gh_repo_view

MARKER = "pubcheck-hold"


#: A whole PEM private key, BEGIN to END (the shared patterns match only the BEGIN line).
PEM_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S
)


def redact(text: str) -> str:
    r"""``text`` with every credential-shaped string replaced by its pattern's name.

    >>> redact("a -----BEGIN RSA PRIVATE KEY-----\nMIIE\nxyz\n-----END RSA PRIVATE KEY----- b")
    'a [credential redacted: private_key_block] b'
    """
    from openloops.egress import CREDENTIAL_PATTERNS

    text = PEM_BLOCK.sub("[credential redacted: private_key_block]", text)
    for name, pattern in CREDENTIAL_PATTERNS:
        text = pattern.sub(f"[credential redacted: {name}]", text)
    return text


def hold_title(target: str, title: str | None) -> str:
    """``held: <target>: <title>``, short enough for a desk card.

    >>> hold_title("github:o/r", "Fix the thing")
    'held: github:o/r: Fix the thing'
    """
    head = f"held: {target}"
    return f"{head}: {redact(title)}"[:200] if title else head


def hold_key(verdict: Verdict, target: str) -> str:
    """What makes two holds the same desk item: the same text to the same target."""
    return text_hash(target, verdict.text_hash)


def hold_body(
    verdict: Verdict,
    *,
    target: str,
    text: str,
    title: str | None,
    more: Sequence[str] = (),
) -> str:
    """The desk item's body: why it was held, what would have been published, and the key."""
    why = (
        [f"- {c}: {HINTS.get(c, c)}" for c in verdict.categories]
        if verdict.decision == "flag"
        else [f"- the check was unavailable: {verdict.reason}"]
    )
    text, title = redact(text), redact(title) if title else title
    also = (
        [f"**Also published with it:** {', '.join(redact(m) for m in more)}", ""]
        if more
        else []
    )
    return "\n".join(
        [
            f"A post to `{target}` ({verdict.visibility}) was held by the publication check, "
            "and nothing was published.",
            "",
            "**Why:**",
            *why,
            "",
            "**Accept** (publish as is, after reading it), **edit** (reword, then send again) "
            "or **ignore** (close this issue).",
            "",
            f"**Title:** {title or '(none)'}",
            "",
            *also,
            "**Text:**",
            "",
            "````",
            text,
            "````",
            "",
            f"<!-- {MARKER}: {hold_key(verdict, target)} -->",
        ]
    )


def _existing(repo: str, key: str, budget: Budget):
    r = budget.run(
        [
            "gh",
            "issue",
            "list",
            "-R",
            repo,
            "--state",
            "open",
            "--search",
            f'"{MARKER}: {key}" in:body',
            "--json",
            "url",
            "-q",
            ".[0].url",
        ],
        cap=8,
    )
    url = (r.stdout.strip() if r is not None and r.returncode == 0 else "") or None
    return url


def file_hold(
    verdict: Verdict,
    *,
    target: str,
    text: str,
    title: str | None = None,
    more: Sequence[str] = (),
    config: Mapping | None = None,
    budget: Budget | None = None,
) -> dict:
    """File (or find) the desk item for a held post; ``{"filed": bool, "url"?, "reason"?}``. Never raises."""
    s = settings(config)
    repo, label = s["hold_repo"], s["hold_label"]
    budget = budget or Budget(s["budget_seconds"])
    if not repo:
        return {"filed": False, "reason": "no hold_repo is configured"}
    if not shutil.which("gh"):
        return {"filed": False, "reason": "gh is not installed"}
    try:
        private = gh_repo_view(
            repo, budget=budget
        )  # fresh: never trust a cache before copying
        if private is not True:
            return {
                "filed": False,
                "reason": f"the hold repo {repo} is not known to be private, so the text is not copied there",
            }
        url = _existing(repo, hold_key(verdict, target), budget)
        if url:
            return {"filed": True, "url": url, "repo": repo, "existing": True}
        body = hold_body(verdict, target=target, text=text, title=title, more=more)
        argv = [
            "gh",
            "issue",
            "create",
            "-R",
            repo,
            "--title",
            hold_title(target, title),
            "--body-file",
            "-",
        ]
        if label:
            argv += ["--label", label]
        r = budget.run(argv, cap=20, stdin=body)
        if r is None or r.returncode != 0:
            err = (
                (r.stderr.strip().splitlines() or ["?"])[-1]
                if r is not None
                else "out of time"
            )
            return {"filed": False, "reason": f"gh issue create failed: {err}"}
        return {"filed": True, "url": r.stdout.strip().splitlines()[-1], "repo": repo}
    except Exception as error:
        return {"filed": False, "reason": f"filing failed ({type(error).__name__})"}
