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
