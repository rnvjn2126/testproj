# Agent instructions: Steel Quotation MVP

Read `docs/PRODUCT_BRIEF.md` before coding. Develop a working Django steel-trader quotation application with tests, incrementally and in the order defined by the current task.

- Local-only development; work on `ai/steel-mvp-overnight`. Do not merge, deploy, push, or change branches yourself.
- User delegates ordinary reversible implementation decisions. Default to simple Django templates, India/INR, metric quantities and synthetic data; record non-obvious decisions in `docs/ASSUMPTIONS_AND_QUESTIONS.md`.
- Put genuine business uncertainties in that same document and your structured final answer. Continue with safe independent work without blocking for routine clarifications.
- Never store or access production credentials, real customer contact lists, payment information, or confidential supplier rates.
- Never send WhatsApp messages, emails or notifications to real contacts. Click-to-chat links should be explicitly staff-triggered.
- Use Python Decimal for monetary calculations, validate every quantity and unit, and distinguish margin from markup.
- Protect account ownership boundaries on all objects, exports, and PDFs.
- Keep migration files consistent. Include automated tests for every new feature and permission boundary.
- Do not disable automated tests or modify CI, repository security settings, or production infrastructure.
- The external overnight controller runs `manage.py check`, `makemigrations --check --dry-run`, and `manage.py test --noinput` and records tested Git checkpoints.
- If unclear, take the least risky reversible approach and state it. Never fabricate test results.
