# Profile Badges — Design

Date: 2026-08-04

## Purpose

Add a staff-managed "Badges" section to profile pages. Staff award badges to
users; users cannot award or remove badges themselves, but can hide the whole
badge box from their profile. The section appears first in the right-hand
profile column by default, and users can reorder it like any other section.

## Data model (`newprofile`)

- `Badge`
  - `title` — CharField(255), the badge name shown as tooltip/label
  - `alt_text` — TextField, accessible description used as the image `alt`
  - `image` — ImageField uploading to `badges/` in media storage
  - `order` — IntegerField (default 0, indexed); `Meta.ordering = ["order",
    "title"]` controls display order everywhere
  - `profiles` — M2M to `Profile` through `ProfileBadge`, related name
    `badges` (so templates use `profile.badges.all`)
- `ProfileBadge` (through table)
  - `badge` FK, `profile` FK, `awarded_at` auto timestamp
  - unique constraint on (badge, profile)
- `Profile.show_badges` — BooleanField(default True), the user-facing hide
  toggle.

## Seed data

The six sample images in `KQBadges/` are committed to
`knowledge_commons_profiles/newprofile/fixtures/badges/` and a data migration
creates six `Badge` rows (placeholder titles "Badge 1"–"Badge 6", order 1–6)
by copying the files into media storage. The migration skips any badge whose
title already exists and is a no-op if the fixture files are missing (so
re-runs and odd deploy environments are safe). Reverse migration deletes the
seeded rows.

## Display

- `templates/newprofile/fragments/badges.html` — renders a "Badges" content
  card only when `profile.show_badges` is on and the profile has at least one
  badge. Badges render as images (alt = `alt_text`, tooltip = `title`)
  in `Badge.order` order.
- `templates/newprofile/fragments/badges_edit.html` — sortable card
  (`id="badges_edit"`, class `sortable-item`) with the crispy
  `show_badges` checkbox, mirroring `mastodon_feed_edit.html`. The existing
  jQuery-UI sortable + `save_profile_order` machinery picks it up with no JS
  changes.
- `"badges"` is added at the head of `settings.PROFILE_FIELDS_RIGHT`.
- `process_orders` currently appends allowed-but-unsaved section ids to the
  end of a user's saved order, and existing tests pin that behaviour for
  ordinary sections. Badges must arrive *first* for existing users too, so
  `process_orders` special-cases `badges`: when it is absent from a user's
  saved right-hand order it is moved to the front instead of appended. Once
  a user drags the box, their saved order includes `badges` and is honoured
  verbatim.

## Admin

- `BadgeAdmin`: list shows thumbnail, title, order, award count; `order` is
  list-editable; search on title. A `ProfileBadge` inline (autocomplete on
  profile) allows individual award/removal.
- Mass award/remove: a custom admin view on each badge
  (`admin/newprofile/badge/<id>/mass-award/`) with a textarea of
  comma-separated usernames and an Award/Remove choice. It reports how many
  profiles were awarded/removed, which usernames were unknown, and which were
  already/not holders. Wrapped in the admin's staff-only permissions.
- `ProfileBadge` is not separately registered; the inline and mass view cover
  management.

## Security

- No non-admin URL can mutate badge awards. `ProfileForm` gains only
  `show_badges`; badge M2M fields are never exposed to users.

## Testing

Red/green TDD: failing tests first for model behaviour and ordering, the
`process_orders` prepend rule, mass award/remove (including unknown
usernames, duplicates, and non-staff rejection), `ProfileForm` exposing
`show_badges` and nothing badge-mutating, and fragment rendering guards
(hidden when `show_badges` is off or the user has no badges).
