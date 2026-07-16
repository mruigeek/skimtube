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
OLLAMA_API_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'gemma4:latest'

# TranscriptAPI (ZeroPointRepo/youtube-skills)
TRANSCRIPTAPI_BASE = 'https://transcriptapi.com/api/v2'
TRANSCRIPTAPI_KEY = os.getenv('TRANSCRIPTAPI_KEY', '')

# Max chars sent to LLM per chunk. ~4 chars/token → 24k chars is safe for gemma3:4b
CHUNK_SIZE = 24000

os.makedirs(SUMMARIES_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def load_json(filepath, default_content):
    """Load a JSON file or return default_content if missing."""
    if not os.path.exists(filepath):
        return default_content
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath, data):
    """Persist data to a JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


# ---------------------------------------------------------------------------
# Transcript fetching — TranscriptAPI (primary, production-grade)
# ---------------------------------------------------------------------------

def get_transcript_from_transcriptapi(video_id: str) -> str | None:
    """
    Primary method: TranscriptAPI.com (ZeroPointRepo/youtube-skills).
    Costs 1 credit per successful call. No IP-block issues.
    Returns plain text transcript, or None on failure.
    """
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
                print("  [-] TranscriptAPI returned empty transcript.")
                return None

            if resp.status_code in retryable:
                wait = int(resp.headers.get("Retry-After", 2 ** attempt))
                print(f"  [!] TranscriptAPI {resp.status_code} — retrying in {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 402:
                print("  [-] TranscriptAPI: no credits remaining.")
            elif resp.status_code == 404:
                print("  [-] TranscriptAPI: no transcript available for this video.")
            elif resp.status_code == 401:
                print("  [-] TranscriptAPI: invalid API key.")
            else:
                print(f"  [-] TranscriptAPI error {resp.status_code}: {resp.text[:200]}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"  [-] TranscriptAPI request error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    return None


# ---------------------------------------------------------------------------
# Transcript fetching — local fallbacks (original implementation)
# ---------------------------------------------------------------------------

def clean_vtt_text(vtt_content: str) -> str:
    """
    Parse a VTT subtitle file into clean, deduplicated plain text.
    Auto-generated subtitles typically duplicate lines; we strip those out.
    """
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


def get_browser_cookies_flag() -> str | None:
    """Return yt-dlp --cookies-from-browser value for the best available browser."""
    candidates = [
        ("/Applications/Google Chrome.app", "chrome"),
        ("/Applications/Microsoft Edge.app", "edge"),
        ("/Applications/Firefox.app", "firefox"),
        ("/Applications/Safari.app", "safari"),
    ]
    for app_path, name in candidates:
        if os.path.exists(app_path):
            return name
    return None


def get_transcript_from_youtube_api(video_id: str) -> str | None:
    """
    Fallback 1: youtube-transcript-api.
    Retries with browser cookies if YouTube blocks the IP.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        print("  [*] Trying youtube-transcript-api (no cookies)...")
        api = YouTubeTranscriptApi()
        transcript_obj = api.fetch(video_id)
        text = " ".join([s.text for s in transcript_obj])
        if text.strip():
            return text
    except Exception as e:
        err = str(e).lower()
        is_ip_block = any(k in err for k in ("blocked", "ip", "requestblocked", "ipblocked"))
        if not is_ip_block:
            print(f"  [-] youtube-transcript-api failed: {e}")
            return None
        print("  [!] IP blocked. Retrying with browser cookies...")

    browser = get_browser_cookies_flag()
    if not browser:
        print("  [-] No supported browser found for cookie extraction.")
        return None

    cookie_file = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode='w') as tf:
            cookie_file = tf.name

        print(f"  [*] Extracting {browser} cookies via yt-dlp...")
        extract_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--cookies-from-browser", browser,
            "--cookies", cookie_file,
            "--skip-download", "--quiet",
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        subprocess.run(extract_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

        if not os.path.exists(cookie_file) or os.path.getsize(cookie_file) == 0:
            print("  [-] Cookie extraction produced an empty file.")
            return None

        import requests as req
        from http.cookiejar import MozillaCookieJar
        session = req.Session()
        jar = MozillaCookieJar(cookie_file)
        jar.load(ignore_discard=True, ignore_expires=True)
        session.cookies = jar

        print(f"  [*] Trying youtube-transcript-api with {browser} cookies...")
        api = YouTubeTranscriptApi(http_client=session)
        transcript_obj = api.fetch(video_id)
        text = " ".join([s.text for s in transcript_obj])
        if text.strip():
            print(f"  [+] Got transcript via youtube-transcript-api + {browser} cookies")
            return text
    except Exception as e:
        print(f"  [-] youtube-transcript-api with cookies failed: {e}")
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try:
                os.remove(cookie_file)
            except Exception:
                pass

    return None


def get_transcript_from_ytdlp_subtitles(video_id: str) -> str | None:
    """Fallback 2: download VTT subtitles via yt-dlp."""
    print("  [*] Trying yt-dlp subtitles...")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    os.makedirs("downloads", exist_ok=True)
    browser = get_browser_cookies_flag()

    command = [
        sys.executable, "-m", "yt_dlp",
        "--write-auto-subs", "--write-subs",
        "--sub-langs", "en.*",
        "--skip-download", "--sub-format", "vtt",
        "-o", "downloads/%(id)s.%(ext)s",
        video_url,
    ]
    if browser:
        command += ["--cookies-from-browser", browser]
        print(f"  [*] Using {browser} cookies for yt-dlp")

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
    """Run the original local fallback chain (youtube-transcript-api → yt-dlp)."""
    transcript = get_transcript_from_youtube_api(video_id)
    if transcript:
        return transcript
    transcript = get_transcript_from_ytdlp_subtitles(video_id)
    if transcript:
        return transcript
    print("  [-] No transcript available via local fallbacks.")
    return None


# ---------------------------------------------------------------------------
# Content-type detection
# ---------------------------------------------------------------------------

NEWS_KEYWORDS = [
    'bbc', 'cnn', 'news', 'reuters', 'guardian', 'times', 'post', 'daily',
    'breaking', 'latest news', 'report', 'press',
]
TECH_KEYWORDS = [
    'ai', 'machine learning', 'tutorial', 'coding', 'programming', 'developer',
    'software', 'llm', 'gpt', 'python', 'javascript', 'devops', 'cloud',
    'how to', 'how i', 'build', 'deploy', 'install', 'setup', 'configure',
    'automation', 'workflow', 'model', 'open source',
]


def detect_content_type(channel_name: str, video_title: str) -> str:
    combined = (channel_name + " " + video_title).lower()
    news_score = sum(1 for kw in NEWS_KEYWORDS if kw in combined)
    tech_score = sum(1 for kw in TECH_KEYWORDS if kw in combined)
    if news_score > tech_score:
        return 'news'
    if tech_score > 0:
        return 'tech'
    return 'general'


# ---------------------------------------------------------------------------
# Prompt engineering — youtube-digest template
#
# Output format follows the youtube-digest skill (wjgoarxiv/youtube-digest-skill):
#   TL;DR → Key Takeaways → Core Assertions (with timestamps) →
#   Topic Timeline → Notable Quotes → Summary
#
# The content-type-specific prompts (news / tech / general) customise the
# *analysis lens* while keeping the shared digest structure intact.
# ---------------------------------------------------------------------------

DIGEST_RULES = """
STRICT OUTPUT RULES — follow every rule without exception:
- Output ONLY the structured digest below. No preamble, intro, or closing remarks.
- Do NOT use phrases like "The video covers", "In this video", "The author explains". State facts directly.
- Every bullet MUST contain a specific fact, name, number, tool, decision, or argument lifted directly from the transcript. Generic observations are forbidden.
- Use plain markdown. Section headings with ##, bullets with -, quotes with >.
- Timestamps: use the format [M:SS] or [H:MM:SS]. If the transcript has no timestamps, omit the timestamp column from the Topic Timeline and omit timestamps from Core Assertions.
- Keep each bullet to 1–2 lines. Dense over verbose.
"""

DIGEST_TEMPLATE = """
## TL;DR
[1–2 sentence summary of the entire video's core message]

## Key Takeaways
- [3–7 bullets — each a complete, standalone insight with a specific fact or claim]

## Core Assertions & Claims
- [Claim] (at [timestamp if available])
- [Flag any claims that are vague, controversial, or unsubstantiated]

## Topic Timeline
| Timestamp | Topic | Summary |
|-----------|-------|---------|
| [time]    | [topic] | [one-line summary] |

## Notable Quotes
> "[Exact or near-exact quote from the transcript]" — at [timestamp if available]

## Summary
[3–5 paragraph narrative covering the video's arc, arguments, and conclusions]
"""


def build_prompt_news(transcript: str, title: str) -> str:
    return f"""You are an expert news analyst producing a structured digest of a news video.

Video Title: {title}

{DIGEST_RULES}

Produce the digest using EXACTLY this structure:
{DIGEST_TEMPLATE}

Additional guidance for news content:
- In Core Assertions: always name WHO did WHAT, WHERE, WHEN, and the stated impact
- In Key Takeaways: lead with the most consequential fact (numbers, decisions, casualties, policy changes)
- In Notable Quotes: prefer direct quotes from officials, spokespeople, or on-camera sources
- In Summary: follow the journalistic inverted pyramid — most important first

---
Transcript:
{transcript}
"""


def build_prompt_tech(transcript: str, title: str) -> str:
    return f"""You are a senior software engineer producing a structured digest of a technical video.

Video Title: {title}

{DIGEST_RULES}

Produce the digest using EXACTLY this structure:
{DIGEST_TEMPLATE}

Additional guidance for technical content:
- In TL;DR: state the problem solved, the tool/approach used, and the outcome
- In Key Takeaways: include specific tech stack names, versions, commands, or config patterns
- In Core Assertions: flag design decisions and any gotchas or limitations explicitly stated
- In Topic Timeline: map each major step or demo segment with its timestamp
- In Summary: describe the build/demo flow end-to-end so a reader can follow along

---
Transcript:
{transcript}
"""


def build_prompt_general(transcript: str, title: str) -> str:
    return f"""You are a sharp analyst producing a structured digest of a video.

Video Title: {title}

{DIGEST_RULES}

Produce the digest using EXACTLY this structure:
{DIGEST_TEMPLATE}

Additional guidance:
- In Key Takeaways: 4–7 bullets minimum, each anchored to a specific claim or evidence from the transcript
- In Core Assertions: identify the speaker's main argument(s) and any supporting evidence cited
- In Notable Quotes: pick the 1–3 most quotable, memorable, or surprising lines
- In Summary: capture the arc — setup, argument, examples, conclusion

---
Transcript:
{transcript}
"""


def build_prompt(transcript: str, title: str, content_type: str) -> str:
    if content_type == 'news':
        return build_prompt_news(transcript, title)
    if content_type == 'tech':
        return build_prompt_tech(transcript, title)
    return build_prompt_general(transcript, title)


# ---------------------------------------------------------------------------
# Chunked summarization via Ollama
# ---------------------------------------------------------------------------

def call_ollama(prompt: str) -> str | None:
    """Send a single prompt to Ollama and return the response text."""
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
    except requests.exceptions.RequestException as e:
        print(f"  [-] Ollama request failed: {e}")
        return None


def chunk_transcript(transcript: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split transcript into overlapping chunks ending at word boundaries."""
    if len(transcript) <= chunk_size:
        return [transcript]

    overlap = 500
    chunks = []
    start = 0
    while start < len(transcript):
        end = start + chunk_size
        if end < len(transcript):
            boundary = transcript.rfind(' ', start, end)
            if boundary > start:
                end = boundary
        chunk = transcript[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap

    return chunks


def merge_partial_summaries(partials: list[str], title: str) -> str:
    """Merge multiple chunk digest summaries into one coherent final digest."""
    combined = "\n\n---NEXT SECTION---\n\n".join(partials)
    merge_prompt = f"""You are merging partial digests of a single YouTube video into one final, unified digest.

Video Title: {title}

The partial digests below cover different sections of the same video. Consolidate them.

{DIGEST_RULES}

ADDITIONAL MERGE RULES:
- Remove duplicate points that appear in multiple sections
- Preserve ALL unique facts, numbers, names, steps, timestamps, and details — drop nothing specific
- Merge the Topic Timeline tables from all sections into one chronological table
- Combine all Notable Quotes from all sections
- The final digest must use the same structure as the partials and read as one coherent document

Partial digests to merge:
{combined}
"""
    result = call_ollama(merge_prompt)
    return result or combined


def generate_summary(transcript: str, video_title: str, channel_name: str) -> str | None:
    """
    Generate a structured digest from a transcript via Ollama.
    Output format follows the youtube-digest skill template:
    TL;DR → Key Takeaways → Core Assertions → Topic Timeline → Notable Quotes → Summary
    Handles chunking and merging for long transcripts.
    """
    content_type = detect_content_type(channel_name, video_title)
    print(f"  [*] Content type: {content_type}")
    print(f"  [*] Generating digest via Ollama ({OLLAMA_MODEL})...")

    chunks = chunk_transcript(transcript)
    print(f"  [*] Transcript split into {len(chunks)} chunk(s)")

    if len(chunks) == 1:
        return call_ollama(build_prompt(chunks[0], video_title, content_type))

    partials = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  [*] Summarizing chunk {i}/{len(chunks)}...")
        partial = call_ollama(build_prompt(chunk, video_title, content_type))
        if partial:
            partials.append(partial)

    if not partials:
        return None
    if len(partials) == 1:
        return partials[0]

    print(f"  [*] Merging {len(partials)} partial summaries...")
    return merge_partial_summaries(partials, video_title)


# ---------------------------------------------------------------------------
# Output — dual summary save
# ---------------------------------------------------------------------------

def save_summary(
    video_id: str,
    title: str,
    channel_name: str,
    summary_transcriptapi: str | None,
    summary_local: str | None,
    transcript_source_label_api: str,
    transcript_source_label_local: str,
):
    """
    Save both summaries in a single markdown file.
    Each section is clearly labelled with its transcript source.
    """
    safe_channel = re.sub(r'[^\w\-]', '_', channel_name)
    filename = f"{safe_channel}_{video_id}.md"
    filepath = os.path.join(SUMMARIES_DIR, filename)

    generated_at = datetime.datetime.now().strftime('%d %b %Y %I:%M %p')

    lines = [
        f"# {title}",
        "",
        f"**Channel:** {channel_name}",
        f"**Video ID:** {video_id}",
        f"**Video URL:** https://www.youtube.com/watch?v={video_id}",
        f"**Generated At:** {generated_at}",
        "",
        "---",
        "",
    ]

    # ── Version A: TranscriptAPI ──────────────────────────────────────────
    lines += [
        "## 🔵 Version A — TranscriptAPI Digest",
        f"> Transcript source: **{transcript_source_label_api}** · Format: youtube-digest template",
        "",
    ]
    if summary_transcriptapi:
        lines.append(summary_transcriptapi)
    else:
        lines.append("*Digest not available — TranscriptAPI transcript could not be fetched.*")

    lines += [
        "",
        "---",
        "",
    ]

    # ── Version B: Local fallback ─────────────────────────────────────────
    lines += [
        "## 🟢 Version B — Local Fallback Digest",
        f"> Transcript source: **{transcript_source_label_local}** · Format: youtube-digest template",
        "",
    ]
    if summary_local:
        lines.append(summary_local)
    else:
        lines.append("*Digest not available — local transcript could not be fetched.*")

    lines.append("")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    print(f"  [+] Saved dual summary → {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# Channel processing
# ---------------------------------------------------------------------------

def process_channel(channel: dict, state: dict):
    """Monitor a single channel's RSS feed and process any new videos."""
    channel_name = channel.get('name', 'Unknown')
    channel_id = channel.get('channel_id', '')

    print(f"\n[*] Checking channel: {channel_name}")

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(feed_url)

    if hasattr(feed, 'status') and feed.status == 404:
        print(f"  [-] RSS feed not found for channel ID '{channel_id}'.")
        return

    if not feed.entries:
        print(f"  [-] No videos in RSS feed for '{channel_name}'.")
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=24)

    for entry in feed.entries:
        video_id = entry.yt_videoid
        title = entry.title

        try:
            published_dt = datetime.datetime.fromtimestamp(
                time.mktime(entry.published_parsed), datetime.timezone.utc
            )
        except Exception:
            continue

        if published_dt < cutoff:
            print(f"  [-] Skipping '{title}' — published {published_dt.strftime('%Y-%m-%d %H:%M UTC')} (>24h ago)")
            continue

        print(f"\n  [+] New video: {title} (ID: {video_id})")

        if video_id in state['processed_videos']:
            print(f"  [-] Already processed. Skipping.")
            continue

        # ── Fetch transcripts from both sources in parallel ───────────────
        print("\n  ── Transcript Source A: TranscriptAPI ──")
        transcript_api = get_transcript_from_transcriptapi(video_id)
        label_api = "TranscriptAPI (transcriptapi.com)" if transcript_api else "unavailable"

        print("\n  ── Transcript Source B: Local Fallback ──")
        transcript_local = get_transcript_local_fallback(video_id)
        label_local = "youtube-transcript-api / yt-dlp" if transcript_local else "unavailable"

        if not transcript_api and not transcript_local:
            print(f"  [-] No transcript from either source. Skipping '{title}'.")
            continue

        # ── Generate summaries ────────────────────────────────────────────
        summary_api = None
        if transcript_api:
            print("\n  ── Generating Summary A (TranscriptAPI transcript) ──")
            summary_api = generate_summary(transcript_api, title, channel_name)
        else:
            print("  [!] Skipping Summary A — no TranscriptAPI transcript.")

        summary_local = None
        if transcript_local:
            print("\n  ── Generating Summary B (Local fallback transcript) ──")
            summary_local = generate_summary(transcript_local, title, channel_name)
        else:
            print("  [!] Skipping Summary B — no local transcript.")

        # ── Save both summaries ───────────────────────────────────────────
        filepath = save_summary(
            video_id, title, channel_name,
            summary_api, summary_local,
            label_api, label_local,
        )

        # ── Print to console ──────────────────────────────────────────────
        print("\n" + "=" * 70)
        print(f"  SUMMARIES — {title}")
        print("=" * 70)

        print("\n🔵 Version A — TranscriptAPI:")
        print(summary_api or "  (not available)")

        print("\n🟢 Version B — Local Fallback:")
        print(summary_local or "  (not available)")

        print("=" * 70 + "\n")

        state['processed_videos'][video_id] = {
            "title": title,
            "channel": channel_name,
            "processed_at": datetime.datetime.now().isoformat(),
            "summary_file": filepath,
            "transcript_sources": {
                "api": label_api,
                "local": label_local,
            },
        }


# ---------------------------------------------------------------------------
# Startup checks
# ---------------------------------------------------------------------------

def check_ollama() -> bool:
    """Verify Ollama is reachable and the configured model is available."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m['name'] for m in resp.json().get('models', [])]
        if not any(OLLAMA_MODEL.split(':')[0] in m for m in models):
            print(f"  [!] Model '{OLLAMA_MODEL}' not found. Available: {models or 'none'}")
            print(f"  [!] Run: ollama pull {OLLAMA_MODEL}")
            return False
        print(f"  [+] Ollama running. Model '{OLLAMA_MODEL}' available.")
        return True
    except requests.exceptions.ConnectionError:
        print("  [-] Cannot connect to Ollama at http://localhost:11434")
        print("  [-] Start Ollama: open the app or run `ollama serve`")
        return False
    except Exception as e:
        print(f"  [-] Ollama health check failed: {e}")
        return False


def check_transcriptapi() -> bool:
    """Quick sanity check that the TranscriptAPI key is configured."""
    if not TRANSCRIPTAPI_KEY:
        print("  [!] TRANSCRIPTAPI_KEY not set in .env — Version A summaries will be skipped.")
        return False
    print(f"  [+] TranscriptAPI key loaded (sk_...{TRANSCRIPTAPI_KEY[-6:]})")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  YouTube Channel Summarizer — Dual Summary Mode")
    print("=" * 70)
    print()
    print("  Version A: TranscriptAPI (transcriptapi.com) → Ollama")
    print("  Version B: youtube-transcript-api / yt-dlp  → Ollama")
    print()

    check_transcriptapi()

    if not check_ollama():
        print("\n[!] Aborting — Ollama must be running to generate summaries.")
        return

    channels_data = load_json(CHANNELS_FILE, {"channels": []})
    state = load_json(STATE_FILE, {"processed_videos": {}})

    channels = channels_data.get('channels', [])
    if not channels:
        print("[-] No channels in channels.json. Add some and re-run.")
        return

    for channel in channels:
        process_channel(channel, state)

    save_json(STATE_FILE, state)
    print("\n[+] Done. All channels processed.")


if __name__ == "__main__":
    main()
