# Steel Trading Quotation MVP

Status: Product brief v0.1, approved for autonomous local development, subject to later user review.

## Audience and problem
A small or midsize Indian steel trader receives enquiries by phone, WhatsApp and email, asks one or more suppliers for prices, and then creates a customer quotation. Rates and freight vary; line items use inconsistent units; employees can accidentally quote below an acceptable margin; many quotations do not receive a timely follow-up.

## Product promise
**Compare supplier offers, protect gross margins, prepare a professional quotation, and follow up on every enquiry—in one simple system.**

## MVP modules (build in this order)
1. Django 5.2 LTS scaffold with login, local SQLite, automated tests and clean Windows startup.
2. Catalogue of customers, suppliers and steel products (grade, shape, dimensions, unit, weight conventions).
3. RFQ intake and line items with server-side validation.
4. Supplier offers with price, quantity, freight, delivery days, and normalized landed cost.
5. Quote pricing with configurable target gross margin, discount guardrails, approval and transparent calculations.
6. Branded HTML/PDF quotation with revisions, expiry and payment/delivery terms.
7. Quote pipeline, follow-up dates and manual WhatsApp click-to-chat.
8. Safe CSV import/export, access-control hardening and mobile usability.

## Commercial rules and definitions
- Currency: INR by default. Use decimal arithmetic, not binary float, for money.
- **Gross margin %** = (selling price - landed cost) / selling price × 100, not markup on cost.
- For a desired gross margin m (as decimal), selling price = landed cost / (1-m), for m < 1.
- Supplier comparison must display assumptions, unit conversions, available quantities, freight allocation and lead times.
- Freight, packaging and other incidental landed costs are explicit editable components.
- GST is a separately configured line on the **sales quote**; do not automatically treat reclaimable GST as procurement cost. Do not claim legal/GST certification.
- Never auto-approve negative margins; surface manager-review requirement.
- Internal supplier buy rates and margins are never shown on customer-facing PDFs.
- Data must be scoped to the correct account or business; prevent cross-customer/tenant access.
- Test values and data are synthetic. No real credentials, customer phone numbers or production DBs.

## Preferred technology
- Server: Python / Django 5.2 LTS (compatible with the user's Windows Python 3.13).
- Development DB: SQLite, local only. Plan PostgreSQL for eventual hosted production after validation.
- UI: Django templates, server-side forms, straightforward mobile CSS, no heavy SPA initially.
- PDF: reportlab, but only after the domain models and calculations work.
- Tests: Django test runner, mandatory per completed milestone.
- External services: none for version one. WhatsApp sharing must be staff-initiated and opt-in.

## What autonomous development may decide
Field names, URLs, internal design, CSS, simple reports, demo data, test structure, migration order and other reversible implementation details. Record non-obvious choices in docs/ASSUMPTIONS_AND_QUESTIONS.md.

## What it must NOT decide / do
Production deployments, spending money, sending real customer messages, public marketing claims, merging to main, exposing confidential data, using real contact lists, creating remote infrastructure, storing tokens, skipping permissions and tests.

## Questions to revisit with the owner
- Which steel categories are first: stainless, mild steel, alloy bars, sheets, pipes, or all?
- Is the business predominantly a stockist/trader or an order-based procurement broker?
- Do quotes require company-specific terms, minimum margin floors or approval tiers?
- Do customers usually buy in kg, tonnes, pieces, metres, or multiple units?
- Do multiple salespeople need account separation in the pilot?

These questions should **not prevent** building the MVP with documented default assumptions. Ask them in the next morning report.

## Acceptance criteria for first demonstration
A signed-in demo user can create a fictitious enquiry, add multiple supplier offers, see a correct landed-cost comparison, select a supplier, calculate an acceptable selling quote, export a customer-facing PDF, and create a follow-up task. Django checks and automated tests pass.

## Workflow
Local Codex runs on the separate branch `ai/steel-mvp-overnight`. The user's local runner tests and commits checkpoints, then pushes this branch for morning review. No automatic merge to `main`.
