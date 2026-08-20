#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py validate_echo
printf 'Local setup complete. Create an administrator with: python manage.py createsuperuser\n'
