# Third-party notices

## Claude Code skills from Jeffallan/claude-skills

Eight skills under `.claude/skills/` are copied unmodified from
https://github.com/Jeffallan/claude-skills (package "fullstack-dev-skills"),
commit `078a25cc5bfd8011459be7b91d004e900c1d02d3`, which is distributed under the MIT License below.

| Skill | Folder | When we use it |
|-------|--------|----------------|
| the-fool | `.claude/skills/the-fool/` | Now: pre-mortems and devil's-advocate checks on big decisions |
| security-reviewer | `.claude/skills/security-reviewer/` | Now: read-only security reviews (auth, PHI handling, dependencies) |
| playwright-expert | `.claude/skills/playwright-expert/` | Later: browser end-to-end tests, once UI pages exist |
| devops-engineer | `.claude/skills/devops-engineer/` | Later: demo deployment phase |
| cloud-architect | `.claude/skills/cloud-architect/` | Later: demo deployment phase |
| terraform-engineer | `.claude/skills/terraform-engineer/` | Later: demo deployment phase |
| sql-pro | `.claude/skills/sql-pro/` | SQL review; schema work as needed |
| postgres-pro | `.claude/skills/postgres-pro/` | Later: if we move from SQLite to Postgres |

The rules for using them are in `CLAUDE.md` section 19 and ADR-0026. To update
them, re-copy from a newer upstream commit in a pull request and review the diff.

### Upstream license (MIT)

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
