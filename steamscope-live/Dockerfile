# Dockerfile: packages the SteamBank website + prediction API into one image.

# 1. Start from a small official Python image
FROM python:3.12-slim

# 2. Work inside /app in the container
WORKDIR /app

# 3. Install the Python packages first (cached, so rebuilds are fast when only code changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the website, the API code and the trained model
COPY . .

# 5. The server listens on port 8000
ENV PORT=8000
EXPOSE 8000

# 6. Start the server when the container runs
CMD ["python", "server.py"]
