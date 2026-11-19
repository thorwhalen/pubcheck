"""The command line: ``public-text-guard check --repo OWNER/REPO [--unattended]``, the text on stdin.

Exit 0 pass (or override), 1 flag, 2 unavailable; one JSON object on stdout naming the
decision and the categories, never the text (the matched terms only with ``--terms``, for a
local author who has to reword). ``--unattended`` is for a writer nobody reads before the
post goes out: @mentions are held, and a missing registry or any failure is ``unavailable``.
``--hold TARGET`` (unattended) also files a held post as a desk item and adds its URL to
the JSON as ``desk_item``.

Usage from a script::

    printf '%s' "$BODY" | public-text-guard check --repo octo/app --unattended
"""

from __future__ import annotations

import argparse
import json
import sys


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
    c.add_argument("--budget", type=float, help="seconds for every lookup together")
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
            budget=args.budget,
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
