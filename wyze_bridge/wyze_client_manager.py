import json

import requests
import os
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

class WyzeClientManager:
    OUTPUT_DIR = '../event_images'

    def __init__(self, email="", password="", key_id="", api_key="", client=Client):
        self.client = client(email=email, password=password, key_id=key_id, api_key=api_key)
        self.__ensure_dir_exists()

    def __ensure_dir_exists(self):
        if not os.path.exists(self.OUTPUT_DIR):
            os.makedirs(self.OUTPUT_DIR)

    def download(self, url: str, file_path: str) -> None:
        """Download image from URL and save it to the specified path."""
        self.__ensure_dir_exists()
        if os.path.exists(file_path):
            print(f"Skipping existing file: {file_path}")
            return
        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"Downloaded: {file_path}")
            else:
                print(f"Failed to download image. Status code: {response.status_code}")
        except Exception as e:
            print(f"An error occurred while downloading the image: {e}")

    def get_event(self, event_file_id: str) -> bytes:
        """
        Retrieves event data from a file.

        :param event_file_id: The identifier of the event file.
        :type event_file_id: str
        :raises FileNotFoundError: If the event file is not found.
        :return: The event data as bytes, or an empty byte string if the file is not found.
        :rtype: bytes
        """
        self.__ensure_dir_exists()
        filepath = os.path.join(self.OUTPUT_DIR, event_file_id + ".jpg")
        try:
            with open(filepath, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b''
        
    def get_events(self) ->list[str]:
        """
        Retrieves a list of event files from the output directory.

        This method scans the designated output directory and returns a list of file names
        that represent event files. It filters out directories and only includes actual files.

        :raises:
            OSError: If there's an issue accessing the output directory.

        :return: A list of strings, where each string is the name of an event file.
        """
        files = os.listdir(self.OUTPUT_DIR)
        return [f for f in files if os.path.isfile(os.path.join(self.OUTPUT_DIR, f))]

    def job_save_events(self):
        """
        Downloads event images from Wyze cameras.

        This method retrieves event lists from each Wyze camera managed by the client,
        downloads the associated images, and saves them to the specified output directory.
        It handles potential errors during API calls and image downloads.
        """
        try:
            cameras = self.client.cameras.list()
            for camera in cameras:
                events = self.client.events.list(device_mac=camera.mac, limit=10)
                for event in events:
                    for file in event.files:
                        image_url = file.url
                        filename = f"{file.id}_{event.time}.jpg"
                        filepath = os.path.join(self.OUTPUT_DIR, filename)
                        self.download(image_url, filepath)
        except WyzeApiError as e:
            print(f"An error occurred: {e}")

    def get_locks(self):
        """
        Retrieves a list of locks associated with the client.

        This method fetches a list of locks from the client's lock collection
        and returns a list of dictionaries, each containing the MAC address
        and nickname of a lock.

        :return: A list of dictionaries, where each dictionary represents a lock
                 and contains its MAC address and nickname.  Returns an empty list
                 if no locks are found or if an error occurs during retrieval.
        """
        locks = self.client.locks.list()
        return [{'mac': lock.mac, 'nickname': lock.nickname} for lock in locks]

    def get_lock(self, lock_id: str):
        """
        Retrieves information about a door lock.

        :param lock_id: The MAC address of the door lock.
        :raises WyzeApiError: If an error occurs during the API call.
        :return: A dictionary containing lock information (is_locked, nickname,
            percentage, mac) if the lock is found, otherwise None.
        """
        try:
            lock_info = self.client.locks.info(device_mac=lock_id)
            if lock_info is None:
                return None
            return {'is_locked': lock_info.is_locked,
                    'nickname': lock_info.nickname,
                    'percentage': lock_info._voltage._value,
                    'mac': lock_info.mac }
        except WyzeApiError as e:
            print(f"An error occurred while getting door lock: {e}")
        return None

    def get_lock_by_name(self, name: str):
        """
        Retrieves a lock object by its nickname.

        This method searches for a lock with the given nickname among the available locks
        and returns the corresponding lock object. If no lock with the specified nickname
        is found, it returns None.
        """
        locks = self.get_locks()
        lock = next((l for l in locks if l["nickname"] == name), None)
        if lock:
            lock_id = lock["mac"]
            return self.get_lock(lock_id)
        return None

    def update_lock(self, lock_id: str, lock_action: bool) -> bool:
        """
        Updates the lock status of a given lock.

        :param lock_id: The ID of the lock to update.
        :type lock_id: str
        :param lock_action: A boolean value indicating whether to lock or unlock the lock.
                             True to lock, False to unlock.
        :type lock_action: bool
        :raises WyzeApiError: If an error occurs while communicating with the Wyze API.
        :returns: True if the lock status was successfully updated, False otherwise.
        :rtype: bool
        """
        if lock_action:
            self.client.locks.lock(lock_id)
        else:
            self.client.locks.unlock(lock_id)
        return True

    def get_devices(self, filter_query=None, orderby=None, select=None):
        devices = self.client.devices_list()
        device_dicts = []

        # Extract relevant information from each device
        for device in devices:
            device_info = {
                "nickname": device.nickname,
                "mac": device.mac,
                "type": device.type,
                "product_type": device.product.type
            }
            device_dicts.append(device_info)

        if filter_query:
            for key, value in filter_query.items():
                device_dicts = [device for device in device_dicts if device.get(key) == value]

        if select:
            if not isinstance(select, list):
                raise ValueError("The 'select' parameter must be a list of field names")
            device_dicts = [{key: device[key] for key in select if key in device} for device in device_dicts]

        if orderby:
            reverse = False
            if orderby.startswith('-'):
                orderby = orderby[1:]
                reverse = True
            device_dicts.sort(key=lambda x: x.get(orderby), reverse=reverse)

        return device_dicts

