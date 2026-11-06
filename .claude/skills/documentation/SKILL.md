---
name: documentation
description: What to document and where in this template - README, AGENTS.md, skills, architecture decision records (docs/adr), module docstrings and comments, .env.example, API docs, changelog. Load when adding a feature, changing setup/config/conventions, making an architectural decision, or writing docstrings and comments.
---

# Documentation

Document the things a new developer (or agent) can't learn quickly from the code: how to run it, why it is built this way, and the rules to follow. Don't restate what clear code already says.

## 1. Where each kind of documentation lives

| Audience / question | Location |
|---|---|
| "How do I run, configure and deploy this?" | `README.md` |
| "What rules must I follow when changing code?" (humans and AI agents) | `AGENTS.md` (short, always loaded) + `.claude/skills/*/SKILL.md` (detailed, loaded per task) |
| "Why is it built this way?" | `docs/adr/NNNN-title.md` (architecture decision records) |
| "How does this complex flow work end to end?" | `docs/<topic>.md`, with a diagram if helpful (e.g. sign-in with 2FA) |
| "What does this module/function do and what must callers know?" | docstrings in the code |
| "Which settings exist?" | `.env.example` (every setting, commented) + `app/core/config.py` |
| "What does the API look like?" | OpenAPI at `/api/docs` in development (generated from routes and schemas) |
| "What changed in this release?" | `CHANGELOG.md` (once the project has releases) |

## 2. README.md

Keep it current with every change to setup, configuration or deployment: what the app is, quick start, commands, configuration highlights, security summary, deployment steps, and links to `AGENTS.md`, the skills and `docs/`. Every command in it must work as written.

## 3. AGENTS.md and skills

- `AGENTS.md` is the entry point for coding agents: the layout summary, run/verify commands, the list of skills and when to load each, and the few non-negotiable rules. Keep it short; details go in skills.
- A skill covers one topic, has front matter (`name`, and a `description` that says **when to load it**), and has a checklist at the end. Describe how *this* codebase works, not generic advice, and mark anything not implemented yet as a gap.
- When code changes a convention described in a skill, update the skill in the same PR.

## 4. Architecture decision records (`docs/adr/`)

Write an ADR when you choose between real alternatives that others will live with: a new dependency or service, a structural pattern, a security trade-off, or deviating from a skill's rule.

- File name: `NNNN-short-title.md` (next number), copied from `docs/adr/0000-template.md`.
- Sections: **Status** (proposed / accepted / superseded by NNNN) · **Context** · **Decision** · **Consequences** (good and bad) · **Alternatives considered**.
- ADRs are immutable once accepted. To change one, write a new ADR that supersedes it and update the old one's status line.

## 5. Code-level documentation

- **Module docstring** on every non-trivial module: what it's for and any rule callers must follow (see `app/features/mfa/service.py`, `app/integrations/mail.py`).
- **Docstrings** on public functions and classes whose behaviour isn't obvious from the name and types: side effects, invariants, error cases and units. Skip them for obvious one-liners.
- **Comments explain why** (a constraint, a trade-off, a security reason), not what the next line does. Delete comments that have gone stale.
- Pydantic models and fields: document only non-obvious semantics (`# in priority order: the first decides the landing page`).
- TypeScript: JSDoc (`/** … */`) on exported components, hooks and types whose usage isn't obvious.
- No commented-out code. No TODOs without an owner or issue reference (`# TODO(#123): …`).

## 6. Configuration

Every new setting goes into `app/core/config.py` (with a type and default), `.env.example` (with a comment saying what it does, its allowed values and the production expectation) and, if it can be unsafe, `enforce_production_safety`. Mention important ones in the README's production section.

## 7. API documentation

- The OpenAPI schema is generated, so its quality depends on the code: clear handler names, a `summary=` on non-obvious routes, `response_model` everywhere, and `Field(description=…)` for non-obvious fields.
- Docs are disabled in production (`ENABLE_API_DOCS`). Don't expose them to make documentation easier.

## 8. Changelog

Once the project ships releases, keep `CHANGELOG.md` in the "Keep a Changelog" style: `## [version] - date` with Added / Changed / Fixed / Security / Removed. Each PR that changes user-visible behaviour adds a line under `## [Unreleased]`. Call out breaking changes and required migration or config steps.

## 9. Checklist

- [ ] Setup, config or deploy changes are reflected in `README.md` and `.env.example`.
- [ ] Changed conventions are updated in `AGENTS.md` / the relevant skill.
- [ ] Significant decisions have an ADR.
- [ ] New modules have a docstring; non-obvious functions explain side effects and errors.
- [ ] Comments explain why; no stale comments, commented-out code or ownerless TODOs.
- [ ] User-visible changes are in the changelog (once releases exist).
