# Superpowers skills

Vendored from [obra/superpowers](https://github.com/obra/superpowers)
(commit `5bf4e78011075bcfc0dc295f0724994cd123ee71`, 2026-09-18), MIT licensed
(see `SUPERPOWERS-LICENSE.md`).

These are project-level Claude Code skills — Claude auto-discovers any
`.claude/skills/<name>/SKILL.md` in this repo and can invoke them by name
(e.g. `/systematic-debugging`, `/test-driven-development`) or automatically
when relevant.

## Included skills

- `brainstorming` — structured idea exploration before committing to a plan
- `diagnosing-superpowers` — troubleshooting the skills setup itself
- `dispatching-parallel-agents` — fanning work out to parallel subagents
- `executing-plans` — carrying out a written implementation plan
- `finishing-a-development-branch` — wrapping up a branch (cleanup, PR prep)
- `receiving-code-review` — acting on code review feedback
- `requesting-code-review` — asking for a code review
- `subagent-driven-development` — delegating implementation to subagents
- `systematic-debugging` — root-cause debugging methodology
- `test-driven-development` — TDD workflow
- `using-git-worktrees` — working across git worktrees
- `using-superpowers` — meta-skill on how/when to reach for these skills
- `verification-before-completion` — checklist before declaring work done
- `writing-plans` — drafting implementation plans
- `writing-skills` — authoring new Claude Code skills

## Updating

Re-sync by re-cloning `https://github.com/obra/superpowers` and copying its
`skills/` directory over this one. The upstream project also ships hooks
(`hooks/session-start`) that force a skill check at the start of every
conversation — not installed here since that changes project-wide hook
behavior; wire it up via `.claude/settings.json` if you want that stronger
enforcement.
