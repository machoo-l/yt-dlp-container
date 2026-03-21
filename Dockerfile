FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install latest yt-dlp binary
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

# Install Flask
RUN pip install flask --break-system-packages

WORKDIR /app

COPY app.py .
COPY yt-dlp.conf .
COPY static/ static/

ENV DOWNLOAD_DIR=/downloads
ENV CONFIG_DIR=/config

EXPOSE 8200

CMD ["python3", "app.py"]
