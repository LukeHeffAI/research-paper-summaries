# `api/` — reserved (Phase 3)

Empty this phase. The future **FastAPI** layer lands here and will call
`downlow.core.services` **unchanged** (the whole point of the ports/adapters split).
`core/` must never import from `api/`. See `PROJECT_PLAN.md` → Phase 3.
