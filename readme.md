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
| `GET`  | `/locks` | List locks (MAC and nickname). |
| `GET`  | `/locks/{lock_id}` | Full lock status: `state` (`locked`, `unlocked`, `locking`, `unlocking`, `jammed`, `unknown`), `door_open` (`null` when the door sensor is off), `online`, `battery`, `firmware`, `gateway_rssi`, `last_event` (`type`, `description`, `time`, `source`). |
| `GET`  | `/locks/{lock_id}/events?limit=N` | Recent lock history, newest first (1-100, default 20). Includes jams and door-left-open alerts. |
| `PUT`  | `/locks/{lock_id}` | Body `{"lock_action": true\|false}` (or `?lock_action=`). Locks (`true`) or unlocks (`false`) the lock. Returns `502` if Wyze rejects the command. |
| `GET`  | `/cameras` | Every camera with basic details (`nickname`, `model`, `online`, `firmware`, `ip`, `rssi`, `ssid`, `battery`) and its newest cloud event (`id`, `time`, `type`, `tags`). Also `by_mac`, the same cameras keyed by MAC. Cached for `WYZE_CAMERA_CACHE_SECONDS` (default 60). |
| `GET`  | `/cameras/{mac}` | One camera. |
| `GET`  | `/cameras/{mac}/events?limit=N` | That camera's recent cloud events, newest first (1-20; Wyze refuses more). |

> **Caching:** lock status and history are cached for `WYZE_LOCK_CACHE_SECONDS` (default 20) so several Home Assistant pollers share one Wyze call; Wyze rate-limits heavily. Any lock or unlock command clears the cache. Gateway signal is cached for 5 minutes.

> **Note:** The scheduler in `wyze_bridge/jobs.py` automatically refreshes tokens and pulls new events in the background.


### Troubleshooting

| Symptom | Possible Fix |
|---------|--------------|
| Token refresh failures | Ensure `WYZE_EMAIL` and `WYZE_PASSWORD` are correct. Review logs for `refresh_token` errors. |
| Event images not showing | Verify `output` directory permissions. Run `docker exec -it <container> ls ../event_images`. |
| Lock endpoint stuck | Confirm `lock_id` matches a MAC address. Check `client.locks.lock()` call logs.

## Home Assistant

`home_assistant/packages/wyze_lock.yaml` adds a lock entity (with jammed, locking and unlocking states) plus door, online, jammed, battery, last event, firmware and gateway signal sensors. Copy it into your HA `packages/` folder and give the HA container the bridge URL for your lock in its docker compose `.env`:

```dotenv
WYZE_LOCK_URL=http://<bridge-host>:7020/locks/<lock-mac>
```

```yaml
# Home Assistant docker-compose.yml
services:
  homeassistant:
    environment:
      WYZE_LOCK_URL: ${WYZE_LOCK_URL}
```

Find the lock MAC with `GET /locks`.

### Cameras

No live streams: the bridge reads Wyze's cloud for camera details and motion events. Each refresh makes one shared event call (Wyze returns the 20 newest events across all cameras) and looks up one camera that has no event yet, so quiet cameras fill in over the first few minutes. Event images aren't available: Wyze's VerifiedView image links (`prod-sight-safe-auth.wyze.com`) return 401.

Generate the HA package from your camera list, and set `WYZE_CAMERAS_URL=http://<bridge-host>:7020/cameras` in the HA container's environment the same way as `WYZE_LOCK_URL`:

```bash
python home_assistant/generate_camera_package.py http://<bridge-host>:7020/cameras > packages/wyze_cameras.yaml
```

Each camera gets `<name> Last Event` (with `event_id`, `time`, `tags` attributes), `<name> Last Event Time`, `<name> Online` (with model, firmware, IP, Wi-Fi signal and battery attributes) and `<name> Recent Event` (on for 5 minutes after an event). Cameras with the same nickname get the last 4 characters of their MAC added to the name. Re-run the generator when cameras are added or renamed.
