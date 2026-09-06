FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt pytest==8.3.4

# Baked copy so the image is self-contained; docker-compose additionally bind
# mounts the repo read-only at /app so the running server uses live source.
COPY . /app/mcp

# No PYTHONPATH: server.py runs as a script, so /app/mcp is sys.path[0] and
# `import loaders` resolves locally while `import mcp` resolves to the SDK.
CMD ["python", "/app/mcp/server.py"]
