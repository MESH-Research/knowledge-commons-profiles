---
description: Generate new technical documentation for specified topics
---

Generate a new technical documentation file for the knowledge-commons-profiles application based on the specified topic. The documentation should follow the same writing conventions and formatting standards as existing documentation.

## Instructions

1. **Determine the topic and scope** from the user's request
2. **Research the codebase** to gather relevant technical information about the specified topic
3. **Choose appropriate location** in the `/docs` folder structure:
   - Authentication/OAuth topics: `/docs/cilogon/`
   - Profile management topics: `/docs/newprofile/`
   - Infrastructure/operations topics: `/docs/`
   - New categories: Create appropriate subfolder in `/docs/`

4. **Generate documentation** following these requirements:

### Writing Standards
- Use technical, factual language - avoid marketing terms like "comprehensive", "seamless", "robust"
- Focus on architectural concepts, data flows, and integration patterns
- Include troubleshooting information and common issues where relevant
- Provide specific examples and code snippets where helpful
- Do NOT include specific code line numbers (they become outdated quickly)

### Document Structure
- Start with version note: `> **Note**: This documentation refers to knowledge-commons-profiles version X.X.X`
- Use clear section hierarchy with descriptive headings
- Include overview section explaining the topic's purpose and scope
- Organize content logically: overview → architecture → implementation → configuration → troubleshooting
- Add cross-references to related documentation where appropriate

### Technical Content Requirements
- Document key components, models, views, and integration points
- Explain configuration options and environment variables
- Include security considerations where relevant
- Provide development and testing guidance
- Add deployment and operational considerations
- Include monitoring and observability aspects if applicable

5. **Update the main README.md** in `/docs/` to include the new documentation file with:
   - Appropriate section placement
   - Descriptive summary of what the documentation covers
   - Relative link to the new file

6. **Verify consistency** with existing documentation style and structure

7. **Run update-docs workflow** to ensure all documentation is current and the index is properly maintained:
   - Execute the `/update-docs` workflow to refresh the documentation index
   - Verify all documentation files have consistent version numbers
   - Ensure the main README.md includes all documentation files from `/docs/` and subfolders

## Example Usage
```
/generate-new-doc write documentation about Docker configuration and deployment setup
/generate-new-doc create a guide for database configuration and migrations
/generate-new-doc document the REST API endpoints and authentication
```

## File Naming Convention
- Use descriptive, lowercase names with underscores
- Include topic area in filename: `{topic}_technical_guide.md`
- Examples: `docker_deployment_guide.md`, `database_configuration_guide.md`, `rest_api_technical_guide.md`

## Quality Checklist
- [ ] Version note included at top
- [ ] Technical language without marketing terms
- [ ] Clear section structure and navigation
- [ ] Code examples without line numbers
- [ ] Security and operational considerations included
- [ ] Cross-references to related docs
- [ ] Main README.md updated with new file
- [ ] Consistent formatting with existing documentation
