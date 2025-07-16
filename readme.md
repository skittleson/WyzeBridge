# Wyze Bridge

An api and job runner to assist in automation with Wyze devices.

```dotenv
WYZE_EMAIL=
WYZE_PASSWORD=
WYZE_KEY_ID=
WYZE_API_KEY=

```


```bash

docker build -t wyze-bridge-api .
docker run -e WYZE_EMAIL=your_email -e WYZE_PASSWORD=your_password -e WYZE_KEY_ID=your_key_id -e WYZE_API_KEY=your_api_key -p 8000:8000 wyze-bridge-api
```

Or use the docker-compose.yml