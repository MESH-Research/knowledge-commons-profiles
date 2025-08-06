---
description: Update the docs files to reflect latest content
---

Update the files in docs/cilogon, /docs/newprofile, and any .md files in /docs. These should be changed to retain their basic structure, but to update their content against the repository as a whole. Do not get rid of sections that explore background contexts, such as the bit on Sentry in the logging and observability guide. If the version hasn't changed, then don't update any files.

Do not put code line numbers into these files at any point. Also, do not use terms like "comprehensive" or "seamlessly" -- these are technical documents, not sales pitches.

Every document should have a note of the version to which the docmentation applies, that looks like this:

> **Note**: This documentation refers to knowledge-commons-profiles version 2.30.0

The version number should be fetched from [project] version in pyproject.toml. You can use this to determine whether the version has changed and, therefore, whether you should change any files or not.

Finally, always create a file README.md in the root of /docs that serves as an index to the documentation. This should have relative links to all the files that will be browsable when uploaded to GitHub, explaining what the files document.
