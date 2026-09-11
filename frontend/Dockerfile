FROM python:3.12-slim

WORKDIR /app

# Copy the entire frontend folder content
COPY . .

# Serve static files on port 8080 using Python's built-in HTTP server
CMD ["python", "-m", "http.server", "8080"]