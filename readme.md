# Wyze Bridge

> **Wyze Bridge** – A lightweight API and job runner for automating interactions with Wyze devices.

---

## Overview

Wyze Bridge exposes a simple FastAPI interface that lets you query devices, retrieve events, and control lock status. It also runs background jobs to keep event snapshots up‑to‑date and periodically refresh Wyze OAuth tokens.

* Fetch device lists, filters, and attributes via `/devices`.
* Stream event images via `/events/{id}` after the background job downloads them.
* Lock or unlock a door lock via `PUT /locks/{lock_id}`.
* All of the heavy lifting (OAuth flow, camera streams, lock APIs) is delegated to the official [wyze‑sdk](https://pypi.org/project/wyze-sdk/). The service focuses on exposing a concise HTTP API and a small job scheduler.

## Prerequisites

* **Python 3.10+** – for the source‑checkout version.
* **Docker** – if you only want to run the container.
* **Wyze account** – with an API key (see *Obtaining an API key* section below).

## Installation

### Docker (recommended)

1. **Build the image**
   ```bash
   docker build -t wyze-bridge-api .
   ```
2. **Run the container** (replace the placeholders with your credentials):
   ```bash
   docker run \
     -e WYZE_EMAIL=your_email \
     -e WYZE_PASSWORD=your_password \
     -e WYZE_KEY_ID=your_key_id \
     -e WYZE_API_KEY=your_api_key \
     -p 8000:8000 \
     wyze-bridge-api
   ```

   > _Tip:_ Use the provided `docker-compose.yml` for the same configuration:
   > 
   > ```bash
   > docker compose up --build
   > ```

### Python (dev / local)

```bash
# Clone the repository
git clone https://github.com/your-org/WyzeBridge.git
cd WyzeBridge

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .[dev]

# Create a `.env` file by copying the example
cp .env.example .env
# Edit .env and provide your credentials

# Run the API
uvicorn wyze_bridge.api:app --reload
```

## Obtaining a Wyze API key

1. Log in to your Wyze account in a browser.
2. Go to **Account Settings** → **Developer Settings**.
3. Generate a new API key. Store the *Key ID* and *API Key*; you'll also need your email and password.

## Environment Variables

```dotenv
WYZE_EMAIL=    # your Wyze email
WYZE_PASSWORD= # your Wyze password
WYZE_KEY_ID=   # Wyze API key ID
WYZE_API_KEY=  # Wyze API key secret
```

Place these in a `.env` file at the project root or export them in your shell before starting the service.

## API Reference

All endpoints use **JSON** for responses and accept the same where applicable.

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Health‑check; returns `200`. |
| `GET`  | `/devices` | List devices. Supports OData‑style query params: `$filter`, `$select`, `$order_by`. |
| `GET`  | `/devices/{device_id}` | Retrieve a single device by MAC address. For locks, returns lock status too. |
| `GET`  | `/events` | List event‑image filenames stored in the output directory. |
| `GET`  | `/events/{event_id}` | Return the raw JPEG for the given event ID. |
| `POST` | `/events` | Trigger a quick rescan of camera events and download images. |
| `PUT`  | `/locks/{lock_id}` | Payload: `{ "lock_action": true | false }`. Locks or unlocks the specified lock. |

> **Note:** The scheduler in `wyze_bridge/jobs.py` automatically refreshes tokens and pulls new events in the background.


### Troubleshooting

| Symptom | Possible Fix |
|---------|--------------|
| Token refresh failures | Ensure `WYZE_EMAIL` and `WYZE_PASSWORD` are correct. Review logs for `refresh_token` errors. |
| Event images not showing | Verify `output` directory permissions. Run `docker exec -it <container> ls ../event_images`. |
| Lock endpoint stuck | Confirm `lock_id` matches a MAC address. Check `client.locks.lock()` call logs.
