# pubcheck.correspond

correspond’s `before_send` check: the publication check for every write correspond makes.

Set it once at the top of correspond’s config file (`~/.config/correspond/config.toml`):

```default
before_send = "pubcheck.correspond:before_send"
```

For a write whose audience is **public** (correspond resolves an unknown audience to
public), it runs [`pubcheck.check()`](pubcheck.html.md#pubcheck.check) on the draft’s title and text, unattended: a
correspond write has nobody reading it before it goes out, so @mentions are held and an
unavailable check holds too (fail closed). Assignees and the `notify` list notify people,
so they hold as mentions; labels, a milestone, a discussion category and attachment names
are checked with the text. Any other audience (a private repo, the operator’s own devices)
passes unchanged.

A held write raises `correspond.errors.NeedsApproval` with the categories (never the
text) in its details. On a real send, not a dry run, the held post also becomes a desk
item ([`pubcheck.hold.file_hold()`](pubcheck.hold.html.md#pubcheck.hold.file_hold)), whose URL is in the details as `desk_item`.
[`make_before_send()`](#pubcheck.correspond.make_before_send) builds a check with other settings or another `hold`.

Not covered: the contents of attached files (the check reads prose, not files).

### Module Attributes

| [`before_send`](#pubcheck.correspond.before_send)(ref, draft, audience, \*[, ...])   | The check correspond's config names: `before_send = "pubcheck.correspond:before_send"`.   |
|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|

### Functions

| [`before_send`](#pubcheck.correspond.before_send)(ref, draft, audience, \*[, ...])   | The check correspond's config names: `before_send = "pubcheck.correspond:before_send"`.   |
|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| [`make_before_send`](#pubcheck.correspond.make_before_send)(\*[, config, hold, check])    | A correspond `before_send` check; `config` overrides pubcheck's settings (`hold_repo`…).  |

### pubcheck.correspond.before_send(ref, draft, audience, , operation='send', dry_run=False, message_id=None, \*\*context)

The check correspond’s config names: `before_send = "pubcheck.correspond:before_send"`.

### pubcheck.correspond.make_before_send(\*, config=None, hold=<function file_hold>, check=<function check>)

A correspond `before_send` check; `config` overrides pubcheck’s settings (`hold_repo`…).

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis), [`None`](https://docs.python.org/3/builtins/constants.html#None)]
