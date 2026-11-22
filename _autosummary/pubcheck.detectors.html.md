# pubcheck.detectors

The detectors: what in a text a public reader may not see.

A detector is a callable `(text, ctx) -> [(category, term)]`. `ctx` carries what the
check knows about the post: `repo` (the target), `surface` (`git commit`, `gh issue
create`, `correspond send`…), `terms` (the registry’s terms for that repo) and
`private_slugs` (repos known to be private). Whitespace is normalised before any detector
runs, so a name wrapped across lines still matches. `term` is what a local author needs
to reword the text; it never leaves the machine (the CLI prints it only with `--terms`,
and the log never holds it). A credential’s term is its pattern name, never the secret.

- `registry`: a term of an acquaint record a public reader may not see;
- `owner-relation`: “the operator stated”, “the owner’s preference”, “my agents”…
  (text inside double quotes, curly quotes or backticks is skipped: a quoted phrase is an
  example, not a claim);
- `private-ref`: a repo known to be private, a private companion
  (`<private_owner>/_<name>`), this machine’s home folder, and the operator’s
  `private_patterns` (`ctx["private_patterns"]`, from the settings);
- `session-link`: `claude.ai/code/session_…` (not on commits, whose session links a
  commit hook strips);
- `credential`: a credential-shaped string (`openloops.egress.find_credentials()`),
  and, when the operator sets `credential_scanner`, what that external scanner finds
  ([`scanner_credential()`](#pubcheck.detectors.scanner_credential));
- `mention`: an `@login` or `@org/team` outside code, which notifies a person:
  sending it is messaging them. Only in [`UNATTENDED_DETECTORS`](#pubcheck.detectors.UNATTENDED_DETECTORS), since an attended
  author chose to notify.

```pycon
>>> findings(["As the owner asked, we fixed it"], {})
[('owner-relation', 'the owner asked')]
>>> findings(["ping @octocat about it"], {}, detectors=UNATTENDED_DETECTORS)
[('mention', '@octocat')]
>>> findings(["write to me@example.org or see `@octocat`"], {}, detectors=UNATTENDED_DETECTORS)
[]
```

### Module Attributes

| [`SCANNER_ARGS`](#pubcheck.detectors.SCANNER_ARGS)         | The arguments of a gitleaks-compatible scanner's `stdin` command (betterleaks 1.x and gitleaks 8 share them): a JSON report on stdout, the secret redacted, exit 0 on a find.   |
|-----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`SCANNER_ENV_DROPPED`](#pubcheck.detectors.SCANNER_ENV_DROPPED)  | Environment variables that would switch a scanner's live validation on; never passed.                                                                                           |
| [`SCANNER_TIMEOUT`](#pubcheck.detectors.SCANNER_TIMEOUT)      | Seconds the scanner may take, within what is left of the check's budget.                                                                                                        |
| [`DETECTORS`](#pubcheck.detectors.DETECTORS)            | the seam is this tuple.                                                                                                                                                         |
| [`UNATTENDED_DETECTORS`](#pubcheck.detectors.UNATTENDED_DETECTORS) | nobody chose to notify that person.                                                                                                                                             |

### Functions

| [`credential`](#pubcheck.detectors.credential)(text, ctx)                 | Credential-shaped strings, named by pattern; the secret itself is never returned.    |
|----------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`dictionary_words`](#pubcheck.detectors.dictionary_words)()                    | Lowercased words of the system dictionary; empty when the machine has none.          |
| [`findings`](#pubcheck.detectors.findings)(texts, ctx, \*[, detectors]) | `[(category, term)]`, each once, found by `detectors` in any of `texts`.             |
| [`is_common`](#pubcheck.detectors.is_common)(word)                       | A stop word or a dictionary word (any case).                                         |
| [`is_scanner_finding`](#pubcheck.detectors.is_scanner_finding)(finding)           | True for a credential an external scanner found (its term is `<scanner>:<rule>`).    |
| [`mention`](#pubcheck.detectors.mention)(text, ctx)                    | `@login` and `@org/team` outside code spans and blocks: each notifies someone.       |
| [`owner_relation`](#pubcheck.detectors.owner_relation)(text, ctx)             | Phrases that relay the owner's own preferences, corrections or relations.            |
| [`private_ref`](#pubcheck.detectors.private_ref)(text, ctx)                | Private repos, companions, the operator's private patterns and this machine's paths. |
| [`registry`](#pubcheck.detectors.registry)(text, ctx)                   | The registry's terms for this repo (`ctx["terms"]`) found in the text.               |
| [`scanner_credential`](#pubcheck.detectors.scanner_credential)(text, ctx)         | What an external secret scanner finds, named `<scanner>:<rule id>`.                  |
| [`session_link`](#pubcheck.detectors.session_link)(text, ctx)               | Claude session links (not on commits, whose session links a commit hook strips).     |

### Exceptions

| [`ScannerUnavailable`](#pubcheck.detectors.ScannerUnavailable)   | A configured scanner did not run; an unattended check must not pass without it.   |
|-----------------------------------------------------------------------|-----------------------------------------------------------------------------------|

### pubcheck.detectors.DETECTORS *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Mapping](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)], [list](https://docs.python.org/3/builtins/stdtypes.html#list)], ...]* *= (<function registry>, <function owner_relation>, <function private_ref>, <function session_link>, <function credential>, <function scanner_credential>)*

the seam is this tuple.

* **Type:**
  The detectors for an attended writer (a Claude Code session)

### pubcheck.detectors.SCANNER_ARGS *= ('stdin', '--report-format', 'json', '--report-path', '-', '--no-banner', '--redact', '--exit-code', '0')*

The arguments of a gitleaks-compatible scanner’s `stdin` command (betterleaks 1.x and
gitleaks 8 share them): a JSON report on stdout, the secret redacted, exit 0 on a find.
Never a validation flag: checking whether a credential is live sends it to its vendor.

### pubcheck.detectors.SCANNER_ENV_DROPPED *= ('BETTERLEAKS_VALIDATE', 'BETTERLEAKS_ANALYZE')*

Environment variables that would switch a scanner’s live validation on; never passed.

### pubcheck.detectors.SCANNER_TIMEOUT *= 5.0*

Seconds the scanner may take, within what is left of the check’s budget.

### *exception* pubcheck.detectors.ScannerUnavailable

Bases: [`RuntimeError`](https://docs.python.org/3/builtins/exceptions.html#RuntimeError)

A configured scanner did not run; an unattended check must not pass without it.

### pubcheck.detectors.UNATTENDED_DETECTORS *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Mapping](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)], [list](https://docs.python.org/3/builtins/stdtypes.html#list)], ...]* *= (<function registry>, <function owner_relation>, <function private_ref>, <function session_link>, <function credential>, <function scanner_credential>, <function mention>)*

nobody chose to notify that person.

* **Type:**
  An unattended writer also holds every @mention

### pubcheck.detectors.credential(text, ctx)

Credential-shaped strings, named by pattern; the secret itself is never returned.

### pubcheck.detectors.dictionary_words()

Lowercased words of the system dictionary; empty when the machine has none.

* **Return type:**
  [`frozenset`](https://docs.python.org/3/builtins/stdtypes.html#frozenset)

### pubcheck.detectors.findings(texts, ctx, \*, detectors=(<function registry>, <function owner_relation>, <function private_ref>, <function session_link>, <function credential>, <function scanner_credential>))

`[(category, term)]`, each once, found by `detectors` in any of `texts`.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]

### pubcheck.detectors.is_common(word)

A stop word or a dictionary word (any case).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### pubcheck.detectors.is_scanner_finding(finding)

True for a credential an external scanner found (its term is `<scanner>:<rule>`).

The built-in patterns name their findings without a colon, and only they are known
to [`pubcheck.hold.redact()`](pubcheck.hold.html.md#pubcheck.hold.redact).

```pycon
>>> is_scanner_finding(("credential", "betterleaks:slack-webhook-url"))
True
>>> is_scanner_finding(("credential", "github_token"))
False
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### pubcheck.detectors.mention(text, ctx)

`@login` and `@org/team` outside code spans and blocks: each notifies someone.

### pubcheck.detectors.owner_relation(text, ctx)

Phrases that relay the owner’s own preferences, corrections or relations.

### pubcheck.detectors.private_ref(text, ctx)

Private repos, companions, the operator’s private patterns and this machine’s paths.

### pubcheck.detectors.registry(text, ctx)

The registry’s terms for this repo (`ctx["terms"]`) found in the text.

### pubcheck.detectors.scanner_credential(text, ctx)

What an external secret scanner finds, named `<scanner>:<rule id>`.

Off unless the operator sets `credential_scanner` (`betterleaks` is the one
weighed in thorwhalen/pubcheck#3; any gitleaks-compatible `stdin` command works,
with `credential_scanner_args` for another argument list). It adds the long tail of
vendor formats to the built-in [`credential()`](#pubcheck.detectors.credential), which stays.

It runs once per check, over every text of the post together (`whole_batch`). The
text goes on stdin, never in argv; the report is redacted; validation is never asked
for; the scanner runs from a neutral folder, so a repo’s own scanner config is not
read, and only from an absolute path outside the current folder.

A scanner that is missing, fails or runs out of time is a gap, logged every time. An
attended check carries on with the built-in patterns (and says so once on stderr);
an **unattended** one raises [`ScannerUnavailable`](#pubcheck.detectors.ScannerUnavailable), so the check is
`unavailable` and the text is held, as any other lookup that cannot be made.

```pycon
>>> scanner_credential("AKIA...", {})  # no scanner configured
[]
```

### pubcheck.detectors.session_link(text, ctx)

Claude session links (not on commits, whose session links a commit hook strips).
