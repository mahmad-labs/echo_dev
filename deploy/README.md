# Deployment assets

These files support a conventional Linux deployment without containerization. Replace paths, hostnames, process counts, and certificate locations for the target environment. Install the systemd units under `/etc/systemd/system/`, the Nginx site under `/etc/nginx/sites-available/`, and the environment file at `/etc/echo/echo.env` with owner-only read permissions. Review every hardening directive against the server layout before enabling the services.
