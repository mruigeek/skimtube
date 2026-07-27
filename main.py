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
# Transcript Fetching
# ---------------------------------------------------------------------------

def get_transcript_from_transcriptapi(video_id: str) -> str | None:
    if not TRANSCRIPTAPI_KEY:
        print("  [!] TRANSCRIPTAPI_KEY not set — skipping TranscriptAPI source.")
        return None

    print("  [*] Trying TranscriptAPI (production)...")
    url = f"{TRANSCRIPTAPI_BASE}/youtube/transcript"
    headers = {"Authorization": f"Bearer {TRANSCRIPTAPI_KEY}"}
    params = {
        "video_url": video_id,
        "format": "text",
        "include_timestamp": "false",
        "send_metadata": "false",
    }

    retryable = {408, 429, 503}
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("transcript", "")
                if isinstance(text, str) and text.strip():
                    print(f"  [+] TranscriptAPI OK (lang: {data.get('language', '?')})")
                    return text.strip()
                return None

            if resp.status_code in retryable:
                wait = int(resp.headers.get("Retry-After", 2 ** attempt))
                time.sleep(wait)
                continue
            return None

        except requests.exceptions.RequestException:
            if attempt < 2:
                time.sleep(2 ** attempt)

    return None


def clean_vtt_text(vtt_content: str) -> str:
    text_lines = []
    for line in vtt_content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (stripped.startswith('WEBVTT') or stripped.startswith('Kind:') or
                stripped.startswith('Language:') or stripped.startswith('Style:') or
                '-->' in stripped or stripped.isdigit()):
            continue
        clean_line = re.sub(r'<[^>]+>', '', stripped).strip()
        if not clean_line:
            continue
        if text_lines and text_lines[-1] == clean_line:
            continue
        text_lines.append(clean_line)

    result = []
    for line in text_lines:
        if result and not result[-1].endswith(('.', '?', '!', ',')):
            result.append(' ')
        result.append(line)
    return ''.join(result)


def get_transcript_from_youtube_api(video_id: str) -> str | None:
    """Fetch transcript using youtube-transcript-api, multi-language support."""
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        print("  [*] Trying youtube-transcript-api...")
        api = YouTubeTranscriptApi()
        
        try:
            tl = api.list(video_id)
            for t in tl:
                fetched = t.fetch()
                text = " ".join([item.text if hasattr(item, 'text') else item.get('text', '') for item in fetched])
                if text.strip():
                    print(f"  [+] youtube-transcript-api OK ({t.language})")
                    return text.strip()
        except Exception:
            pass

        try:
            transcript_obj = api.fetch(video_id, languages=['en', 'ta', 'hi', 'te', 'es', 'fr', 'de', 'auto'])
            text = " ".join([item.text if hasattr(item, 'text') else item.get('text', '') for item in transcript_obj])
            if text.strip():
                print("  [+] youtube-transcript-api direct fetch OK")
                return text.strip()
        except Exception:
            pass

    except Exception as e:
        print(f"  [-] youtube-transcript-api failed: {e}")

    return None


def get_transcript_from_ytdlp_subtitles(video_id: str) -> str | None:
    """Fallback: download VTT subtitles via yt-dlp."""
    print("  [*] Trying yt-dlp subtitles...")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    os.makedirs("downloads", exist_ok=True)

    command = [
        sys.executable, "-m", "yt_dlp",
        "--write-auto-subs", "--write-subs",
        "--sub-langs", "all,-live_chat",
        "--skip-download", "--sub-format", "vtt",
        "-o", "downloads/%(id)s.%(ext)s",
        video_url,
    ]

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        pass

    vtt_files = glob.glob(f"downloads/{video_id}*.vtt")
    if not vtt_files:
        print("  [-] No subtitles found via yt-dlp")
        return None

    print("  [+] Found subtitles via yt-dlp")
    with open(vtt_files[0], 'r', encoding='utf-8') as f:
        vtt_content = f.read()

    for vf in vtt_files:
        try:
            os.remove(vf)
        except Exception:
            pass

    return clean_vtt_text(vtt_content)


def get_transcript_local_fallback(video_id: str) -> str | None:
    transcript = get_transcript_from_youtube_api(video_id)
    if transcript:
        return transcript
    return get_transcript_from_ytdlp_subtitles(video_id)


# ---------------------------------------------------------------------------
# Prompts & LLM Generation
# ---------------------------------------------------------------------------

NEWS_KEYWORDS = ['bbc', 'cnn', 'news', 'reuters', 'guardian', 'times', 'post', 'daily', 'breaking', 'report', 'press']
TECH_KEYWORDS = ['ai', 'machine learning', 'tutorial', 'coding', 'programming', 'developer', 'software', 'llm', 'gpt', 'python', 'javascript', 'devops', 'cloud', 'how to', 'build', 'deploy', 'install', 'setup', 'configure', 'automation', 'model', 'open source']


def detect_content_type(channel_name: str, video_title: str) -> str:
    combined = (channel_name + " " + video_title).lower()
    news_score = sum(1 for kw in NEWS_KEYWORDS if kw in combined)
    tech_score = sum(1 for kw in TECH_KEYWORDS if kw in combined)
    if news_score > tech_score:
        return 'news'
    if tech_score > 0:
        return 'tech'
    return 'general'


def prepare_transcript_for_llm(transcript: str, max_chars: int = 24000) -> str:
    if len(transcript) <= max_chars:
        return transcript
    section_size = max_chars // 3
    start = transcript[:section_size]
    mid_start = (len(transcript) // 2) - (section_size // 2)
    middle = transcript[mid_start: mid_start + section_size]
    end = transcript[-section_size:]
    return f"{start}\n\n[... middle section ...]\n\n{middle}\n\n[... final section ...]\n\n{end}"


def call_ollama(prompt: str) -> str | None:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "top_p": 0.9},
    }
    try:
        resp = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json().get('response', '').strip()
    except Exception as e:
        print(f"  [-] Ollama request failed: {e}")
        return None


def generate_summary(transcript: str, video_title: str, channel_name: str) -> str | None:
    content_type = detect_content_type(channel_name, video_title)
    sampled_transcript = prepare_transcript_for_llm(transcript, max_chars=24000)

    if content_type == 'news':
        guidance = "Focus on WHO, WHAT, WHERE, WHEN, WHY, and key impacts."
    elif content_type == 'tech':
        guidance = "Focus on TOOLS USED, STEPS, CODE CONCEPTS, ARCHITECTURE, and KEY ADVANTAGES."
    else:
        guidance = "Focus on CORE ARGUMENTS, CONCRETE NUMBERS/METRICS, CLAIMS, and PRACTICAL TAKEAWAYS."

    prompt = f"""You are an expert content analyst producing a structured digest of a YouTube video transcript.
If the transcript is in a non-English language, translate and write the digest entirely in clear English.

Video Title: {video_title}
Channel: {channel_name}
Category: {content_type}
Guidance: {guidance}

STRICT OUTPUT RULES — follow every rule without exception:
- Output ONLY the structured markdown below. No preamble, intro, or closing remarks.
- Do NOT use phrases like "The video covers", "In this video", "The author explains". State facts directly.
- Every bullet MUST contain a specific fact, name, number, tool, decision, or argument lifted directly from the transcript.

## TL;DR
[1–2 sentence summary in English of the core takeaway]

## Key Takeaways
- [3–7 rich bullets with concrete details, numbers, or claims]

## Detailed Breakdown
[3–5 paragraph detailed breakdown of the content]

Transcript:
{sampled_transcript}
"""
    return call_ollama(prompt)


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

        if not transcript_api and not transcript_local:
            print(f"  [-] No transcript from either source. Skipping '{title}'.")
            continue

        main_transcript = transcript_api or transcript_local
        transcript_label = "TranscriptAPI" if transcript_api else "Local Fallback"

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
