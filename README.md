# pubcheck

One publication check for every writer: is this text fit for the repository it is about to be published to?

```bash
pip install pubcheck
printf '%s' "$BODY" | public-text-guard check --repo octo/app --unattended
# exit 0 pass, 1 flag, 2 unavailable; one JSON line naming the categories, never the text
```

```python
from pubcheck import check

v = check("As the owner asked, we fixed it.", repo="octo/app")
v.decision, v.categories   # ('flag', ['owner-relation'])
```

A private target passes untouched. A public one, or one whose visibility is unknown, is scanned for:

- `registry`: names from the owner's acquaint records that a public reader may not see (`acquaint disclosure --audience '{"scope": "public"}'`);
- `owner-relation`: the owner's own preferences, corrections or relations ("the operator stated", "my agents");
- `private-ref`: repos known to be private, private companions, this machine's home folder, and your own `private_patterns`;
- `session-link`: Claude session links;
- `credential`: credential-shaped strings (the patterns of `openloops.egress`);
- `mention`: `@login` and `@org/team` outside code, for an **unattended** writer only, since a mention notifies a person.

## Attended and unattended writers

An attended writer (an agent session someone is driving) proceeds without the registry when acquaint cannot be asked, and the gap is logged. An unattended writer (a connector, a scheduled job, anything that posts with nobody reading first) fails closed: a missing registry, a lookup out of time or any error is `unavailable` (exit 2), and the text must be held, never posted.

## Three ways in, one check

- **Python**: `pubcheck.check(text, repo=..., title=..., unattended=...)` returns a `Verdict`.
- **CLI**: `public-text-guard check --repo OWNER/REPO [--unattended] [--title T] [--hold TARGET] [--terms]`, the text on stdin. `--terms` adds the matched terms, for a local author who has to reword; `--hold` files a held post as a desk item.
- **correspond**: at the top of `~/.config/correspond/config.toml`, `before_send = "pubcheck.correspond:before_send"`. Every write to a public audience is checked unattended; a held one raises correspond's `NeedsApproval` with the categories, and on a real send (not a dry run) becomes a desk item.

## Held posts become desk items

With `hold_repo` set, a held post is filed as an issue in that private repo with the label the desk reads (`hold_label`, default `escalate`): the target, the title, the text (credential-shaped strings redacted) and the categories, so it can be published as is, edited or dropped. The hold repo's visibility is asked of GitHub just before filing, and nothing is copied to a repo that is not private. The same text held twice is filed once. With no `hold_repo`, the post is still held; only the desk item is missing.

## Settings

`~/.config/pubcheck/config.toml` (`$PUBCHECK_CONFIG` names another file), then environment variables, then keyword arguments:

| key | env | default |
|---|---|---|
| `hold_repo` | `PUBCHECK_HOLD_REPO` | unset (no desk item) |
| `hold_label` | `PUBCHECK_HOLD_LABEL` | `escalate` |
| `budget_seconds` | `PUBCHECK_BUDGET_SECONDS` | `12` |
| `private_owner` | `PUBCHECK_PRIVATE_OWNER` | unset: the account whose `<owner>/_<name>` repos are private companions |
| `private_issues` | `PUBCHECK_PRIVATE_ISSUES` | unset: where context with no companion goes |
| `private_patterns` | (config only) | none: regexes for private references, such as working folders |

## Caches and log

Visibility comes from a cache shared with other tools (`~/.cache/priv/repo_visibility/`), then `gh repo view`. The vocabulary is cached an hour in `~/.cache/public-text-guard/`. Decisions worth keeping go to `~/.local/state/public-text-guard/events.jsonl` (mode 0600): categories, repo, writer, a short hash of the text, an error's type and an override's reason; never the text or the matched terms.

## System requirements

`gh` (authenticated) for visibility lookups and desk items; `acquaint` for the registry. Without `gh`, visibility is unknown and so public; without `acquaint`, an unattended check is unavailable.
