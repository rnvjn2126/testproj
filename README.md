# Steel quotation MVP

Local Django 5.2 application for the steel-trader quotation MVP.

## Windows quick start

From PowerShell in this folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start-local.bat
```

Open <http://127.0.0.1:8000/>. Create a local account in a second terminal with:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

The SQLite database is created locally as `db.sqlite3`. Do not use this development configuration for deployment.

## Follow-ups and catalogue CSV

Use **Follow-ups** to review open reminders. Each enquiry can have dated reminders, and a staff member marks them complete manually. WhatsApp opens only from the explicit link on an enquiry and never sends a message automatically.

The **Products** page supports importing and exporting the product catalogue. CSV uses the headers `name, grade, shape, dimensions, unit, weight_basis, weight_kg, notes`; imports are validated as a whole before saving and exports include only the signed-in user's products. Customer contacts and supplier rates are not included.

## Development checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --noinput
```

## Click-to-run checks on Windows

After creating the `.venv` environment above, double-click **`test-local.bat`**
in File Explorer. It runs the Django configuration check, verifies that no
model migrations are missing, and runs the Django test suite. A clear
`[PASS]` or `[FAIL]` message will appear. This does not require the overnight
controller or Codex CLI.

The test suite covers account isolation, unit normalization, supplier offer
coverage, landed-cost and gross-margin arithmetic, quote PDF permissions,
manual follow-ups, and safe catalogue CSV exports. These are automated
regression tests, not a substitute for a buyer acceptance test.

**Current security boundary:** records are separated per login/user in the
local demo. Shared company accounts and multi-user approval hierarchies require
additional design before any production rollout.
