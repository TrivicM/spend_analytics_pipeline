---
name: git-commit-generator
description: Generates conventional commit messages with a detailed body and semantic versioning reasoning for git diffs or current session changes. Scopes for this project: pipeline, dashboard, notifier, server, sql, agents, docs.
---

# Git Commit Generator Skill

This skill assists the agent in writing high-quality, descriptive Conventional Commit messages for modified files or the current git diff.

## Activation / Triggering
This skill is triggered when the user requests a commit message, a conventional commit message, or asks to commit/stage changes with proper semantic reasoning.

## Commit Message Standards

All generated commit messages must follow the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) specification:

```
<type>(<scope>): <description>

<body>

<footer>
```

### 1. Types
- **feat**: A new feature (corresponds to `MINOR` in semantic versioning)
- **fix**: A bug fix (corresponds to `PATCH` in semantic versioning)
- **docs**: Documentation-only changes
- **style**: Changes that do not affect the meaning of the code
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **chore**: Other changes that don't modify src or test files

### 2. Scopes (project-specific)
- `pipeline` — generate_data.py, schema.sql, views.sql
- `notifier` — ai_notifier.py
- `server` — dashboard_server.py
- `dashboard` — dashboard/index.html
- `sql` — sql/ directory
- `agents` — .agents/ directory (AGENTS.md, memory, skills)
- `docs` — README.md, any documentation

### 3. Subject (Description)
- Use the imperative, present tense: "add" not "added"
- Do not capitalize the first letter
- Do not end with a period

### 4. Body
- Explain the **why** behind the changes, not just the **what**
- Wrap lines at 72 characters

### 5. Semantic Versioning Impact
Include a brief explanation:
- **Major (Breaking Change)**: Incompatible API changes (`BREAKING CHANGE:` in footer)
- **Minor (Feature)**: Adding functionality in a backwards-compatible manner
- **Patch (Fix)**: Backwards-compatible bug fixes
- **None**: Documentation, formatting, chores, or refactoring

## Instructions for the Agent

When this skill is activated:
1. Run `git diff --cached` to identify staged changes.
2. If nothing is staged, alert the user and suggest files to stage.
3. Group staged changes by component (pipeline, dashboard, notifier, etc.).
4. Determine the primary commit type and scope.
5. Construct a draft commit message in Conventional Commits format.
6. Provide a "Semantic Reasoning" section explaining the type/scope choice and versioning impact.
