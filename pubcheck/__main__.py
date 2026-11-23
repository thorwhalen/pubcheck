"""The command line: ``public-text-guard check --repo OWNER/REPO [--unattended]``, the text on stdin.

Exit 0 pass (or override), 1 flag, 2 unavailable; one JSON object on stdout naming the
decision and the categories, never the text (the matched terms only with ``--terms``, for a
local author who has to reword). ``--unattended`` is for a writer nobody reads before the
post goes out: @mentions are held, and a missing registry or any failure is ``unavailable``.
``--hold TARGET`` (unattended) also files a held post as a desk item and adds its URL to
the JSON as ``desk_item``.

``--budget`` is counted from the moment the command starts, and ``--deadline`` (a Unix
time, ``time.time()``) is the moment its caller gives up; the lookups stop
``FINISH_RESERVE`` seconds before the earlier of the two, so the command answers even on
a loaded machine, where starting Python alone can take seconds. A caller that kills the
command at a deadline should pass it: only the caller knows when it started waiting.

Usage from a script::

    printf '%s' "$BODY" | public-text-guard check --repo octo/app --unattended
"""

from __future__ import annotations

import argparse
import json
import sys
import time

_STARTED = time.monotonic()  # as early as the command can tell: its budget starts here


def effective_budget(budget, deadline=None, *, started, reserve=None, default=None):
    """Seconds the lookups may take: what is left of ``budget`` since ``started`` and
    before ``deadline`` (Unix time), less ``reserve``; never negative.

    >>> now = time.monotonic()
    >>> effective_budget(10, started=now, reserve=1) <= 9
    True
    >>> effective_budget(10, time.time() + 3, started=now, reserve=1) <= 2
    True
    >>> effective_budget(10, time.time() - 5, started=now, reserve=1)
    0.0
    """
    from pubcheck.base import FINISH_RESERVE, settings

    reserve = FINISH_RESERVE if reserve is None else reserve
    if budget is None:
        budget = default if default is not None else settings()["budget_seconds"]
    left = budget - (time.monotonic() - started)
    if deadline is not None:
        left = min(left, deadline - time.time())
    return max(left - reserve, 0.0)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="public-text-guard", description=__doc__.splitlines()[0]
    )
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="check the text on stdin for publication to --repo")
    c.add_argument("--repo", help="OWNER/REPO the text goes to (none: presumed public)")
    c.add_argument(
        "--repo-dir",
        help="a checkout whose origin is the target, when --repo is not given",
    )
    c.add_argument("--title", help="a title published with the text")
    c.add_argument(
        "--unattended",
        action="store_true",
        help="nobody reads it first: fail closed, hold @mentions",
    )
    c.add_argument(
        "--public",
        action="store_true",
        help="the target is known to be public: skip the lookup",
    )
    c.add_argument(
        "--surface",
        default="cli",
        help="what posts it (git commit, gh issue create…), for the log",
    )
    c.add_argument(
        "--override", help="publish despite findings, for this reason (logged)"
    )
    c.add_argument(
        "--terms", action="store_true", help="include the matched terms (local use only)"
    )
    c.add_argument(
        "--hold",
        metavar="TARGET",
        help="on a hold, file a desk item for TARGET (e.g. github:o/r)",
    )
    c.add_argument(
        "--budget",
        type=float,
        help="seconds for the whole check, from the command's start",
    )
    c.add_argument(
        "--deadline",
        type=float,
        help="Unix time at which the caller gives up; the check answers before it",
    )
    c.add_argument("--session", help="a session id for the log")
    return p


def main(argv=None) -> int:
    """Run the CLI; returns the exit code (0 pass, 1 flag, 2 unavailable)."""
    args = _parser().parse_args(argv)
    try:
        from pubcheck.core import check

        text = sys.stdin.read()
        verdict = check(
            text,
            repo=args.repo,
            repo_dir=args.repo_dir,
            title=args.title,
            unattended=args.unattended,
            public=True if args.public else None,
            surface=args.surface,
            override=args.override,
            budget=effective_budget(args.budget, args.deadline, started=_STARTED),
            writer="cli",
            context={"session": args.session} if args.session else None,
        )
        out = verdict.to_json(terms=args.terms)
        if args.hold and verdict.held:
            from pubcheck.hold import file_hold

            filed = file_hold(verdict, target=args.hold, text=text, title=args.title)
            out["desk_item"] = filed.get("url") or f"not filed: {filed.get('reason')}"
        print(json.dumps(out))
        return verdict.exit_code
    except Exception as error:  # the check could not be made
        print(
            json.dumps(
                {
                    "decision": "unavailable",
                    "reason": f"the check failed ({type(error).__name__})",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
