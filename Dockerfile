FROM surnet/alpine-wkhtmltopdf:3.20.0-0.12.6-small as wkhtmltopdf

FROM python:3.11-alpine

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Set working directory
WORKDIR /app

COPY --from=wkhtmltopdf /bin/wkhtmltopdf /bin/

RUN apk update && apk add --update --no-cache \
    font-urw-base35 \
    procps \
    supervisor \
    libxrender \
    fontconfig \
    freetype \
    libx11 \
    && rm -rf /var/cache/apk/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY . .

# Start server with supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
