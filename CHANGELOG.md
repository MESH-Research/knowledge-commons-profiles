## 2.35.0 (2025-11-03)

### Feat

- **members-list**: add a /members/ page and refactor newprofile views into separate modules
- **sync**: add arlisna sync and fix mla sync

### Fix

- **linting**: add noqa tc003 to decimal import

## 2.34.0 (2025-11-01)

### Feat

- **profiles**: add msu detection

### Fix

- **mla**: put mla credentials in a secret
- **sync**: update sync_ids every time, rather than relying on database, in case recinded

## 2.33.0 (2025-10-30)

### Feat

- **sync**: allow mla search to use multiple emails from comanager

## 2.32.1 (2025-10-30)

### Fix

- **urls**: change member to members

## 2.32.0 (2025-10-30)

### Feat

- **profiles**: add mla membership to profile page and sync on page load

### Fix

- **profiles**: change display of commons groups to align with academic interests
- **profiles**: change pluralisation of "slides"
- **sync**: update external sync logging in test command and Role str representatio
- **comanage**: fix bug in import of duplicate primary keys

## 2.31.0 (2025-10-29)

### Feat

- **comanage**: write comanage import commands

## 2.30.5 (2025-10-07)

### Fix

- **oauth**: add additional logging to determine malfunction in PHP interaction

## 2.30.4 (2025-09-29)

### Fix

- **stats**: relocate module after refactor

## 2.30.3 (2025-08-15)

### Fix

- **middleware/oauth**: fix security issues identified by llm

## 2.30.2 (2025-08-14)

### Fix

- **views**: remove erroneous security warning comment
- **views**: add transaction atomiticy to avoid race condition

## 2.30.1 (2025-08-08)

### Fix

- **mastodon**: fix mastodon formatting and add nocache option for debugging
- **citeproc**: remove unnecessary logging
- **base-template**: change base to load bootstrap first in order to fix the override resetting all colors
- **mysql**: add further handling in case mysql database is down

## 2.30.0 (2025-08-06)

### Feat

- **registration**: add registration form

## 2.29.2 (2025-07-21)

### Fix

- **health-check**: remove debug log

## 2.29.1 (2025-07-21)

### Fix

- **health-check**: stop middleware running on healthcheck, as this relies on the cache

## 2.29.0 (2025-07-18)

### Feat

- **logging**: try sentry logging feature
- **logging**: structured logging for all apps
- **webhook**: add webhook into association flow
- **debug**: add additional cilogon debug info
- **webhook**: more work on webhook polling
- **association-service**: add new confirmation page and fix email logic
- **cilogon**: add secure aes-encrypted exchange of userinfo
- **cilogon**: fix JWTClaims checking
- **cilogon**: add ability to decode passed userinfo

### Fix

- **logging**: add debug logging throughout views
- **logging**: change level of citeproc warning to debug
- **api**: add slug and name to groups api call to fix groups list
- **cilogon**: check session after get parameter for new signup
- **cilogon**: make sub unique
- **cilogon**: handle unicodedecodeerror
- **cilogon**: attempt to fix refresh token bug
- **cilogon**: attempt fix for refresh bug
- **cilogon**: set middleware to wipe session
- **cilogon**: handle arbitrary failures in refresh token middleware
- **cilogon**: fix middleware access to non-existent member
- **rest-api**: fixes to email visibility and serialization
- **email**: fix email host string and inject request object into context
- **email**: fix cilogon association email
- **email**: fix sparkpost url mangling
- **email**: fix to sparkpost url mangling
- **association-service**: change image url src to s3 rather than local static url
- **cilogon**: change next parameter to callback_next
- **cilogon**: fix redirect logic
- **cilogon**: fix to redirect logic
- **oauth**: fix forwarding logging
- **logging**: change loglevel

### Refactor

- **cilogon**: refactor code for fetching userinfo

## 2.28.0 (2025-07-17)

### Feat

- **cilogon**: fix JWTClaims checking
- **cilogon**: add ability to decode passed userinfo

### Refactor

- **cilogon**: refactor code for fetching userinfo

## 2.27.2 (2025-07-17)

### Fix

- **logging**: add debug logging throughout views

## 2.27.1 (2025-07-16)

### Fix

- **logging**: change level of citeproc warning to debug

## 2.27.0 (2025-07-16)

### Feat

- **logging**: try sentry logging feature

## 2.26.1 (2025-07-15)

### Fix

- **api**: add slug and name to groups api call to fix groups list

## 2.26.0 (2025-07-15)

### Feat

- **logging**: structured logging for all apps

## 2.25.2 (2025-07-04)

### Fix

- **cilogon**: check session after get parameter for new signup

## 2.25.1 (2025-07-03)

### Fix

- **cilogon**: make sub unique

## 2.25.0 (2025-07-01)

### Feat

- **webhook**: add webhook into association flow

## 2.24.1 (2025-06-30)

### Fix

- **cilogon**: handle unicodedecodeerror

## 2.24.0 (2025-06-30)

### Feat

- **debug**: add additional cilogon debug info

## 2.23.4 (2025-06-25)

### Fix

- **cilogon**: attempt to fix refresh token bug

## 2.23.3 (2025-06-25)

### Fix

- **cilogon**: attempt fix for refresh bug

## 2.23.2 (2025-06-25)

### Fix

- **cilogon**: set middleware to wipe session

## 2.23.1 (2025-06-25)

### Fix

- **cilogon**: handle arbitrary failures in refresh token middleware

## 2.23.0 (2025-06-25)

### Feat

- **webhook**: more work on webhook polling

### Fix

- **cilogon**: fix middleware access to non-existent member

## 2.22.4 (2025-06-17)

### Fix

- **rest-api**: fixes to email visibility and serialization

## 2.22.3 (2025-06-16)

### Fix

- **email**: fix email host string and inject request object into context

## 2.22.2 (2025-06-16)

### Fix

- **email**: fix cilogon association email

## 2.22.1 (2025-06-16)

### Fix

- **email**: fix sparkpost url mangling
- **email**: fix to sparkpost url mangling
- **association-service**: change image url src to s3 rather than local static url

## 2.22.0 (2025-06-13)

### Feat

- **association-service**: add new confirmation page and fix email logic

## 2.21.0 (2025-06-13)

### Feat

- **cilogon**: add secure aes-encrypted exchange of userinfo

## 2.20.1 (2025-06-13)

### Refactor

- **cilogon**: refactor code for fetching userinfo

## 2.20.0 (2025-06-11)

### Feat

- **cilogon**: fix JWTClaims checking

## 2.19.0 (2025-06-11)

### Feat

- **cilogon**: add ability to decode passed userinfo

## 2.18.7 (2025-06-10)

### Fix

- **cilogon**: change next parameter to callback_next

## 2.18.6 (2025-06-10)

### Fix

- **cilogon**: fix redirect logic

## 2.18.5 (2025-06-10)

### Fix

- **cilogon**: fix to redirect logic

## 2.18.4 (2025-06-10)

### Fix

- **oauth**: fix forwarding logging

## 2.18.3 (2025-06-10)

### Fix

- **logging**: change loglevel

## 2.18.2 (2025-06-09)

### Fix

- **cilogon**: change schema to https

## 2.18.1 (2025-06-09)

### Fix

- **cilogon**: fix missing requirement

## 2.18.0 (2025-06-09)

### Feat

- **cilogon**: further work on association service
- **association**: initial work on association service
- **cilogon**: re-sync external memberships on login
- **rest-api**: add mla member status to api
- **mla-api**: add mla api functionality
- **rest-api**: add swagger docs
- **rest-api**: add options support for logout
- **rest-api**: add logout endpoint
- **cilogon**: add tokens api endpoint and token revocation on logout
- **cilogon**: add validation of next_url to constrained whitelist
- **rest-api**: add subs endpoint
- **rest-api**: add group endpoint
- **REST-API**: new rest api application and authentication system
- **oauth**: add basic cilogon code as part of idms2

### Fix

- **cilogon**: move email module
- **rest-api**: fix rest api group detail view error
- **rest-api**: change hidden group to display 404 to non-authorized user
- **rest-api**: change all rest urls to be consistent. refactor
- **oauth**: further cilogon integrations
- **rest-api**: hide email to unathenticated api users
- **rest-api**: additional work on the rest api

### Refactor

- **rest-api**: improvements to rest api
- **mla-sync**: clean up and refactor mla sync class
- **cilogon**: add todos
- **cilogon**: major refactor and rework of middleware and logout logic
- **cilogon**: refactor views for readability
- **rest-api**: refactor to use native drf style
- **rest-api**: many tidy-ups to rest api

## 2.17.0 (2025-04-24)

### Feat

- **dashboard**: add table and csv download
- **dashboard**: change password system and exclude useless emails

## 2.16.2 (2025-04-24)

### Fix

- **dashboard**: fix syntax in build_stats

## 2.16.1 (2025-04-22)

### Fix

- **dashboard**: fix mobile table width on stats
- **styles**: remove gemfile lock

## 2.16.0 (2025-04-22)

### Feat

- **dashboard**: add table and csv download
- **dashboard**: change password system and exclude useless emails

## 2.15.2 (2025-04-20)

### Fix

- **dashboard**: fix resource hog query

## 2.15.1 (2025-04-20)

### Fix

- **dashboard**: remove command from dockerfile

## 2.15.0 (2025-04-20)

### Feat

- **dashboard**: accelerate dashboard loading by pre-generating results

## 2.14.1 (2025-04-20)

### Fix

- **models**: linting fix

## 2.14.0 (2025-04-20)

### Feat

- **dashboard**: add institutions to map
- **dashboard**: add maps to dashboard

### Fix

- **dashboard**: rewrite and optimize function to retrieve wordpress users and associated annotations

### Refactor

- **dashboard**: move local data generation to new function

## 2.13.1 (2025-04-19)

### Fix

- **dashboard**: rewrite and optimize function to retrieve wordpress users and associated annotations

## 2.13.0 (2025-04-19)

### Feat

- **dashboard**: add maps to dashboard

### Refactor

- **dashboard**: move local data generation to new function

## 2.12.1 (2025-04-19)

### Fix

- **ror**: fixes ROR import bugs
- **dashboard**: fix problematic static access paths

## 2.12.0 (2025-04-19)

### Feat

- **ror**: add ROR import
- **dashboard**: add initial work on dashboard

### Fix

- **ror**: remove limit

## 2.11.1 (2025-04-18)

### Fix

- **works**: fix works display and add various formatting tweaks to bullets and titles

## 2.11.0 (2025-04-17)

### Feat

- **works**: add links to citations
- **commands**: add csv export command for users
- **works**: rewrite of charts to optimize, use kc color scheme, and alphabetically order legend

### Fix

- **works**: move styles to root to speed deploy
- **base**: add version to css loader so that stylesheets are not cached between releases

### Perf

- **stats**: optimise csv generation

## 2.10.0 (2025-04-16)

### Feat

- **works**: rewrite of charts to optimize, use kc color scheme, and alphabetically order legend

## 2.9.0 (2025-04-15)

### Feat

- **works**: change chart to stacked

## 2.8.0 (2025-04-15)

### Feat

- **works**: add graph of works by year

## 2.7.0 (2025-04-15)

### Feat

- **works**: pluralize works title headings
- **health**: add additional information on redis, databases, etc. to healthcheck

### Fix

- **works**: remive redundant date field from citeproc parsing

## 2.6.0 (2025-04-15)

### Feat

- **versioning**: switch to commitizen versioning everywhere

## 2.5.3 (2025-04-14)

### Refactor

- **works**: rewrite of works module and tests to use pydantic for api parsing

## 2.5.2 (2025-04-12)

### Fix

- **works**: fix incorrect location

## 2.5.1 (2025-04-12)

### Fix

- **works**: use settings.STATICFILES_DIRS for static file locations

## 2.5.0 (2025-04-12)

### Feat

- **works**: add ability to change reference style

## 2.4.0 (2025-04-11)

### Feat

- **works**: add csl for citation formatting

## 2.3.0 (2025-04-10)

### Feat

- **works**: add ability to hide specific works

### Fix

- **works**: when editing works, tick all checkboxes by default
- **errors**: change error pages to use correct html layout

## 2.2.1 (2025-04-10)

### Fix

- **works**: fix nonetype handling bug in json parsing

## 2.2.0 (2025-04-09)

### Feat

- **works**: make kc works entries sortable by section and also allow sections to be hidden

## 2.1.0 (2025-04-08)

### Feat

- **settings**: remove compressor and rcssmin

### Fix

- **edit**: show form errors alongside fields
- **edit**: allow academic interests list to be empty

## 2.0.0 (2025-04-08)

### BREAKING CHANGE

- This commit moves the URL structure from /profiles/ to /. It therefore breaks anything relying on that structure.

### Feat

- **profiles**: make profiles reorderable
- **edit**: add styling for movable blocks
- **edit**: make profile items hideable and sortable
- **csrf**: add csrf reasons
- **urls**: move profiles to root of application
- **login**: add login button to homepage

### Fix

- **profiles**: move some htmx to main template
- **mastodon**: correct mastodon hide variable information
- **blog_posts**: fix incorrect dictionary access to profile object
- **mysql_data**: change mysql_data processing
- **csrf**: add trusted origins
- **csrf**: change csrf settings so test pass
- **csrf**: remove session configuration options which were causing csrf errors
- **js**: remove unneeded js
- **mysql_data**: correct link with new structure
- **base**: remove erroneous use of jquery in htmx return for mastodon_feed
- **edit_profile**: remove htmx boost from submit button to avoid 403 csrf errors
- **custom_login**: fix bug with error handling on API request
- **base-requirements**: limit smart_open requirement to aws

## 1.3.2 (2025-04-07)

### Fix

- **profiles**: move some htmx to main template

## 1.3.1 (2025-04-07)

### Fix

- **mastodon**: correct mastodon hide variable information
- **blog_posts**: fix incorrect dictionary access to profile object

## 1.3.0 (2025-04-07)

### Feat

- **profiles**: make profiles reorderable
- **edit**: add styling for movable blocks

## 1.2.0 (2025-04-03)

### Feat

- **edit**: make profile items hideable and sortable

## 1.1.4 (2025-04-03)

### Fix

- **mysql_data**: change mysql_data processing

## 1.1.3 (2025-04-02)

### Fix

- **csrf**: add trusted origins

## 1.1.2 (2025-04-02)

### Fix

- **csrf**: change csrf settings so test pass

## 1.1.1 (2025-04-02)

### Fix

- **csrf**: remove session configuration options which were causing csrf errors

## 1.1.0 (2025-04-02)

### Feat

- **csrf**: add csrf reasons

### Fix

- **js**: remove unneeded js

## 1.0.0 (2025-04-02)

### BREAKING CHANGE

- This commit moves the URL structure from /profiles/ to /. It therefore breaks anything relying on that structure.

### Feat

- **urls**: move profiles to root of application

### Fix

- **mysql_data**: correct link with new structure
- **base**: remove erroneous use of jquery in htmx return for mastodon_feed
- **edit_profile**: remove htmx boost from submit button to avoid 403 csrf errors

## 0.12.0 (2025-04-02)

### Feat

- **login**: add login button to homepage

## 0.11.2 (2025-04-02)

### Fix

- **custom_login**: fix bug with error handling on API request
- **base-requirements**: limit smart_open requirement to aws

## 0.11.1 (2025-04-02)

### Fix

- **middleware**: add error handling if wordpress database is not available
- **styles**: wrap long urls

## 0.11.0 (2025-04-01)

### Feat

- **auth**: add logout support

### Fix

- **settings**: change tinymce base url to point to final static files location

## 0.10.0 (2025-04-01)

### Feat

- **edit**: basic edit profile functionality

### Fix

- **urls**: remove sso urls

## 0.9.0 (2025-03-31)

### Feat

- **sidebar**: seperate sidebar into different nav section and add links

## 0.8.1 (2025-03-28)

### Fix

- **middleware**: wordpress login/logout fixes
- **profile**: handle logged_in_user_is_profile identity between user and profile

## 0.8.0 (2025-03-28)

### Feat

- **profile**: add favicon
- **middleware**: wordpress login/logout improvements

## 0.7.0 (2025-03-28)

### Feat

- **errors**: add better formatted 404, 403, and 500 error handling
- **profile**: delete old theme, rework tests, add new htmx endpoints
- **profile**: change font to atkinson hyperlegible throughout for accessibility (#62)

### Fix

- **sql_import**: fix for latest sqloxide layout

## 0.6.3 (2025-03-27)

### Fix

- **import_cover_images**: fixes to cover image import to allow for pathlib.path support

## 0.6.2 (2025-03-27)

### Fix

- **import_profile_images**: fixes for pathlib.Path version of script

## 0.6.1 (2025-03-27)

### Fix

- **import_profile_images**: fix bad path construction

## 0.6.0 (2025-03-25)

### Feat

- **import**: add smart_open to handle s3 files as well as local

## 0.5.0 (2025-03-24)

### Feat

- **import**: add cmdline argument

## 0.4.0 (2025-03-21)

### Feat

- **healthcheck**: add heartbeat

## 0.3.1 (2025-03-20)

### Fix

- **production**: fixes to various components detected during production build

## 0.3.0 (2025-03-19)

### Feat

- **api.py**: add fast-fail situation for when MySQL database is not available
- **theme**: use new theme by default
- **new-theme**: add new theme (#40)

### Fix

- **asgi**: Remove asgi and wsgi files (#41)

## 0.2.0 (2025-03-10)

### Feat

- first commit

### Fix

- **README**: update coverage badge
- **tests**: add lcov generation in test CI
- **__init__**: no encoding needed for binary open
- **tests**: change imports
- **Debug**: remove custom debug panel and reinstate defaults as we are now running async
- **README**: inline coverage
- **README**: more coverage
- **HTML**: linting fixes
- **github**: adjust action
- **HTML**: adjust for linting
- **README**: Add test coverage
- **HTML**: cleanup mysql_data.html for linting
- **HTML**: more inline styles of base.html for linting
- **HTML**: adjust inline styles of base.html for linting
- **HTML**: adjust formatting of base.html for linting
- **HTML**: adjust formatting of base.html for linting
- **HTML**: adjust formatting of profile_info.html for linting
- **HTML**: adjust formatting of profile.html for linting
- **CI**: tell dependabot to ignore rcssmin versions
- **requirements**: reduce rcssmin for compat with django-compressor
- **CI**: rename test phase
- **tests**: test fixes and updates to CI
- **CI**: change import for new structure
- **CI**: Remove redundant field creation and deletion in migrations
- **CI**: alter migrations
- **CI**: alter migrations
- **CI**: Further CI fixes
- **CI**: More CI fixes
- **CI**: Change app name and Docker config
- **CI**: Change app name in LOCAL_APPS to fix import error
- **CI**: Add DJANGO_SETTINGS_MODULE to github env
- add transaction.atomic to main method for speedup
- change scope of already_printed to remove duplicate unhandled errors
- Remove duplicate README sections
