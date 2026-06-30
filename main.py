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
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

# Configuration
CHANNELS_FILE = 'channels.json'
STATE_FILE = 'state.json'
SUMMARIES_DIR = 'summaries'
OLLAMA_API_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'gemma3:4b'  # Ensure this model is pulled in your Ollama instance

# Max characters sent to the LLM per chunk. Gemma 3 4B handles ~6k tokens safely.
# ~4 chars per token → 24k chars is a safe ceiling that avoids context overflow.
CHUNK_SIZE = 24000

# Create summaries directory if it doesn't exist
os.makedirs(SUMMARIES_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def load_json(filepath, default_content):
    """Load a JSON file or return default_content if it doesn't exist."""
    if not os.path.exists(filepath):
        return default_content
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath, data):
    """Save data to a JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


# ---------------------------------------------------------------------------
# Transcript fetching
# ---------------------------------------------------------------------------

def clean_vtt_text(vtt_content):
    """
    Parse a VTT subtitle file into clean, deduplicated plain text.
    Auto-generated subtitles typically duplicate lines; we strip those out
    so the LLM receives coherent prose rather than repeated fragments.
    """
    text_lines = []
    for line in vtt_content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip VTT structural lines
        if (stripped.startswith('WEBVTT') or stripped.startswith('Kind:') or
                stripped.startswith('Language:') or stripped.startswith('Style:') or
                '-->' in stripped or stripped.isdigit()):
            continue
        # Remove inline tags: <c>, <i>, timestamps like <00:00:01.000>
        clean_line = re.sub(r'<[^>]+>', '', stripped).strip()
        if not clean_line:
            continue
        # Deduplicate: skip if identical to previous line (auto-sub artifact)
        if text_lines and text_lines[-1] == clean_line:
            continue
        text_lines.append(clean_line)

    # Join into sentences — insert a space unless the previous line ends with punctuation
    result = []
    for line in text_lines:
        if result and not result[-1].endswith(('.', '?', '!', ',')):
            result.append(' ')
        result.append(line)
    return ''.join(result)


def get_transcript_from_youtube_api(video_id):
    """Primary method: use youtube-transcript-api."""
    try:
        print("  [*] Trying youtube-transcript-api...")
        api = YouTubeTranscriptApi()
        transcript_obj = api.fetch(video_id)
        text = " ".join([snippet.text for snippet in transcript_obj])
        if text.strip():
            return text
        return None
    except Exception as e:
        print(f"  [-] youtube-transcript-api failed: {e}")
        return None


def get_transcript_from_ytdlp_subtitles(video_id):
    """Fallback method: download VTT subtitles via yt-dlp."""
    print("  [*] Trying yt-dlp subtitles...")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    os.makedirs("downloads", exist_ok=True)

    command = [
        sys.executable, "-m", "yt_dlp",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs", "en.*",
        "--skip-download",
        "--sub-format", "vtt",
        "-o", "downloads/%(id)s.%(ext)s",
        video_url,
    ]

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        pass  # Normal when no subs exist

    vtt_files = glob.glob(f"downloads/{video_id}*.vtt")
    if not vtt_files:
        print("  [-] No subtitles found via yt-dlp")
        return None

    print("  [+] Found subtitles via yt-dlp")
    with open(vtt_files[0], 'r', encoding='utf-8') as f:
        vtt_content = f.read()

    # Clean up downloaded temp files
    for vf in vtt_files:
        try:
            os.remove(vf)
        except Exception:
            pass

    return clean_vtt_text(vtt_content)


def get_transcript(video_id):
    """Try all transcript sources in order; return the first successful result."""
    transcript = get_transcript_from_youtube_api(video_id)
    if transcript:
        return transcript

    transcript = get_transcript_from_ytdlp_subtitles(video_id)
    if transcript:
        return transcript

    print("  [-] No transcript available for this video.")
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
    """
    Heuristically determine if a video is 'news', 'tech', or 'general'.
    This drives prompt selection so the LLM is guided differently per content type.
    """
    combined = (channel_name + " " + video_title).lower()
    news_score = sum(1 for kw in NEWS_KEYWORDS if kw in combined)
    tech_score = sum(1 for kw in TECH_KEYWORDS if kw in combined)

    if news_score > tech_score:
        return 'news'
    if tech_score > 0:
        return 'tech'
    return 'general'


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

SHARED_RULES = """
STRICT OUTPUT RULES — follow every rule without exception:
- Output ONLY the structured summary. Do NOT write any preamble, intro sentence, or closing remark.
- Do NOT use phrases like "The video covers", "In this video", "The author explains", "As mentioned", "In conclusion", or any variant. State facts directly.
- Every bullet point MUST contain a specific fact, name, number, tool, decision, or argument lifted directly from the transcript. Generic observations are forbidden.
- Use plain markdown. Headings with ##, bullet lists with -.
- Keep each bullet to 1–2 lines max. Dense over verbose.
"""

def build_prompt_news(transcript: str, title: str) -> str:
    return f"""You are an expert news analyst. Extract only concrete facts from the transcript below.

Video Title: {title}

{SHARED_RULES}

## Required output format (use exactly these sections):

## TL;DR
One sentence: who did what, where, when, and why it matters.

## Key Facts
- [WHO] The main people, organisations, or governments involved — use their actual names
- [WHAT] The specific event, decision, or development — exact numbers, dates, or quotes if present
- [WHERE] Location(s) with context
- [WHEN] Timeline or sequence of events
- [WHY / IMPACT] Stated consequences, reactions, or significance

## Context & Background
- Any historical or political background mentioned in the transcript
- Related developments referenced

## Notable Quotes or Statements
- Direct quotes or paraphrased positions of key figures (only if present in transcript)

---
Transcript:
{transcript}
"""


def build_prompt_tech(transcript: str, title: str) -> str:
    return f"""You are a senior software engineer and technical writer. Distil the transcript below into sharp, useful notes.

Video Title: {title}

{SHARED_RULES}

## Required output format (use exactly these sections):

## TL;DR
One sentence: what problem is solved, what tool/approach is used, and what outcome is achieved.

## Core Concept / What Was Built
- The specific problem, goal, or idea being addressed
- The technology stack, model, API, or framework used (exact names and versions if mentioned)

## Step-by-Step Breakdown
- Each meaningful step, decision, or configuration in order
- Include commands, parameters, or code patterns mentioned (even partial ones are valuable)
- Flag any gotchas, errors, or workarounds discussed

## Key Insights & Design Decisions
- Why specific choices were made over alternatives (if discussed)
- Performance notes, limitations, or tradeoffs mentioned

## Actionable Takeaways
- What the viewer can immediately do or apply
- Links, tools, repos, or resources mentioned

---
Transcript:
{transcript}
"""


def build_prompt_general(transcript: str, title: str) -> str:
    return f"""You are a sharp analyst. Extract the core value from this transcript.

Video Title: {title}

{SHARED_RULES}

## Required output format (use exactly these sections):

## TL;DR
One sentence capturing the central argument, insight, or story.

## Main Points
- Each major idea, argument, or narrative beat — stated as a concrete claim, not a topic label
- Include specific examples, numbers, names, or evidence cited in the transcript
- Minimum 4 bullets, maximum 10

## Supporting Details
- Notable examples, anecdotes, or data points that back the main points
- Any contrarian takes or counterarguments addressed

## Takeaways
- The most useful, surprising, or actionable things from this video

---
Transcript:
{transcript}
"""


def build_prompt(transcript: str, title: str, content_type: str) -> str:
    """Select and build the right prompt for the detected content type."""
    if content_type == 'news':
        return build_prompt_news(transcript, title)
    if content_type == 'tech':
        return build_prompt_tech(transcript, title)
    return build_prompt_general(transcript, title)


# ---------------------------------------------------------------------------
# Chunked summarization
# ---------------------------------------------------------------------------

def call_ollama(prompt: str) -> str | None:
    """Send a single prompt to Ollama and return the response text."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,   # Low temperature → factual, less hallucination
            "top_p": 0.9,
        },
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
        response.raise_for_status()
        return response.json().get('response', '').strip()
    except requests.exceptions.RequestException as e:
        print(f"  [-] Ollama request failed: {e}")
        return None


def chunk_transcript(transcript: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """
    Split transcript into overlapping chunks that each end at a word boundary.
    Overlap of ~500 chars prevents cutting mid-thought at chunk edges.
    """
    if len(transcript) <= chunk_size:
        return [transcript]

    overlap = 500
    chunks = []
    start = 0
    while start < len(transcript):
        end = start + chunk_size
        if end < len(transcript):
            # Walk back to nearest word boundary
            boundary = transcript.rfind(' ', start, end)
            if boundary > start:
                end = boundary
        chunk = transcript[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap  # back up by overlap for continuity

    return chunks


def merge_partial_summaries(partials: list[str], title: str) -> str:
    """
    Merge multiple chunk summaries into a single coherent final summary.
    Uses a dedicated merge prompt so the LLM consolidates rather than re-summarizes.
    """
    combined = "\n\n---NEXT SECTION---\n\n".join(partials)
    merge_prompt = f"""You are merging partial summaries of a single YouTube video into one final, unified summary.

Video Title: {title}

The partial summaries below cover different sections of the same video. Consolidate them into a single summary.

{SHARED_RULES}

ADDITIONAL MERGE RULES:
- Remove duplicate points that appear in multiple sections
- Preserve ALL unique facts, numbers, names, steps, and details — do not drop anything specific
- Keep the same output structure as the partials (TL;DR, key sections, takeaways)
- The final summary must read as a single coherent document, not a list of sections

Partial summaries to merge:
{combined}
"""
    result = call_ollama(merge_prompt)
    return result or combined  # Fallback: return joined partials if merge fails


def generate_summary(transcript: str, video_title: str, channel_name: str) -> str | None:
    """
    Main summarization entry point.
    - Detects content type for prompt selection
    - Splits long transcripts into chunks
    - Merges chunk summaries if needed
    """
    content_type = detect_content_type(channel_name, video_title)
    print(f"  [*] Content type detected: {content_type}")
    print(f"  [*] Generating summary for '{video_title}' using Ollama ({OLLAMA_MODEL})...")

    chunks = chunk_transcript(transcript)
    print(f"  [*] Transcript split into {len(chunks)} chunk(s)")

    if len(chunks) == 1:
        prompt = build_prompt(chunks[0], video_title, content_type)
        return call_ollama(prompt)

    # Multiple chunks: summarize each, then merge
    partials = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  [*] Summarizing chunk {i}/{len(chunks)}...")
        prompt = build_prompt(chunk, video_title, content_type)
        partial = call_ollama(prompt)
        if partial:
            partials.append(partial)

    if not partials:
        return None

    if len(partials) == 1:
        return partials[0]

    print(f"  [*] Merging {len(partials)} partial summaries...")
    return merge_partial_summaries(partials, video_title)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_summary(video_id: str, title: str, channel_name: str, summary: str):
    """Save the markdown summary to the summaries directory."""
    safe_channel = re.sub(r'[^\w\-]', '_', channel_name)
    filename = f"{safe_channel}_{video_id}.md"
    filepath = os.path.join(SUMMARIES_DIR, filename)

    generated_at = datetime.datetime.now().strftime('%d %b %Y %I:%M %p')
    content = (
        f"# {title}\n\n"
        f"**Channel:** {channel_name}\n"
        f"**Video ID:** {video_id}\n"
        f"**Video URL:** https://www.youtube.com/watch?v={video_id}\n"
        f"**Generated At:** {generated_at}\n\n"
        "---\n\n"
        f"{summary}\n"
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  [+] Saved summary → {filepath}")


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
        print(f"  [-] RSS feed not found for channel ID '{channel_id}'. Check the ID in channels.json.")
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

        print(f"  [+] New video: {title} (ID: {video_id})")

        if video_id in state['processed_videos']:
            print(f"  [-] Already processed. Skipping.")
            continue

        transcript = get_transcript(video_id)
        if not transcript:
            print(f"  [-] No transcript available. Skipping.")
            continue

        summary = generate_summary(transcript, title, channel_name)
        if not summary:
            print(f"  [-] Summary generation failed for {video_id}.")
            continue

        save_summary(video_id, title, channel_name, summary)

        print("\n" + "=" * 60)
        print(f"  SUMMARY — {title}")
        print("=" * 60)
        print(summary)
        print("=" * 60 + "\n")

        state['processed_videos'][video_id] = {
            "title": title,
            "channel": channel_name,
            "processed_at": datetime.datetime.now().isoformat(),
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  YouTube Channel Summarizer")
    print("=" * 60)

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
