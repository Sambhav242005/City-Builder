# Raspberry Pi Deployment

CityBuilder deploys from GitHub Actions with a self-hosted runner on the
Raspberry Pi. The Pi runner keeps an outbound connection to GitHub, so GitHub
notifies the Pi when a `main` push starts the workflow.

The workflow in `.github/workflows/deploy-pi.yml` is event-driven:

1. Run backend tests.
2. Build the frontend.
3. If those pass, run the deploy job on the Pi runner.
4. Sync the exact tested commit into `/home/sambhav/CityBuilder`.
5. Install listed Debian packages.
6. Rebuild and restart the Docker Compose stack.

The Pi exposes a single frontend/proxy entrypoint on `http://192.168.1.5:5173`.
Cloudflare Tunnel should point at that port. The browser calls the public
origin only, and Nginx proxies `/api/*` to the backend container internally.
The backend container listens on `8085` inside the Docker network but is not
published directly to the LAN.

Add Python packages to `backend/requirements.txt`, frontend packages through
`frontend/package.json` and `frontend/package-lock.json`, and OS packages to
`deploy/system-packages.txt`.

Containers use `restart: unless-stopped`, so Docker brings the app back after a
container crash or Pi reboot. If the Pi is powered off, the site is offline
until the Pi starts again.
