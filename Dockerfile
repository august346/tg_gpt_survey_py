# Base image
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Set working directory
WORKDIR /app

RUN apt-get update \
    && apt-get install -y procps \
    && apt-get install -y supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY . .


# Start server with gunicorn
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]