#!/bin/bash
set -e


# Step 1: Pull the latest changes from the master branch
echo "Pulling the latest changes from the master branch..."
git checkout main
git pull origin main

# Step 2: Build the Docker containers
echo "Building the Docker containers..."

docker-compose down
docker-compose build

# Step 3: Start the Docker containers
echo "Starting the Docker containers..."
docker-compose up -d --wait

echo "Waiting for FastAPI to be ready..."
until curl -s http://localhost:8000/login | grep -q "status"; do
  echo "FastAPI is not ready yet. Retrying in 5 seconds..."
  sleep 5
done
echo "FastAPI is ready."


# Step 4: Run database migrations with Alembic
echo "Running Alembic migrations..."
docker-compose exec fastapi-app alembic upgrade head

# Step 5: Show the status of the containers
echo "Showing the status of the containers..."
docker-compose ps

echo "Process completed!"

