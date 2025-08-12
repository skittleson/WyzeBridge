import random
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from wyze_client_manager import WyzeClientManager


async def schedule_job(job_function) -> None:
    """
    Schedules a job function to run periodically.

    This function takes a job function and a sleep duration,
    and repeatedly executes the job function while handling
    potential exceptions. It logs any errors that occur during
    job execution and continues to the next scheduled run.

    :param job_function: The asynchronous function to be scheduled.
    :type job_function: callable
    """
    while True:
        try:
            job_function()
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
