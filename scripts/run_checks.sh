#!/usr/bin/env sh
set -eu
python scripts/static_validate.py
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py validate_echo
python manage.py validate_tools
python manage.py validate_agents
python manage.py echo_health
python manage.py test
