from __future__ import annotations
import os
import json
import datetime
import time
import requests
import feedparser
import subprocess
import glob
import re
import sys
import tempfile
from dotenv import load_dotenv

# Add root directory to sys.path for backend imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.pipeline import (
    get_transcript_from_transcriptapi,
    get_transcript_local_fallback,
    detect_content_type,
    prepare_transcript_for_llm,
    call_ollama,
    generate_full_digest as generate_summary,
)

# Load environment variables from .env
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHANNELS_FILE = 'channels.json'
STATE_FILE = 'state.json'
SUMMARIES_DIR = 'summaries'
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434/api/generate')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:4b')

TRANSCRIPTAPI_BASE = 'https://transcriptapi.com/api/v2'
TRANSCRIPTAPI_KEY = os.getenv('TRANSCRIPTAPI_KEY', '')

CHUNK_SIZE = 24000
os.makedirs(SUMMARIES_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Utilities & Cleanup
# ---------------------------------------------------------------------------

def load_json(filepath, default_content):
    if not os.path.exists(filepath):
        return default_content
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def cleanup_old_summaries(max_hours: int = 24):
    """Purge files in summaries/ older than max_hours."""
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=max_hours)
    purged = 0
    for f in glob.glob(os.path.join(SUMMARIES_DIR, "*.md")):
        try:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f), datetime.timezone.utc)
            if mtime < cutoff:
                os.remove(f)
                purged += 1
        except Exception:
            pass
    if purged > 0:
        print(f"[*] Cleanup: Removed {purged} old summary files (>24h).")


# ---------------------------------------------------------------------------
# Summary Storage
# ---------------------------------------------------------------------------

def save_summary(
    video_id: str,
    title: str,
    channel_name: str,
    summary_digest: str | None,
    transcript_label: str,
    published_dt: datetime.datetime | None = None,
) -> str:
    safe_channel = re.sub(r'[^\w\-]', '_', channel_name)
    filename = f"{safe_channel}_{video_id}.md"
    filepath = os.path.join(SUMMARIES_DIR, filename)
    published_str = published_dt.strftime('%d %b %Y %H:%M:%S') if published_dt else "N/A"

    lines = [
        f"# {title}",
        "",
        f"**Channel:** {channel_name} | **Video ID:** {video_id}",
        f"**Published At:** {published_str}",
        f"**Thumbnail:** https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"**Source:** {transcript_label}",
        "",
        "---",
        "",
        "## Detailed Summary Digest",
        "",
        summary_digest or "*Not available*",
        ""
    ]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    return filepath


def process_channel(channel: dict, state: dict):
    channel_name = channel.get('name', 'Unknown')
    channel_id = channel.get('channel_id', '')

    print(f"\n[*] Processing channel: {channel_name} ({channel_id})")
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(feed_url)

    if not hasattr(feed, 'entries') or not feed.entries:
        print("  [-] No entries found in feed.")
        return

    now = datetime.timezone.utc
    now_dt = datetime.datetime.now(now)
    cutoff = now_dt - datetime.timedelta(hours=24) # Strict 24h filter

    for entry in feed.entries:
        video_id = getattr(entry, 'yt_videoid', '')
        if not video_id:
            continue

        title = entry.title
        published_parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
        if published_parsed:
            published_dt = datetime.datetime.fromtimestamp(
                time.mktime(published_parsed), datetime.timezone.utc
            )
        else:
            print(f"  [-] Skipping {title}: Could not parse publication date.")
            continue

        # STRICT 24-HOUR FILTER
        if published_dt < cutoff:
            continue

        if video_id in state.get('processed_videos', {}):
            print(f"  [-] Video {video_id} already processed. Skipping.")
            continue

        print(f"\n[+] Processing 24h video: {title} ({video_id})")

        transcript_api = get_transcript_from_transcriptapi(video_id)
        transcript_local = get_transcript_local_fallback(video_id)

        main_transcript = transcript_api or transcript_local
        transcript_label = "TranscriptAPI" if transcript_api else ("Local Fallback" if transcript_local else "Description Fallback")

        if not main_transcript:
            main_transcript = getattr(entry, 'summary', '')
            print(f"  [*] No transcript found. Falling back to video description.")

        if not main_transcript or not main_transcript.strip():
            print(f"  [-] No transcript or description available. Skipping '{title}'.")
            continue

        summary_digest = generate_summary(main_transcript, title, channel_name)

        filepath = save_summary(
            video_id, title, channel_name,
            summary_digest, transcript_label, published_dt
        )

        state.setdefault('processed_videos', {})[video_id] = {
            "title": title,
            "channel": channel_name,
            "processed_at": datetime.datetime.now().isoformat(),
            "summary_file": filepath,
        }


def check_ollama() -> bool:
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        return True
    except Exception:
        print("  [-] Cannot connect to Ollama at http://localhost:11434")
        return False


def main():
    print("=" * 70)
    print("  YouTube Channel Summarizer — Last 24h Strict Mode")
    print("=" * 70)

    cleanup_old_summaries(max_hours=24)

    if not check_ollama():
        print("\n[!] Aborting — Ollama must be running.")
        return

    channels_data = load_json(CHANNELS_FILE, {"channels": []})
    state = load_json(STATE_FILE, {"processed_videos": {}})

    channels = channels_data.get('channels', [])
    if not channels:
        print("[-] No channels in channels.json.")
        return

    for channel in channels:
        process_channel(channel, state)

    save_json(STATE_FILE, state)
    print("\n[+] Done. All channels processed.")


if __name__ == "__main__":
    main()
