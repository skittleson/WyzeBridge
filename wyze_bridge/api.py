from wyze_client_manager import WyzeClientManager
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Depends
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
async def get_home():
    return Response(content="200", status_code=200)

@app.get("/devices")
async def get_devices(
    filter_query: list[str] = Depends(parse_csv_query_param("$filter")),
    order_by: str = Query(None, alias='$order_by'),
    select: list[str] = Depends(parse_csv_query_param("$select"))
):
    return manager.get_devices(filter_query=filter_query, orderby=order_by, select=select)

@app.get("/devices/{device_id}")
def get_devices(device_id: str):
    return manager.get_device(device_id)

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
    return Response(content=event_data, media_type="image/jpeg")

@app.put("/locks/{lock_id}")
async def update_lock(lock_id: str = None, lock_action: bool = True):
    return {"success": manager.update_lock(lock_id, lock_action)}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=7020)