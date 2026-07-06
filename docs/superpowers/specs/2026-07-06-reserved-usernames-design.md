# Reserved usernames — design

Issue: https://github.com/MESH-Research/knowledge-commons-profiles/issues/630

## Goal

Prevent people from registering usernames that should be protected — platform
and institution names (`knowledgecommons`, `humanitiescommons`, `kcworks`),
and staff/official-sounding names (`admin`, `superuser`, `tech_support`, …).

The list of prohibited terms must be editable in the Django admin by
non-technical staff. The only special character they need to learn is `*`
(asterisk) for wildcards — no regular expressions.

## Where this plugs in

Signup lives in `cilogon/views.py`:

- `register()` handles the POST from `templates/cilogon/new_user.html`.
- It calls `validate_form(email, full_name, request, username)`, which pushes
  `messages.error(...)` for each problem and returns an `errored` flag.
- The template already renders `messages`, so a new `messages.error(...)` is
  displayed with no template change required.

So enforcement is a single new check inside `validate_form()`.

## Components

### 1. `ReservedUsername` model (`cilogon/models.py`)

| Field     | Type                | Purpose                                        |
|-----------|---------------------|------------------------------------------------|
| `pattern` | `CharField(unique)` | The simple term, optionally containing `*`.    |
| `note`    | `CharField(blank)`  | Optional admin memo ("why is this reserved").  |
| `active`  | `BooleanField`      | Toggle a term off without deleting it.         |

Registered in `cilogon/admin.py` with `list_display`, `search_fields`, and
`list_filter` on `active`. `help_text` on `pattern` explains the matching rules
in plain language.

### 2. Matcher (`cilogon/reserved_usernames.py`)

A small, pure, dependency-free module so it can be unit-tested in isolation.

```
normalize(value)         -> lowercase; strip spaces, "-" and "_"
pattern_to_regex(pattern) -> escaped, "*" -> ".*", anchored at the start
username_is_reserved(username, patterns) -> bool
```

**Matching rules (what an admin needs to know):**

1. Matching ignores **case**, **hyphens** and **underscores**. So one entry
   `knowledgecommons` blocks `knowledge_commons`, `Knowledge-Commons`,
   `knowledgeCommons`, etc.
2. A term blocks any username that **begins with** it (prefix match). So
   `admin` blocks `admin`, `admin123`, `administrator` — but not `badminton`.
   This automatically handles trailing junk like `knowledgecommons123` without
   the admin having to add anything.
3. `*` means "any characters here". Use `*word*` to block a word appearing
   anywhere (`*support*` blocks `techsupport`, `mysupportbot`).

Implementation detail: each pattern compiles to `^` + escaped-with-`.*`, matched
with `re.match` (start-anchored, end open) against the normalized username. The
normalized username has separators removed, and the pattern is normalized the
same way (keeping `*`), so admins never enter separator permutations.

### 3. Enforcement (`cilogon/views.py::validate_form`)

After the existing format/length checks, load the active patterns and, if the
username is reserved, set `errored = True` and add a polite message:

> "That username isn't available — it's reserved for the platform or its staff.
> Please choose a different one."

The reserved list is static configuration (not per-user data), so it carries no
user-enumeration timing concern and can be checked inline.

### 4. Seed data (data migration)

A data migration inserts the initial list. Because separators and case are
ignored, the issue's ~40 entries collapse to a smaller set of roots. Shipped in
a migration so it installs automatically but remains editable/deletable in admin.

Proposed roots (each is a prefix term):

- Platform/institution: `knowledgecommons`, `humanitiescommons`, `hcommons`,
  `kcworks`, `mla`, `mesh`, `commons`
- Admin/official: `admin`, `administrator`, `superuser`, `root`, `staff`,
  `support`, `techsupport`, `helpdesk`, `moderator`, `sysadmin`, `system`,
  `official`, `security`, `abuse`, `postmaster`, `webmaster`, `noreply`,
  `hostmaster`, `owner`

(Final list is a product call; admins can prune/extend freely.)

## Testing (TDD, red first)

Pure matcher unit tests (isolated, no DB):

- prefix match blocks `admin`, `admin123`, `administrator`
- prefix match does **not** block `badminton` (bare `admin`)
- case-insensitive: `ADMIN` blocked
- separator-insensitive: `knowledge_commons`, `knowledge-commons`,
  `knowledgeCommons` all blocked by `knowledgecommons`
- wildcard: `*support*` blocks `techsupport`, `mysupportbot`
- ordinary names pass (`martineve`, `jsmith`)
- empty pattern list blocks nothing

Integration tests (register flow):

- POST with a reserved username -> error message shown, no `Profile`/`User`
  created
- POST with an allowed username -> passes the reserved check (proceeds)

Model/admin: `ReservedUsername` is creatable and matching reads only `active`
rows.

## Out of scope

- Retroactively renaming existing usernames that would now be reserved.
- Applying the check anywhere other than signup (this is the only place a
  brand-new username is chosen).
