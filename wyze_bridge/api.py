from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Depends
from wyze_client_manager import WyzeClientManager
import os
from dotenv import load_dotenv
from fastapi.responses import Response
from jobs import lifespan
from utils import parse_csv_query_param

load_dotenv()
wyze_email = os.getenv("WYZE_EMAIL")
wyze_password = os.getenv("WYZE_PASSWORD")
key_id = os.getenv("WYZE_KEY_ID")
api_key = os.getenv("WYZE_API_KEY")

manager = WyzeClientManager(
    email=wyze_email,
    password=wyze_password,
    key_id=key_id,
    api_key=api_key
)
app = FastAPI(lifespan=lambda x: lifespan(x, manager))

@app.get("/")
async def get_status():
    return manager.get_devices()

@app.get("/devices")
async def get_devices(
    filter_query: list[str] = Depends(parse_csv_query_param("$filter")),
    order_by: str = Query(None, alias='$order_by'),
    select: list[str] = Depends(parse_csv_query_param("$select"))
):
    return manager.get_devices(filter_query=filter_query, orderby=order_by, select=select)

@app.get("/events")
async def get_events():
    return manager.get_events()

@app.post("/events")
async def get_events():
    manager.job_save_events()
    return manager.get_events()

@app.get("/events/{event_id}")
async def get_event(event_id: str):
    event_data = manager.get_event(event_file_id=event_id)
    if not event_data:
        raise HTTPException(status_code=404, detail="Event file not found")
    headers = {
        "Content-Disposition": f"attachment; filename={event_id}.jpg"
    }
    return Response(content=event_data, media_type="image/jpeg", headers=headers)

def _get_lock_id(lock_name=None):
    if lock_name is not None:
        lock_id = manager.get_lock_by_name(lock_name)
        if not lock_id:
            raise HTTPException(status_code=400, detail=f"Lock with name {lock_name} does not exist")
    else:
        lock_id = None
    return lock_id

@app.put("/locks/{lock_id}")
@app.put("/locks/={lock_name}")
async def update_lock(lock_id: str = None, lock_name: str = None, lock_action: bool = True):
    if lock_name is not None:
        lock_id = _get_lock_id(lock_name)
    elif lock_id is None:
        raise HTTPException(status_code=400, detail="Missing lock name or id")
    return {"success": manager.update_lock(lock_id, lock_action)}

@app.get("/locks/")
async def get_locks():
    return manager.get_locks()

@app.get("/locks/{lock_id}")
@app.get("/locks/={lock_name}")
async def get_lock(lock_id: str = None, lock_name: str = None):
    if lock_id is not None:
        lock_info = manager.get_lock(lock_id)
    elif lock_name is not None:
        lock_id = _get_lock_id(lock_name)
        lock_info = manager.get_lock(lock_id)
    else:
        raise HTTPException(status_code=400, detail="Missing lock name or id")
    if not lock_info:
        raise HTTPException(status_code=404, detail="Lock not found")
    return lock_info



if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)