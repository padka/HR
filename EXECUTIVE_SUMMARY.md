# EXECUTIVE_SUMMARY

## Overall Assessment
- Current interface quality: `visually promising but operationally flawed`
- Mobile readiness: `partially usable`
- Redesign recommendation: proceed, but start with shell and design-system foundations before touching individual page cosmetics.

## What Is Working Today
- There is already a credible premium visual base.
- Token system, safe-area handling and reduced-motion support are materially better than in a typical internal CRM.
- Key recruiter workflows already exist as real screens and can be improved incrementally.
- Router and code splitting are stable enough to support phased redesign.

## What Is Not Working Systemically
- Shell, theme and page contracts are not strict enough to govern the whole product.
- Mobile shell semantics are not production-grade yet.
- High-density recruiter and admin screens still solve layout locally.
- Long-form admin pages and utility editors are hard to scale and audit.

## Top 15 Critical Problems
### P0
1. Closed mobile "More" sheet remains rendered as dialog-like structure in root shell. Ref: `frontend/app/src/app/routes/__root.tsx:1250-1258`.
2. Decorative ambient background is too global for operational routes. Ref: `frontend/app/src/app/routes/__root.tsx:763-858`.
3. No mandatory page contract exists across routes. Evidence: `dashboard.tsx`, `incoming.tsx`, `profile.tsx`, `system.tsx`.
4. CSS and shell monoliths slow safe redesign. Ref: `frontend/app/src/theme/global.css:1-8717`, `frontend/app/src/app/routes/__root.tsx:1-1286`.
5. Admin-heavy pages rely on inline-style layout decisions. Ref: `city-edit.tsx`, `system.tsx`, `test-builder-graph.tsx`.

### P1
6. Candidate detail is too dense for fast operational scanning. Ref: `frontend/app/src/app/routes/app/candidate-detail.tsx:1855-2665`.
7. Filters and toolbars are inconsistent across core screens. Ref: `incoming.tsx:420-466`, `candidates.tsx:437-468`, `dashboard.tsx:672-745`.
8. Table-to-card responsive strategy is duplicated manually in multiple routes.
9. Mobile kanban and calendar are usable but not well optimized for daily work.
10. System and detailization pages are visually and cognitively heavy.

### P2
11. Landmark and scroll-region accessibility issues remain.
12. Z-index ladder is fragile and likely to drift.
13. Empty/loading/error/success blocks are not standardized enough.
14. Motion hierarchy is under-specified and still lets decorative movement compete with work.
15. Dormant routes create backlog noise outside mounted scope.

## Top 15 Highest-Value Improvements
1. Fix mobile shell dialog semantics. UX impact: very high. Visual impact: medium. Engineering complexity: low.
2. Make ambient background opt-in. UX impact: high. Visual impact: high. Engineering complexity: low-medium.
3. Enforce shared page hero and section contract. UX impact: high. Visual impact: high. Engineering complexity: medium.
4. Enforce shared surface ladder. UX impact: high. Visual impact: high. Engineering complexity: medium.
5. Normalize toolbar and filter patterns. UX impact: high. Visual impact: medium. Engineering complexity: medium.
6. Reduce blur/glow noise on operational screens. UX impact: medium-high. Visual impact: high. Engineering complexity: low.
7. Re-architect candidate detail hierarchy. UX impact: high. Visual impact: high. Engineering complexity: medium-high.
8. Strengthen mobile drill-down behavior. UX impact: high. Visual impact: medium. Engineering complexity: medium.
9. Standardize mobile card parity with table behavior. UX impact: high. Visual impact: medium. Engineering complexity: medium-high.
10. Quiet long-form admin screens. UX impact: medium-high. Visual impact: medium-high. Engineering complexity: medium.
11. Burn down inline-style debt in top-risk screens. UX impact: medium. Visual impact: medium. Engineering complexity: high.
12. Improve calendar mobile model. UX impact: medium-high. Visual impact: medium. Engineering complexity: medium.
13. Improve shell and overlay accessibility. UX impact: medium-high. Visual impact: low. Engineering complexity: low-medium.
14. Standardize state blocks and skeletons. UX impact: medium. Visual impact: medium. Engineering complexity: medium.
15. Add route-level responsive and a11y smoke coverage. UX impact: indirect high. Visual impact: none. Engineering complexity: low-medium.

## Recommended First Implementation Wave
- Foundation first:
  - `frontend/app/src/app/routes/__root.tsx`
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/mobile.css`
  - `frontend/app/src/theme/material.css`
- Recruiter-first screens next:
  - `/app/dashboard`
  - `/app/incoming`
  - `/app/slots`
  - `/app/candidates`
  - `/app/candidates/$candidateId`
  - `/app/messenger`
- Admin-heavy second wave:
  - `/app/cities/$cityId/edit`
  - `/app/system`
  - `/app/test-builder`
  - `/app/test-builder/graph`
  - `/app/templates*`
  - `/app/questions*`

## Recommended Rollout Strategy
### First Week
- Freeze docs package.
- Fix shell/mobile semantics.
- Introduce shared page and surface primitives.

### First 2 Weeks
- Apply foundation contract to recruiter-first screens.
- Run mobile-first pass on those routes.
- Add shell and route smoke validation.

### First Month
- Move admin and long-form screens onto the same system.
- Reduce inline-style debt on highest-risk pages.
- Run responsive, a11y and motion hardening.

## Main Risks
- Design debt lives in large route files and monolithic CSS, so ad hoc fixes will regress quickly.
- Candidate detail and test-builder graph are too dense for a cosmetic pass; they need structural work.
- Mobile quality will remain inconsistent if implementation starts from screen cosmetics instead of shell and shared primitives.

## Expected Value Of Redesign
- Faster operational scanning and action-taking.
- Fewer layout bugs and layering regressions.
- Stronger mobile support for daily recruiter work.
- Lower maintenance cost through shared primitives and reduced inline styling.
- A more mature premium interface without sacrificing CRM usability.
