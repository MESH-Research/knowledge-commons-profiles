---
trigger: always_on
description:
globs:
---

// Windsurf rule implementation
async function autoFormat(context) {
  const { filePath, fileExtension } = context;

  // Skip if file is in excluded directories
  const excludedPaths = ['/docs/', '/migrations/', 'devcontainer.json'];
  if (excludedPaths.some(path => filePath.includes(path))) {
    return;
  }

  try {
    if (fileExtension === '.py') {
      // Format Python files with Ruff
      await context.runCommand(`ruff format --line-length 79 "${filePath}"`);
      await context.runCommand(`ruff check --fix --line-length 79 "${filePath}"`);
      await context.runCommand(`ruff check --select I --fix "${filePath}"`);
    }

    // Run pre-commit hooks for all files
    await context.runCommand(`pre-commit run --files "${filePath}"`);

    context.log(`Formatted: ${filePath}`);
  } catch (error) {
    context.log(`Formatting failed for ${filePath}: ${error.message}`);
  }
}
