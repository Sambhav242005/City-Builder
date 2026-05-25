# Raspberry Pi Deployment

CityBuilder deploys from GitHub Actions with a self-hosted runner on the
Raspberry Pi. The Pi runner keeps an outbound connection to GitHub, so GitHub
notifies the Pi when a `main` push starts the workflow.

The workflow in `.github/workflows/deploy-pi.yml` is event-driven:

1. Run backend tests.
2. Build the frontend.
3. If those pass, run the deploy job on the Pi runner.
4. Sync the exact tested commit into `/home/sambhav/CityBuilder`.
5. Install Python, npm, and listed Debian packages.
6. Restart the backend and frontend systemd services.

The Pi exposes the frontend on `http://192.168.1.5:5173` and the backend API
on `http://192.168.1.5:8010`. Port `8000` is intentionally avoided because it
is already used by another Docker service on the Pi.

Add Python packages to `backend/requirements.txt`, frontend packages through
`frontend/package.json` and `frontend/package-lock.json`, and OS packages to
`deploy/system-packages.txt`.
