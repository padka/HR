---
name: visual-qa-authenticated
description: Use for authenticated RecruitSmart operator UI checks through browser automation, snapshots, and screenshots. Covers signed-in admin/recruiter flows and requires explicit limitation wording when full Computer Use is unavailable.
---

# Visual QA Authenticated

Use this skill for:

- signed-in admin UI walkthroughs
- candidate detail and operator modal checks
- list/filter/badge verification
- screenshot-backed proof for bounded UI changes

Do not use for:

- provider-owned external UI verification
- unauthenticated website checks
- claiming desktop-level Computer Use when only browser automation is available

## Workflow

1. Prefer the project Playwright setup or browser MCP over ad hoc manual browsing.
2. Authenticate using the existing test/admin harness when available.
3. Verify the concrete operator flow:
   - entry screen renders
   - action buttons are understandable
   - disabled/error/success states are readable
   - no raw provider tokens, URLs, or IDs leak into UI
4. Capture screenshots or snapshots as evidence when useful.
5. If full Computer Use is unavailable, state that visual QA was completed through browser automation and screenshots only.

## Required Output

- checked screens/components
- evidence path or screenshot summary
- observed copy/status issues
- explicit limitation wording if provider-side UI or desktop interactions were not proven
