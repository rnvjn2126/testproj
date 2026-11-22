# Decisions, Assumptions, and Morning Questions

## Default decisions for autonomous MVP
- Build for India, INR, metric units; start with stainless round bars and sheets, but design catalogue for additional shapes.
- Start with order-based trading, not inventory accounting.
- Use Django 5.2 LTS, SQLite development database, server-rendered responsive pages, local synthetic data.
- Default target gross margin 12%; **demonstration assumption only**, configurable per business. Quotes below threshold require explicit manager review.
- Show entered weights and calculated weights separately; never infer missing grade/density without a visible assumption.
- Never send customer communication automatically. All WhatsApp links require a user click.
- One business/account boundary at first, but design ownership checks for future multi-business use.
- Keep purchase rates, margins and internal remarks off customer-facing documents.

## Record each new decision
| Date | Task | Decision | Rationale | Reversible? |
|---|---|---|---|---|
| 2026-11-22 | Initial setup | Choose safe defaults listed above | Permit unattended work without pretending business rules are confirmed | Yes |
| 2026-11-22 | Django foundation | Use Django's built-in session authentication; provision local accounts with `createsuperuser` or Django admin; no public sign-up | Keeps the local demo access-controlled without introducing account approval or recovery workflows | Yes |
| 2026-11-22 | Catalogue milestone | Customers, suppliers and products are owned by the signed-in local user; products capture optional metric dimensions and distinguish actual from theoretical item weight without calculating or inferring weight | Establishes a clear ownership boundary and avoids unverified steel-density assumptions | Yes |

## Questions for the next morning review
1. Should the first demo focus on stainless steel only or include MS/alloy products?
2. Are supplier offers for stock on hand or procurement after an order?
3. What actual gross-margin floor and manager-approval hierarchy should be used?
4. Which quotation terms and GST treatments apply to your business?
5. Should each sales representative see their own accounts or all company leads?

Questions do not block unrelated safe implementation. Never fabricate an answer; mark the relevant workflow as a configurable pilot assumption.

## Blockers
None at setup. Record any task failure with failing command, log, and recommended next action.
