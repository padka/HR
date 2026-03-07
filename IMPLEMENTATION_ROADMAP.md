# IMPLEMENTATION_ROADMAP

## Week 1
- Publish canonical redesign docs in root.
- Fix mobile shell layering/dialog issue in `__root`.
- Make ambient background opt-in for quiet operational routes.
- Introduce shared page/surface primitives in theme layer.
- Apply new page shell to recruiter-first screens.

## Weeks 2-3
- Hardening pass on recruiter-first screens:
  - `dashboard`
  - `incoming`
  - `slots`
  - `candidates`
  - `candidate detail`
  - `messenger`
- Add automated shell, responsive and a11y regressions.
- Remove page-local styling from the worst hotspots in core screens.

## Weeks 3-4
- Admin-heavy redesign wave:
  - `cities`, `city-edit`
  - `recruiters*`
  - `templates*`, `message-templates`, `questions*`
  - `system`
  - `test-builder*`
  - `detailization`, `calendar`, `copilot`
- Start inline-style debt burn-down.

## Final Hardening
- Visual polish and motion cleanup.
- Responsive matrix pass.
- QA checklist run.
- Final artifact refresh with delivered state and remaining backlog.
