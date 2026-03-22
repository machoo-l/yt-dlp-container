#!/usr/bin/env python3
"""
PULL — yt-dlp web downloader backend
Flask server with SSE streaming for live terminal output
"""

from flask import Flask, request, jsonify, Response, send_from_directory
import subprocess
import threading
import queue
import os
import json
import uuid
from datetime import datetime

app = Flask(__name__, static_folder="static")

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/downloads")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/config")
CONF_FILE = "/app/yt-dlp.conf"

# Active job streams: job_id -> queue of log lines
job_streams = {}
job_status = {}  # job_id -> 'running' | 'done' | 'error'
job_lock = threading.Lock()


def run_download(job_id, url):
    log_queue = job_streams[job_id]

    def emit(line, level="info"):
        log_queue.put(json.dumps({"line": line, "level": level, "ts": datetime.now().strftime("%H:%M:%S")}))

    emit(f"starting download: {url}", "info")

    cmd = [
        "yt-dlp",
        url
    ]

    emit(f"cmd: {' '.join(cmd)}", "debug")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            level = "info"
            if "[download]" in line:
                level = "progress"
            elif "ERROR" in line or "error" in line.lower():
                level = "error"
            elif "WARNING" in line:
                level = "warn"
            elif "[ExtractAudio]" in line or "[EmbedThumbnail]" in line or "[Metadata]" in line:
                level = "success"
            elif "has already been recorded" in line:
                level = "skip"
            emit(line, level)

        proc.wait()

        if proc.returncode == 0:
            emit("✓ download complete", "success")
            with job_lock:
                job_status[job_id] = "done"
        else:
            emit(f"✗ yt-dlp exited with code {proc.returncode}", "error")
            with job_lock:
                job_status[job_id] = "error"

    except FileNotFoundError:
        emit("✗ yt-dlp not found", "error")
        with job_lock:
            job_status[job_id] = "error"
    except Exception as e:
        emit(f"✗ unexpected error: {e}", "error")
        with job_lock:
            job_status[job_id] = "error"
    finally:
        log_queue.put(None)  # sentinel to close stream


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/download", methods=["POST"])
def start_download():
    data = request.get_json()
    url = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400

    job_id = str(uuid.uuid4())[:8]
    with job_lock:
        job_streams[job_id] = queue.Queue()
        job_status[job_id] = "running"

    thread = threading.Thread(target=run_download, args=(job_id, url), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/stream/<job_id>")
def stream(job_id):
    if job_id not in job_streams:
        return jsonify({"error": "job not found"}), 404

    def generate():
        q = job_streams[job_id]
        while True:
            item = q.get()
            if item is None:
                yield f"data: {json.dumps({'done': True, 'status': job_status.get(job_id, 'done')})}\n\n"
                break
            yield f"data: {item}\n\n"
        # cleanup after a delay
        with job_lock:
            job_streams.pop(job_id, None)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/archive")
def get_archive():
    path = f"{CONFIG_DIR}/downloadarchive.txt"
    try:
        with open(path) as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        entries = []
        for line in lines:
            parts = line.split(" ", 2)
            source = parts[0] if len(parts) > 0 else ""
            video_id = parts[1] if len(parts) > 1 else ""
            title = parts[2] if len(parts) > 2 else ""
            entries.append({"raw": line, "source": source, "id": video_id, "title": title})
        return jsonify({"count": len(entries), "entries": entries})
    except FileNotFoundError:
        return jsonify({"count": 0, "entries": []})


@app.route("/archive/delete", methods=["POST"])
def delete_archive_entry():
    data = request.get_json()
    raw = (data or {}).get("raw", "").strip()
    if not raw:
        return jsonify({"error": "raw entry required"}), 400
    path = f"{CONFIG_DIR}/downloadarchive.txt"
    try:
        with open(path) as f:
            lines = f.readlines()
        new_lines = [l for l in lines if l.strip() != raw]
        with open(path, "w") as f:
            f.writelines(new_lines)
        return jsonify({"success": True, "removed": len(lines) - len(new_lines)})
    except FileNotFoundError:
        return jsonify({"error": "archive not found"}), 404


@app.route("/archive/clear", methods=["POST"])
def clear_archive():
    path = f"{CONFIG_DIR}/downloadarchive.txt"
    try:
        open(path, "w").close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    print(f"[PULL] downloads → {DOWNLOAD_DIR}")
    print(f"[PULL] config    → {CONFIG_DIR}")
    app.run(host="0.0.0.0", port=8200, threaded=True)
