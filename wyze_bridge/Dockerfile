# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any necessary dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables for the FastAPI app (to be set at runtime)
ENV WYZE_EMAIL=NA
ENV WYZE_PASSWORD=NA
ENV WYZE_KEY_ID=NA
ENV WYZE_API_KEY=NA

# Run the application
CMD ["python", "api.py"]
