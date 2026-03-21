# PULL — yt-dlp Web Downloader
# Drop-in replacement for MeTube using your own yt-dlp.conf

## Files
# app.py          — Flask backend with SSE streaming
# static/index.html — Web UI
# yt-dlp.conf     — your yt-dlp options (baked into image)
# Dockerfile      — builds the container

## Setup

# 1. Copy all files to your Pi
mkdir -p /srv/docker/pull/static
# scp these files into that folder

# 2. Build the image
cd /srv/docker/pull
docker build -t pull-ytdlp .

# 3. Add to your Portainer stack:

  pull:
    image: pull-ytdlp
    container_name: pull
    restart: unless-stopped
    ports:
      - "8200:8200"
    volumes:
      - /srv/docker/music:/downloads
      - /srv/docker/pull/config:/config
    environment:
      DOWNLOAD_DIR: /downloads
      CONFIG_DIR: /config

# 4. Create config dir and archive file
mkdir -p /srv/docker/pull/config
touch /srv/docker/pull/config/downloadarchive.txt
chmod 666 /srv/docker/pull/config/downloadarchive.txt

# 5. Access at http://your-pi-ip:8200

## Updating yt-dlp.conf
# Edit /srv/docker/pull/yt-dlp.conf on the Pi, then rebuild:
# docker build -t pull-ytdlp /srv/docker/pull && docker restart pull

## Notes
# - archive is stored in /config/downloadarchive.txt (persisted volume)
# - downloads go to /downloads (your /srv/docker/music folder)
# - live terminal output streams to the browser as downloads run
# - supports videos, playlists, and channels
