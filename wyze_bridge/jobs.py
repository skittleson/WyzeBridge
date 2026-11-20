import random
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from wyze_client_manager import WyzeClientManager


async def schedule_job(job_function) -> None:
    """
    Runs a blocking job periodically WITHOUT freezing the event loop.

    The wyze_sdk calls here (token refresh, event-image downloads) are
    synchronous and can take minutes; running them directly on the loop
    wedged the whole app (HA lock/camera entities went unavailable).
    asyncio.to_thread keeps the loop responsive while the job runs.
    """
    while True:
        try:
            await asyncio.to_thread(job_function)
        except Exception as e:
            print(f"Error in {job_function.__name__}: {e}")
        sleep_minutes = random.randint(10, 60)
        await asyncio.sleep(sleep_minutes * 60)

@asynccontextmanager
async def lifespan(app: FastAPI, manager: WyzeClientManager):
    task01 = asyncio.create_task(schedule_job(manager.client.refresh_token))
    task02 = asyncio.create_task(schedule_job(manager.job_save_events))
    yield
    task01.cancel()
    task02.cancel()
