# Security review

## Fixes made

- Replaced the known development signing key with a fresh random key per local process. Production mode now requires `DJANGO_SECRET_KEY` and refuses wildcard hosts.
- Made `DEBUG` and allowed hosts configurable. Production mode turns on HTTPS redirects, secure and HTTP-only session cookies, secure CSRF cookies, same-site cookie policy, one-hour HSTS, content-type sniffing protection, a same-origin referrer policy, and frame denial.
- Raised Django's built-in minimum password length to 12 while retaining its similarity, common-password, and numeric-password checks. Rotated the local `admin` account away from the weak demo password.
- Added regression coverage for CSRF rejection/acceptance, untrusted host rejection, password policy, security headers, import file/row caps, existing owner scoping, and customer-document data boundaries.
- Kept the existing protections that require authentication, scope records to their owner, prevent CSV formula execution, and exclude procurement costs/margins from customer quotations.

## Local bypass checks

- A state-changing request without a CSRF token returned `403` and did not change the enquiry; the same request with a valid token succeeded.
- A request with `Host: attacker.example` returned `400`.
- Before the local account was rotated, the demo password `12345` authenticated. It has been replaced with a generated password and the old credential no longer authenticates.
- Password validation rejects short and numeric-only values. CSV import rejects files over 1 MB and uploads with more than 500 rows.

## Verification

- `manage.py check`: passed with no issues.
- `manage.py makemigrations --check --dry-run`: passed; no model changes are pending.
- `manage.py test --noinput`: passed, 53 tests.
- Production-mode `manage.py check --deploy`: ran with a temporary secret and explicit test hostname. Django reported only `security.W005` and `security.W021` because HSTS subdomain coverage and browser preload are intentionally disabled until the production domain is confirmed.

## Remaining decisions before a public launch

- Confirm the production hostname and whether every subdomain is HTTPS-only before enabling HSTS subdomain coverage or preload.
- Choose a shared cache and add login-attempt throttling before exposing sign-in publicly. The current local-only app does not implement throttling, and an in-process cache would not protect a multi-worker deployment.
- Configure the trusted TLS proxy/header behavior for the actual hosting platform before enabling production HTTPS redirects.
- Configure recovery, operational monitoring, backups, and production secret storage as part of deployment planning. No deployment was performed in this review.
