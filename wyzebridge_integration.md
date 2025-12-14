# WyzeBridge Integration

This integration allows Home Assistant to communicate with the **WyzeBridge** FastAPI service exposed by `api.py`. It provides support for:

* **Lock control** – lock/unlock and monitoring the current state of Wyze smart locks.
* **Event images** – display the most recent event image for each Wyze camera.

The integration uses Home Assistant’s built‑in *REST* component and the *template* and *binary_sensor* helpers to expose the data in a user‑friendly way.

## API Overview

```
GET  /devices            → list all devices
GET  /devices/{device_id} → single device details
GET  /locks              → list all locks (mac, nickname, locked state, battery %)
PUT  /locks/{lock_id}    → lock/unlock a lock (JSON body: {"lock_action": true|false})
GET  /events             → list of event image file names
GET  /events/{event_id}  → raw JPEG image (use in picture‑entity)
```

All endpoints are **public** – no authentication is added by the service.  If you need to lock your security, protect the API with a reverse proxy or a basic auth header.

## Home Assistant Configuration

Below is an example `configuration.yaml` that demonstrates:

* a **lock** entity per Wyze lock using the REST *lock* platform.
* a **binary_sensor** that displays the current lock state.
* a **picture‑entity** showing the latest camera event image.

```yaml
# configuration.yaml
http:
  # optional: if your API is on the same network as HA
  server_port: 80

# REST platform for Wyze locks
lock:
  - platform: rest
    name: "Wyze Front Door"
    resource: "http://wyzebridge.local:7020/locks"
    value_template: '{{ value_json[0].is_locked }}'
    entity_id: lock.wyzebridge_front_door
    lock_action: '{{ lock_action }}'
    unlock_action: '{{ lock_action }}'
    # The `lock_action` and `unlock_action` values are passed from the PUT call
    # Home Assistant will POST a JSON body like `{"lock_action": true}`

binary_sensor:
  - platform: template
    sensors:
      wyzebridge_front_door_locked:
        friendly_name: "Front Door Locked"
        value_template: '{{ states(''lock.wyzebridge_front_door'') == "locked" }}'

# Picture entity for camera events
camera:
  - platform: rest
    name: "Wyze Front Door Camera"
    resource: "http://wyzebridge.local:7020/events"
    method: GET
    timeout: 10
    # Extract the most recent file name
    value_template: '{{ value_json[0] }}'

picture_entity:
  - entity: camera.wyzebridge_front_door_camera
    name: Front Door Camera
    image_class: camera
    state_image: "{{ url_for('static', filename='placeholder.png') }}"
    # The entity returns a JPEG; use `entity_picture` instead
```

### Notes

1. **Multiple locks** – If you have several Wyze locks, change the `name` and `entity_id` accordingly and point to the same `/locks` endpoint; the lock platform will filter by the `mac` field.
2. **Event images** – The `/events` endpoint returns a JSON array of filenames.  The `value_template` picks the first item (most recent).  The `picture_entity` then displays the image by requesting `/events/<filename>`.
3. **Security** – This example assumes the Bridge is reachable at `wyzebridge.local`.  In production, use HTTPS and optionally a reverse proxy that requires authentication.

## Testing the Integration

1. Start the WyzeBridge service:
   ```bash
   uvicorn wyze_bridge.api:app --host 0.0.0.0 --port 7020
   ```
2. In Home Assistant, reload the `configuration.yaml` or restart HA.
3. The lock and camera entities should appear in the UI.
4. Use the lock UI to lock/unlock or check the binary sensor state.
5. View the camera picture to see the latest event image.

Feel free to adjust the templates or platform settings to fit your exact hardware and naming conventions.  Happy automating!

---

*Author: Your Name – based on WyzeBridge API*