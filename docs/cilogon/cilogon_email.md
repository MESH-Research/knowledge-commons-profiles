# CILogon and Missing/Empty Email Values

> **Note**: This documentation refers to knowledge-commons-profiles version 4.27.1

## Why this problem exists

CILogon is a federated identity broker. When a user authenticates, CILogon
relays an OIDC `id_token`/userinfo payload that was assembled from whatever
the user's home identity provider (IdP) released. The set of released claims
is decided by the upstream IdP and the federation's attribute-release policy,
**not** by us and not reliably by CILogon itself.

The `sub` (subject identifier) claim is always present — it is the stable,
opaque identifier CILogon guarantees. The `email` claim is **not**
guaranteed. Depending on the IdP behind CILogon, the userinfo we receive may:

- omit `email` entirely (the key is absent from the dict), or
- include `email` as an empty string, or
- include a valid `email`.

This is expected behaviour from a federated broker and cannot be fixed on our
side: we cannot compel an upstream institutional IdP to release an email
address. Any code path that assumed `userinfo["email"]` was always a usable
string would be incorrect.

## Why it does not affect what we are doing

Account identity in this application is keyed on the CILogon `sub`, never on
the email address. The email released by CILogon is treated as advisory only.
The authoritative email is the one the user supplies through our own
association/registration form, which is stored on the `Profile`.

The relevant flow lives in
`knowledge_commons_profiles/cilogon/views.py` and
`knowledge_commons_profiles/cilogon/oauth.py`:

### Returning users (a `SubAssociation` already exists)

`callback()` (`views.py:174`) looks the account up purely by `sub`:

```python
sub_association = SubAssociation.objects.filter(
    sub=userinfo.get("sub", "")
).first()
```

Login itself is performed by `find_user_and_login()`
(`oauth.py:292`), which uses `sub_association.profile.email` — the email
already stored on the `Profile` from a previous association — and never the
email from the current CILogon response. A missing or empty CILogon email has
no effect on the user's ability to log in.

The only place the callback consumes the CILogon email
(`views.py:230-239`) is fully guarded:

```python
if (
    userinfo.get("email")
    and userinfo.get("email") != sub_association.profile.email
):
    if userinfo.get("email") not in sub_association.profile.emails:
        sub_association.profile.emails.append(userinfo.get("email"))
        sub_association.profile.save()
```

`userinfo.get("email")` returns `None` when the key is absent and `""` when
it is empty; both are falsy, so the block is simply skipped. This is purely
an opportunistic "has CILogon told us about a new secondary address?" step.
Nothing breaks when it is skipped.

### New users (no `SubAssociation` yet)

When no `SubAssociation` is found, `callback()` redirects to the association
view (`views.py:association`). The email used to locate or create the account
comes from the form the user fills in:

```python
email = request.POST.get("email")
```

It is then used to find an existing `Profile` (by primary `email` or by the
`emails` array) or, failing that, to register a new account. The CILogon
email is only ever used to *pre-fill* the form field as a convenience
(`views.py:1233`, `userinfo.get("email", "")`); when CILogon supplies
nothing, the field simply renders empty and the user types their address.
The form is the authoritative source of the email, so the account-matching
and registration paths do not depend on CILogon returning one.

### Identity broker payload

`build_broker_redirect()` (`oauth.py:742`) emits an encrypted payload to
third-party broker apps. It includes the CILogon-sourced value as
`userinfo.email` (which degrades to `""` when CILogon omits it) but also
always includes the authoritative `Profile` email separately:

```python
payload = {
    "userinfo": {
        "sub": userinfo.get("sub", ""),
        "email": userinfo.get("email", ""),   # advisory; may be ""
        ...
    },
    "kc_username": profile.username,
    "primary_email": profile.email,           # authoritative
    "other_emails": profile.emails,
    ...
}
```

Consuming apps should read `primary_email` for the user's real address;
`userinfo.email` is the raw, possibly-empty broker value and is included only
for completeness.

## Summary

| Path | Depends on CILogon email? |
|------|---------------------------|
| Returning-user login / account match (by `sub`) | No |
| Opportunistic secondary-email capture (`views.py:230-239`) | No — guarded, skipped when absent |
| New-user association / registration | No — email comes from our form |
| Identity broker payload | No — `primary_email` from `Profile` is authoritative |

A missing or empty `userinfo["email"]` from CILogon is therefore an expected
condition that the system already handles correctly. No code change is
required; this document exists so the behaviour is not re-investigated.
