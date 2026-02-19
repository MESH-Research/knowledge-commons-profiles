# Testing Guide for Knowledge Commons IDMS and New Profiles

This document describes what testers need to know and what areas require
coverage. File bugs and enhancement requests at
<https://github.com/MESH-Research/knowledge-commons-profiles/issues>.

---

## Environments

Three deployments are available for testing. All require VPN access or IP
whitelisting.

| Site | URL |
|------|-----|
| Profiles | <https://profile.hcommons-dev.org> |
| Works | <https://works.hcommons-staging.org> |
| Commons | <https://hcommons-staging.org> |

---

## ⚠️ CRUCIAL NOTE: Unexpected Error Pages When Navigating

Many links within the profile area (and across the Commons sites) still point
to legacy WordPress/BuddyPress URLs that have not yet been intercepted and
redirected to the new profiles application. Clicking these links is likely to
lead to error pages or unexpected behaviour.

**This is expected.** We are progressively catching and redirecting these URLs
via nginx rewrite rules ([#301](https://github.com/MESH-Research/knowledge-commons-profiles/issues/301)).
If you encounter an error page while clicking around the profile area, please
check whether the URL in question is already listed in
[#301](https://github.com/MESH-Research/knowledge-commons-profiles/issues/301)
before filing a new bug. If it is not listed there, please add a comment to
that issue with the URL that caused the error.

---

## Authentication

### Login

Login on all three sites goes through CILogon. Each site maintains its own
session, so logging in on one does not automatically log you in on the others.
However, because you have already authenticated with CILogon, the login flow on
subsequent sites should be fast -- you will be redirected through CILogon and
back without needing to re-enter credentials.

### Logout

Logout is intended to be universal: logging out on any one site should log you
out of all three. **Known issue:** universal logout is not currently working on
works.hcommons-staging.org. We are working to resolve this. For now, logging
out on Profiles or Commons should still log you out of both of those sites.

### Account association (first login)

When a user logs in for the first time and has no existing Knowledge Commons
account, they are taken to the account association page. This is likely the most
complex part of the login flow and needs careful testing.

**Existing account:** The user can enter the email address associated with their
existing KC account. We send a verification email with a confirmation code. When
they click the link, the new login method is associated with their account and
they are logged in immediately.

**New account:** The user can instead create a new account. We ask for minimal
information to get them started quickly. After account creation, verify that the
user can then log in successfully across all three applications (Profiles, Works,
and Commons).

---

## Profile Management

Once logged in, users can manage their profile settings at:

    https://profile.hcommons-dev.org/members/USERNAME/settings/

where `USERNAME` is the user's KC ID. This page is linked from the My Profile
page (<https://profile.hcommons-dev.org/my-profile/>) under "Manage Login
Methods and Emails".

From this settings page, users can:

- **Associate login methods** with their account
- **Change network memberships** for open networks
- **Add, remove, or change primary and secondary email addresses**
- **View network registrations** derived from external APIs -- for example, if
  one of your email addresses appears in the MLA API as belonging to an active
  member, your MLA network membership will show as active. Similarly, MSU
  network membership depends on having an MSU email address in your profile.

---

## New Profiles

User profiles are available at URLs such as:

- <https://profile.hcommons.org/members/kfitz/>
- <https://profile.hcommons.org/members/martin_eve/>

The following areas all need testing.

### Viewing profiles

- Profile displays correctly for anonymous (logged-out) visitors
- All visible sections render: name, title, affiliation, bio, education,
  academic interests, social links, works deposits, CV, blog posts, Mastodon
  feed, Commons groups, Commons sites, and recent activity
- Profile and cover images display correctly

### Editing profiles

The edit profile page is at `/edit-profile/`. Test that users can:

- Edit name, title, institutional affiliation, and website
- Edit social media handles (Mastodon, Twitter/X, Bluesky, GitHub, ORCID,
  LinkedIn, Facebook)
- Edit rich-text content sections: About, Education, Upcoming Talks, Projects,
  Publications, Memberships
- Add and remove academic interests using the autocomplete/tag widget
- Upload, crop, and save a profile avatar (JPEG, PNG, or WebP)
- Upload, crop, and save a cover image (JPEG, PNG, or WebP)
- Upload a CV (PDF, DOC, or DOCX; max 10 MB) and clear/remove it
- Toggle visibility for individual profile sections (works, CV, blog posts,
  Mastodon feed, Commons groups, Commons sites, recent activity, academic
  interests, projects, publications, education)
- Reorder profile sections by dragging them between and within the left and
  right columns
- Changes persist after saving and display correctly on the public profile

### Works deposits

- Works display on the profile with correct citation formatting
- Users can change their citation style and see the display update
- Users can reorder works by dragging
- Users can toggle visibility of individual works
- Changes to works ordering and visibility persist

### Members directory and search

- The members directory at `/members/` paginates correctly
- Searching for members by username or name returns correct results
- The global search at `/search/` returns results across people, works, and
  blog posts

---

## Superuser and Staff Functions

These features should only be visible to users with superuser or staff status.
Verify that ordinary users cannot see or access them.

### Bestow/remove superadmin rights

Superusers should see a button on other users' profiles to grant or revoke
superadmin status. Test that:

- The button appears only for superusers
- Granting superadmin rights works and takes effect immediately
- Revoking superadmin rights works and takes effect immediately
- Non-superusers never see this button

### Manage User Roles

Staff users should see a link to the role management page. This page allows
overrides to be set that grant network membership even when an external API
would deny it. Test that:

- The page is accessible only to staff
- Overrides can be created, modified, and removed
- Overrides take effect on the affected user's profile

### Editing other users' profiles

Staff users should be able to edit profiles belonging to other users. This has not been implemented yet and is tracked in [#300](https://github.com/MESH-Research/knowledge-commons-profiles/issues/300).

---

## KCWorks
- Try editing the metadata on an existing deposit
- Create a new version of an existing deposit
- Upload a new deposit
- Check to see if information changed in WordPress is propagated through to Works
- If testing as a non-priviledged user check to ensure that the link to their profile in the top menu bar is correct.

---

## Known Issues

- **Search is not working:** The global search at `/search/` currently returns
  a 403 error due to an authentication issue with the search service. Tracked
  in [#309](https://github.com/MESH-Research/knowledge-commons-profiles/issues/309).

- **Primary email changes are not synced to WordPress:** When a user changes
  their primary email address in Profiles, the change is not yet propagated to
  their WordPress account. Tracked in
  [#324](https://github.com/MESH-Research/knowledge-commons-profiles/issues/324).

- **Join group buttons not visible for regular users:** Non-admin users may not
  see "Join Group" buttons on group listing and individual group pages. Instead
  they see a message prompting them to join HC. Admin users are not affected.
  Tracked in
  [#330](https://github.com/MESH-Research/knowledge-commons-profiles/issues/330).

- **New user login issues (possibly resolved):** Users who create a new account
  via CILogon may be returned to the WordPress login form instead of being
  logged in, if their account exists in the Profiles API but not yet in
  WordPress. We believe this has been fixed but are awaiting confirmation from
  testing. Tracked in
  [#317](https://github.com/MESH-Research/knowledge-commons-profiles/issues/317).

---

## What to File

### Bugs

Issues where something is broken or behaves incorrectly. Examples:

- Being logged in as the wrong user
- Not being logged out after clicking logout
- Profile edits not saving
- Images failing to upload or display
- Sections visible when they should be hidden (or vice versa)
- Superuser-only controls appearing for regular users

### Enhancements

Requests for new functionality or changes to existing behaviour. Examples:

- "I need to be able to edit another user's profile"
- "I need a function to block a user"
- UI/UX suggestions

File all issues at <https://github.com/MESH-Research/knowledge-commons-profiles/issues>.
