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
| 2026-11-22 | Supplier landed-cost comparison | Record offers against one enquiry line with an entered unit rate, available quantity, delivery days, freight total and packaging/incidental total. Normalize kg and tonnes directly; allow piece conversion only from the linked catalogue product's recorded actual or theoretical kg per piece, saved with the offer as its conversion basis. Allocate freight and packaging across the smaller of requested and available quantities after conversion, and label partial coverage. | Makes comparisons transparent without inferring missing weights or assuming an offer covers the full order | Yes |
| 2026-11-22 | Supplier landed-cost comparison | Treat supplier rates and entered freight/packaging as entered amounts, with no supplier GST calculation in this milestone | GST inclusion and any non-creditable procurement tax treatment need business confirmation | Yes |
| 2026-11-22 | RFQ intake | Capture enquiry channel, received/required dates, customer, notes and one or more requested items; permit a catalogue product or free-text specification, with quantity required in an explicit catalogue metric unit | Supports varied incoming enquiry detail without inferring steel weights or adding supplier/quote workflows | Yes |
| 2026-11-22 | Margin-protected quotations | Use account-editable defaults of 12% target margin, 8% minimum margin, and 5% maximum discount for the local demo. Calculate selling price from landed cost using gross margin (not markup), apply any discount to that target price, require one full-quantity offer per enquiry line, and snapshot the inputs and calculated rates on each quote. Round unit prices to four decimals and displayed INR totals to paise using half-up rounding. A below-floor or negative-margin quote remains pending until a signed-in staff account explicitly approves it. The approval action stays within the existing per-user account boundary; shared multi-user manager review needs the business account model and role hierarchy confirmed first. | Makes the arithmetic auditable and prevents a quote from silently bypassing the configured discount cap or review floor; these thresholds and the manager role are unconfirmed pilot assumptions | Yes |
| 2026-11-22 | Customer quotation documents | Assign a local quote number from the creation year and record ID; revisions retain that number and increment their revision. New quotes default to a seven-day validity period. Apply the entered GST/tax percentage to the sales subtotal only; do not certify tax treatment. The PDF uses the demo Steel Quotes identity, includes customer-facing specifications, selling rates, tax and terms, and excludes supplier names, procurement rates and margin details. Quotes pending margin review cannot be downloaded. | Keeps the pilot document useful while business branding, tax treatment and commercial terms await confirmation; avoids exposing internal procurement data | Yes |
| 2026-11-22 | Follow-ups and hardening | Attach dated reminders to enquiries; staff mark completion manually. Use enquiry states New, In progress and Closed, and quote states move through Ready/Approved, Sent, then Accepted/Lost (Expired only after the validity date). New quotes default to seven days of validity, which remains an editable assumption. WhatsApp links appear only for valid phone formats, open with an explicit staff click, and do not prefill or send a message. Product CSV import/export uses a fixed eight-column catalogue schema, validates all rows before an atomic import, is scoped to the signed-in owner, caps uploads at 1 MB / 500 rows, and prefixes spreadsheet formula-like exported cells with an apostrophe. | Provides local follow-up tracking and controlled data portability without background messaging, supplier rates, customer contacts, or cross-account exports | Yes |

| 2026-11-22 | Security review | Generate a random development secret key; require `DJANGO_SECRET_KEY` and explicit allowed hosts with debug disabled; enable HTTPS redirect, secure cookies and one-hour HSTS in production mode; set a 12-character minimum with Django's built-in password validators; rotate the weak local demo admin credential. Keep HSTS subdomain/preload flags off until the real domain and all subdomains are confirmed. | Removes default-key, debug, weak-password and cookie/header risks while avoiding a long-lived HSTS policy for an unconfirmed domain | Yes |

## Questions for the next morning review
1. Should the first demo focus on stainless steel only or include MS/alloy products?
2. Are supplier offers for stock on hand or procurement after an order?
3. What target and minimum gross margins, maximum discount, and manager-approval hierarchy should be used?
4. Which quotation terms and GST treatments apply to your business?
5. Should each sales representative see their own accounts or all company leads?
6. Do supplier offer prices include GST, and should any non-creditable GST enter landed procurement cost?
7. Should unprefixed ten-digit phone numbers always be treated as Indian numbers when opening WhatsApp?
8. Are the selected quotation outcomes and follow-up reminder fields sufficient for the pilot pipeline?
9. What legal company name, logo and quotation contact details should replace the demo document identity?
10. What production hostname and subdomains will be HTTPS-only, and which shared cache should enforce login throttling across workers before any public launch?

Questions do not block unrelated safe implementation. Never fabricate an answer; mark the relevant workflow as a configurable pilot assumption.

## Blockers
None at setup. Record any task failure with failing command, log, and recommended next action.
