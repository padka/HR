---
name: dependency-upgrade-check
description: Validate RecruitSmart dependency additions or upgrades against official docs, changelogs, deprecations, security advisories, and compatibility impact before changing lockfiles or versions.
---

# Dependency Upgrade Check

Use this skill when:

- adding a new dependency
- upgrading Python, Node, framework, or infra libraries
- changing lockfiles or package manager behavior
- validating a version-sensitive API or CLI

Do not use for:

- in-repo code changes without dependency movement
- docs-only updates
- refactors that do not touch package versions

## Checklist

- Official docs were checked.
- Changelog or release notes were checked.
- Breaking changes or deprecations were identified.
- Security advisories were checked when relevant.
- The dependency is actually justified.
- Compatibility with current code and tooling was assessed.
- The change can be rolled back cleanly.

## Output

Return:

- current version vs target version
- why the change is needed
- compatibility risks
- required code changes
- recommendation to adopt or defer
