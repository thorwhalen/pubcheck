"""correspond's ``before_send`` check: the publication check for every write correspond makes.

Set it once at the top of correspond's config file (``~/.config/correspond/config.toml``)::

    before_send = "pubcheck.correspond:before_send"

For a write whose audience is **public** (correspond resolves an unknown audience to
public), it runs :func:`pubcheck.check` on the draft's title and text, unattended: a
correspond write has nobody reading it before it goes out, so @mentions are held and an
unavailable check holds too (fail closed). Assignees and the ``notify`` list notify people,
so they hold as mentions; labels, a milestone, a discussion category and attachment names
are checked with the text. Any other audience (a private repo, the operator's own devices)
passes unchanged.

A held write raises ``correspond.errors.NeedsApproval`` with the categories (never the
text) in its details. On a real send, not a dry run, the held post also becomes a desk
item (:func:`pubcheck.hold.file_hold`), whose URL is in the details as ``desk_item``.
:func:`make_before_send` builds a check with other settings or another ``hold``.

Not covered: the contents of attached files (the check reads prose, not files).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pubcheck.core import check as _check
from pubcheck.hold import file_hold

WRITER = "correspond"
PUBLIC = "public"


def _is_public(audience: Any) -> bool:
    """Public unless correspond computed a narrower scope; an audience it could not compute is public."""
    scope = getattr(audience, "scope", None)
    return scope is None or str(getattr(scope, "value", scope)) == PUBLIC


def _repo_of(ref: Any) -> str | None:
    """``owner/repo`` of a ``github:`` conversation, else ``None``.

    >>> class Ref: channel, id = "github", "octo/app#12"
    >>> _repo_of(Ref())
    'octo/app'
    """
    if str(getattr(ref, "channel", "")) != "github":
        return None
    slug = str(getattr(ref, "id", "") or "").split("#", 1)[0]
    return slug if slug.count("/") == 1 else None


def _strings(value: Any) -> list[str]:
    """The text values in plain data (strings and numbers, through mappings and lists); objects are skipped."""
    if isinstance(value, Mapping):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple, set)):
        return [s for v in value for s in _strings(v)]
    return [str(value)] if isinstance(value, (str, int, float)) and not isinstance(value, bool) else []


def _published_with(draft: Any) -> list[str]:
    """What a draft publishes besides its title and text, as strings to check.

    The people it notifies (its ``notify`` list and any native ``assignees``) as
    ``@login``, so the mention detector holds them; every other native value (labels, a
    milestone, a discussion category); the attachments' names.
    """
    native = getattr(draft, "native", None) or {}
    native = native if isinstance(native, Mapping) else {}
    people = list(getattr(draft, "notify", ()) or ()) + _strings(native.get("assignees"))
    out = ["@" + str(p).lstrip("@") for p in people]
    out += [s for k, v in native.items() if k != "assignees" for s in _strings(v)]
    for a in getattr(draft, "attachments", ()) or ():
        name = getattr(a, "name", None) or str(getattr(a, "ref", "") or "").rsplit("/", 1)[-1]
        out += _strings(name or None)
    return out


def make_before_send(
    *,
    config: Mapping | None = None,
    hold: Callable[..., dict] = file_hold,
    check: Callable = _check,
) -> Callable[..., None]:
    """A correspond ``before_send`` check; ``config`` overrides pubcheck's settings (``hold_repo``…)."""

    def before_send(ref, draft, audience, *, operation="send", dry_run=False, message_id=None, **context):
        if not _is_public(audience):
            return None
        from correspond.errors import NeedsApproval

        text = getattr(draft, "text", None) or ""
        title = getattr(draft, "title", None)
        more = _published_with(draft)
        target = str(getattr(ref, "encoded", None) or ref)
        verdict = check(
            text,
            title=title,
            more=more,
            repo=_repo_of(ref),
            public=True,
            unattended=True,
            surface=f"correspond {operation}",
            writer=WRITER,
            budget=(config or {}).get("budget_seconds"),
        )
        if not verdict.held:
            return None
        details = {
            "check": "pubcheck",
            "decision": verdict.decision,
            "categories": ",".join(verdict.categories),
            "text_hash": verdict.text_hash,
        }
        if dry_run:
            details["desk_item"] = "not filed (dry run)"
        else:
            filed = hold(verdict, target=target, text=text, title=title, more=more, config=config)
            details["desk_item"] = filed.get("url") or f"not filed: {filed.get('reason')}"
        why = (
            f"held for review: {', '.join(verdict.categories)} in a post to a public audience"
            if verdict.decision == "flag"
            else f"held: the publication check is unavailable ({verdict.reason})"
        )
        raise NeedsApproval(why, **details)

    return before_send


#: The check correspond's config names: ``before_send = "pubcheck.correspond:before_send"``.
before_send = make_before_send()
