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
