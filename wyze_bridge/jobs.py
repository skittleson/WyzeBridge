import random
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from wyze_client_manager import WyzeClientManager


async def schedule_job(manager: WyzeClientManager, job_function, sleep_minutes: int) -> None:
    """
    Schedules a job function to run periodically.

    This function takes a job function and a sleep duration,
    and repeatedly executes the job function while handling
    potential exceptions. It logs any errors that occur during
    job execution and continues to the next scheduled run.

    :param manager: The WyzeClientManager instance to be used by the job function.
    :type manager: WyzeClientManager
    :param job_function: The asynchronous function to be scheduled.
    :type job_function: callable
    :param sleep_minutes: The number of minutes to sleep between job executions.
    :type sleep_minutes: int
    """
    while True:
        try:
            await job_function(manager)
        except Exception as e:
            print(f"Error in {job_function.__name__}: {e}")
        await asyncio.sleep(sleep_minutes * 60)


async def refresh_token_job(manager: WyzeClientManager):
    """
    Asynchronously refreshes the access token using the Wyze client manager.

    This function is intended to be run as a background job to automatically refresh
    the access token before it expires. It sleeps for a random interval between
    30 and 120 minutes before triggering the refresh.

    :param manager: The Wyze client manager instance.
    :type manager: WyzeClientManager
    """
    sleep_rand = random.randint(30, 120) * 60
    print(f"Sleeping refresh token {sleep_rand} seconds")
    await asyncio.sleep(sleep_rand)
    print("refresh token triggered")
    manager.client.refresh_token()

async def events_download_job(manager: WyzeClientManager):
    """
    Downloads events using the WyzeClientManager.

    This function initiates a job to save events using the provided manager instance.
    It does not return any value.

    :param manager: The WyzeClientManager instance used for saving events.
    :type manager: WyzeClientManager
    :raises TypeError: if manager is not an instance of WyzeClientManager
    """
    manager.job_save_events()

@asynccontextmanager
async def lifespan(app: FastAPI, manager: WyzeClientManager):
    task01 = asyncio.create_task(schedule_job(refresh_token_job(manager)))
    task02 = asyncio.create_task(events_download_job(manager))
    yield
    task01.cancel()
    task02.cancel()
