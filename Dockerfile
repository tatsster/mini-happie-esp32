FROM python:3.13-slim

WORKDIR /app

# Install Pillow system dependencies in a single layer to keep image small
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for pip layer caching (requirements change rarely)
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Copy app code last (changes most often — cache miss here is cheap)
COPY server/ server/

# Create bind-mount target directories inside the image
RUN mkdir -p /app/data/frames /app/data/songs

# Shell-form CMD so $PORT is interpolated at runtime (exec-form does NOT expand env vars)
CMD sh -c "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}"
