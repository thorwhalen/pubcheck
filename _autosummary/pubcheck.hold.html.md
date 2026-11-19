# pubcheck.hold

A held post becomes a desk item: an issue in a private repo, labelled for the desk.

When an unattended writer’s text is held (flagged, or the check unavailable), nothing is
lost and nothing is refused silently: [`file_hold()`](#pubcheck.hold.file_hold) opens one issue in the hold repo
(setting `hold_repo`, by default the desk’s own private repo) with the label the desk
reads (`hold_label`, by default `escalate`), carrying the target, the title, the text
and the categories, so the owner can publish it as is, edit it, or drop it.

The hold repo receives the text, so it must be private: [`file_hold()`](#pubcheck.hold.file_hold) asks GitHub
(never a cache) just before filing, and files nothing when it is public or unknown, or
when no `hold_repo` is configured. Credential-shaped strings are redacted from the copy
([`redact()`](#pubcheck.hold.redact)). The same text held twice (a retry) is filed once: the body carries the
text’s hash, and an open issue with that hash is reused.

```pycon
>>> redact("token: ghp_" + "A1" * 18)
'token: [credential redacted: github_token]'
```

### Module Attributes

| [`PEM_BLOCK`](#pubcheck.hold.PEM_BLOCK)   | A whole PEM private key, BEGIN to END (the shared patterns match only the BEGIN line).   |
|--------------------------------------------------------------|------------------------------------------------------------------------------------------|

### Functions

| [`file_hold`](#pubcheck.hold.file_hold)(verdict, \*, target, text[, title, ...])   | File (or find) the desk item for a held post; `{"filed": bool, "url"?, "reason"?}`.   |
|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| [`hold_body`](#pubcheck.hold.hold_body)(verdict, \*, target, text, title[, ...])   | The desk item's body: why it was held, what would have been published, and the key.   |
| [`hold_key`](#pubcheck.hold.hold_key)(verdict, target)                            | What makes two holds the same desk item: the same text to the same target.            |
| [`hold_title`](#pubcheck.hold.hold_title)(target, title)                            | `held: <target>: <title>`, short enough for a desk card.                              |
| [`redact`](#pubcheck.hold.redact)(text)                                         | `text` with every credential-shaped string replaced by its pattern's name.            |

### pubcheck.hold.PEM_BLOCK *= re.compile('-----BEGIN [A-Z ]\*PRIVATE KEY-----.\*?(?:-----END [A-Z ]\*PRIVATE KEY-----|\\\\Z)', re.DOTALL)*

A whole PEM private key, BEGIN to END (the shared patterns match only the BEGIN line).

### pubcheck.hold.file_hold(verdict, , target, text, title=None, more=(), config=None, budget=None)

File (or find) the desk item for a held post; `{"filed": bool, "url"?, "reason"?}`. Never raises.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### pubcheck.hold.hold_body(verdict, , target, text, title, more=())

The desk item’s body: why it was held, what would have been published, and the key.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### pubcheck.hold.hold_key(verdict, target)

What makes two holds the same desk item: the same text to the same target.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### pubcheck.hold.hold_title(target, title)

`held: <target>: <title>`, short enough for a desk card.

```pycon
>>> hold_title("github:o/r", "Fix the thing")
'held: github:o/r: Fix the thing'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### pubcheck.hold.redact(text)

`text` with every credential-shaped string replaced by its pattern’s name.

```pycon
>>> redact("a -----BEGIN RSA PRIVATE KEY-----\nMIIE\nxyz\n-----END RSA PRIVATE KEY----- b")
'a [credential redacted: private_key_block] b'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
