import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from wyze_client_manager import WyzeClientManager
from jobs import lifespan
from utils import parse_csv_query_param

load_dotenv()
wyze_email = os.getenv("WYZE_EMAIL", "")
wyze_password = os.getenv("WYZE_PASSWORD", "")
key_id = os.getenv("WYZE_KEY_ID", "")
api_key = os.getenv("WYZE_API_KEY", "")

# Initialize the Wyze client manager with required credentials
if not all([wyze_email, wyze_password, key_id, api_key]):
    raise RuntimeError("Required Wyze credentials are missing. Check environment variables.")

manager = WyzeClientManager(
    email=wyze_email,
    password=wyze_password,
    key_id=key_id,
    api_key=api_key,
)

app = FastAPI(lifespan=lambda x: lifespan(x, manager))

# === Base route ===
@app.get("/")
async def get_home() -> dict:
    """Health‑check endpoint for Home Assistant."""
    return {"status": "ok"}

# === Devices ===
@app.get("/devices")
async def list_devices(
    filter_query: list[str] = Depends(parse_csv_query_param("$filter")),
    order_by: str | None = Query(None, alias="$order_by"),
    select: list[str] | None = Depends(parse_csv_query_param("$select")),
):
    return {"devices": manager.get_devices(filter_query=filter_query, orderby=order_by, select=select)}

@app.get("/devices/{device_id}")
async def get_device(device_id: str) -> dict:
    device = manager.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

# === Events ===
@app.get("/events")
async def list_events() -> dict:
    return {"events": manager.get_events()}

@app.post("/events")
async def download_events() -> dict:
    """Trigger the download of recent camera event images.
    Returns a list of filenames that were downloaded.
    """
    manager.job_save_events()
    return {"events": manager.get_events()}

@app.get("/events/{event_id}")
async def get_event(event_id: str) -> Response:
    event_data = manager.get_event(event_file_id=event_id)
    if not event_data:
        raise HTTPException(status_code=404, detail="Event file not found")
    return Response(content=event_data, media_type="image/jpeg")

# === Locks ===
@app.get("/locks")
async def list_locks() -> dict:
    return {"locks": manager.get_locks()}

@app.get("/locks/{lock_id}")
async def get_lock(lock_id: str) -> dict:
    """Full lock status: state, door, online, battery, firmware, gateway signal, last event."""
    status = manager.get_lock_status(lock_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Lock not found")
    return status

@app.get("/locks/{lock_id}/events")
async def get_lock_events(lock_id: str, limit: int = Query(20, ge=1, le=100)) -> dict:
    return {"events": manager.get_lock_events(lock_id, limit=limit)}

class LockCommand(BaseModel):
    lock_action: bool


@app.put("/locks/{lock_id}")
async def update_lock(lock_id: str, lock_action: bool = True, body: LockCommand | None = None) -> dict:
    """Lock (true) or unlock (false), from a JSON body or the lock_action query param."""
    if body is not None:
        lock_action = body.lock_action
    success = manager.update_lock(lock_id, lock_action)
    if not success:
        raise HTTPException(status_code=502, detail="Wyze rejected the lock command")
    return {"success": success}

# === Run ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7020)
