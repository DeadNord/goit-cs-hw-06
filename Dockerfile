# Use an official Python runtime as a base image
FROM python:3.10

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY src/ ./src
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make ports 3000 (HTTP) and 5000 (Socket) available to the world outside this container
EXPOSE 3000 5000

# No default command, we'll specify it in docker-compose.yml
