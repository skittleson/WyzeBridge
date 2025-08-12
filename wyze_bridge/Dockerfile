FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app
COPY . .
RUN mkdir -p event_images
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8000

ENV WYZE_EMAIL=NA
ENV WYZE_PASSWORD=NA
ENV WYZE_KEY_ID=NA
ENV WYZE_API_KEY=NA

ENV PYTHONPATH=/app
# Run the application
CMD ["python", "api.py"]
