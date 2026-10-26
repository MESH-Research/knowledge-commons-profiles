# UP Salesforce (External Client App)

A self-contained integration with the Association of University Presses
(UP) Salesforce org that authenticates with a **Salesforce External Client
App** using the OAuth 2.0 **client-credentials** flow.

It exists alongside, and does not touch, the legacy integration in
`cilogon/sync_apis/up.py`, which uses a Connected App refresh token that can
no longer be rotated. Nothing in production is switched over by this app:
`rest_api/sync.py` still registers the legacy `UP` class. When the new
credentials are confirmed working, `UPExternalClientApp` (in `sync.py`) can
be registered there instead because it implements the same `SyncClass`
interface.

## Configuration

| Environment variable         | Purpose                                                        | Default                                 |
| ---------------------------- | -------------------------------------------------------------- | --------------------------------------- |
| `UP_ECA_CONSUMER_KEY`        | The External Client App consumer key (`client_id`)             | empty                                   |
| `UP_ECA_CONSUMER_SECRET`     | The External Client App consumer secret (`client_secret`)      | empty                                   |
| `UP_ECA_LOGIN_URL`           | The org's My Domain login URL                                  | `https://aupresses.my.salesforce.com`   |
| `UP_ECA_API_VERSION`         | REST API version used for data calls                           | `v62.0`                                 |
| `UP_ECA_TOKEN_CACHE_TIMEOUT` | Seconds a token is reused from the cache                       | `900`                                   |

Rotating the secret is a matter of changing `UP_ECA_CONSUMER_SECRET` and
restarting (or running `up_eca_token --refresh`).

On the Salesforce side the External Client App needs the client-credentials
flow enabled in its OAuth policies and a **Run As** user selected; every
API call is made as that user, so it needs read access to `Contact` and
the `UP_Commons_Eligible__c` / `Current_Staff__c` fields.

## How it works

- `auth.py` — `ClientCredentialsTokenProvider` posts
  `grant_type=client_credentials` to `/services/oauth2/token`, caches the
  resulting token (Salesforce returns no `expires_in` or refresh token) and
  exposes `invalidate()`.
- `client.py` — `SalesforceRestClient` adds the bearer token, resolves
  paths against the token's `instance_url`, retries once with a fresh token
  on `401`, follows `nextRecordsUrl`, and raises `UPSalesforceError` with
  Salesforce's `errorCode`/`message` on failure.
- `sync.py` — `UPExternalClientApp` reproduces the legacy sync behaviour:
  find a `Contact` by (normalised, SOQL-escaped) email, return the
  `AccountId` as the sync id, and report `UP_Commons_Eligible__c` as
  membership. Results are cached per email for `UP_ECA_CACHE_TIMEOUT`.

## Management commands

All commands accept `--json` for machine-readable output and exit with a
`CommandError` carrying Salesforce's message when a call fails.

```
uv run ./manage.py up_eca_token [--refresh]      # obtain a token; prints instance URL and a masked token
uv run ./manage.py up_eca_whoami                 # identity of the Run As user (userinfo endpoint)
uv run ./manage.py up_eca_limits [--all]         # org API limits: a cheap end-to-end check
uv run ./manage.py up_eca_query ["SOQL"] [--all] # ad-hoc SOQL; --all follows pagination
uv run ./manage.py up_eca_lookup EMAIL... | --username USERNAME
                                                 # contact lookup + eligibility via the sync class
```
