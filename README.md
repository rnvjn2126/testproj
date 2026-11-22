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

## Development checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --noinput
```
