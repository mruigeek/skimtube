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
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from backend.database import Video, Channel, SessionLocal

# Load environment variables
load_dotenv()

SUMMARIES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'summaries')
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434/api/generate')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:4b')

TRANSCRIPTAPI_BASE = 'https://transcriptapi.com/api/v2'
TRANSCRIPTAPI_KEY = os.getenv('TRANSCRIPTAPI_KEY', '')

os.makedirs(SUMMARIES_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Transcript Fetching & Cleaning
# ---------------------------------------------------------------------------

def get_transcript_from_transcriptapi(video_id: str) -> str | None:
    if not TRANSCRIPTAPI_KEY:
        return None

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
                    return text.strip()
                return None

            if resp.status_code in retryable:
                time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))
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
    """Fetch transcript using youtube-transcript-api, iterating across all available languages."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        
        # 1. Try iterating list of available transcripts (manual & auto-generated)
        try:
            tl = api.list(video_id)
            for t in tl:
                fetched = t.fetch()
                text = " ".join([item.text if hasattr(item, 'text') else item.get('text', '') for item in fetched])
                if text.strip():
                    return text.strip()
        except Exception:
            pass

        # 2. Direct fetch with explicit fallback language codes
        try:
            transcript_obj = api.fetch(video_id, languages=['en', 'ta', 'hi', 'te', 'es', 'fr', 'de', 'auto'])
            text = " ".join([item.text if hasattr(item, 'text') else item.get('text', '') for item in transcript_obj])
            if text.strip():
                return text.strip()
        except Exception:
            pass
            
    except Exception as e:
        print(f"  [-] youtube_transcript_api exception for {video_id}: {e}")
    return None


def get_transcript_from_ytdlp_subtitles(video_id: str) -> str | None:
    downloads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    command = [
        sys.executable, "-m", "yt_dlp",
        "--write-auto-subs", "--write-subs",
        "--sub-langs", "all,-live_chat",
        "--skip-download", "--sub-format", "vtt",
        "-o", f"{downloads_dir}/%(id)s.%(ext)s",
        video_url,
    ]

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        pass

    vtt_files = glob.glob(f"{downloads_dir}/{video_id}*.vtt")
    if not vtt_files:
        return None

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
# Content Type Detection & Smart Sampling Prompts
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
    """Sample transcript across start, middle, and end if it exceeds max_chars."""
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


def generate_short_inshorts_summary(transcript: str, video_title: str, channel_name: str) -> str:
    """Generate a crisp ~100 word InShorts-style paragraph for mobile card UI."""
    sampled_transcript = prepare_transcript_for_llm(transcript, max_chars=12000)
    prompt = f"""You are an expert news editor producing a byte-sized InShorts style summary for a mobile card app.
If the transcript is in a non-English language, translate and write the summary in clear English.

Video Title: {video_title}
Channel: {channel_name}

INSHORTS SUMMARY RULES:
1. Write EXACTLY ONE clean paragraph between 80 and 130 words long in English.
2. Lead immediately with the primary headline/hook in the first sentence.
3. Follow with 3 to 5 key concrete facts, figures, tools, decisions, or quotes directly from the transcript.
4. Do NOT use filler words like "The video discusses", "In this video", "The speaker explains". State facts directly.
5. End with a strong concluding sentence summarizing the overall takeaway.

Transcript:
{sampled_transcript}
"""
    result = call_ollama(prompt)
    if result:
        clean_result = re.sub(r'#+\s*', '', result).strip()
        return clean_result
    
    return f"{video_title}. High-density summary generated from channel {channel_name}."


def generate_full_digest(transcript: str, video_title: str, channel_name: str) -> str | None:
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


# ---------------------------------------------------------------------------
# Channel Processing & Cleanup
# ---------------------------------------------------------------------------

def cleanup_old_summaries(db: Session, max_hours: int = 24):
    """Purge video records and summary markdown files older than max_hours."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=max_hours)
        
        old_videos = db.query(Video).filter(Video.published_at < cutoff.replace(tzinfo=None)).all()
        purged_count = 0
        for v in old_videos:
            if v.summary_file and os.path.exists(v.summary_file):
                try:
                    os.remove(v.summary_file)
                except Exception:
                    pass
            db.delete(v)
            purged_count += 1
        db.commit()
        if purged_count > 0:
            print(f"[*] Cleanup: Purged {purged_count} videos older than {max_hours}h.")
    except Exception as e:
        print(f"[-] Cleanup error: {e}")


def process_all_channels(db: Session = None):
    """Fetch RSS feeds for all channels in DB and process new videos published in last 24h."""
    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    try:
        # Purge files & DB entries older than 24h to keep feed strictly last 24h
        cleanup_old_summaries(db, max_hours=24)

        channels = db.query(Channel).all()
        if not channels:
            print("[*] Pipeline: No channels configured in database.")
            return {"processed": 0, "status": "no channels"}

        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=24) # Strictly last 24h filter
        processed_count = 0

        for ch in channels:
            print(f"[*] Pipeline checking: {ch.name} ({ch.channel_id})")
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch.channel_id}"
            feed = feedparser.parse(feed_url)

            if not hasattr(feed, 'entries') or not feed.entries:
                continue

            for entry in feed.entries:
                video_id = getattr(entry, 'yt_videoid', '')
                if not video_id:
                    continue

                # Check if already processed
                existing = db.query(Video).filter(Video.video_id == video_id).first()
                if existing:
                    continue

                title = entry.title
                published_parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
                if published_parsed:
                    published_dt = datetime.datetime.fromtimestamp(
                        time.mktime(published_parsed), datetime.timezone.utc
                    )
                else:
                    print(f"[-] Skipping {title}: Could not parse publication date.")
                    continue

                # STRICT 24-HOUR FILTER
                if published_dt < cutoff:
                    continue

                print(f"[+] Processing new 24h video: {title} ({video_id})")

                # Transcripts
                transcript_api = get_transcript_from_transcriptapi(video_id)
                transcript_local = get_transcript_local_fallback(video_id)

                if not transcript_api and not transcript_local:
                    print(f"[-] Skipping {video_id}: No transcript available.")
                    continue

                main_transcript = transcript_api or transcript_local
                content_type = detect_content_type(ch.name, title)

                # Generate InShorts short summary (~100 words)
                short_summary = generate_short_inshorts_summary(main_transcript, title, ch.name)

                # Generate Full digests
                summary_api = generate_full_digest(transcript_api, title, ch.name) if transcript_api else None
                summary_local = generate_full_digest(transcript_local, title, ch.name) if transcript_local else None

                # Save markdown file
                safe_channel = re.sub(r'[^\w\-]', '_', ch.name)
                filepath = os.path.join(SUMMARIES_DIR, f"{safe_channel}_{video_id}.md")
                thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

                # Write dual markdown output
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# {title}\n\n")
                    f.write(f"**Channel:** {ch.name} | **Video ID:** {video_id}\n")
                    f.write(f"**Thumbnail:** {thumbnail_url}\n\n")
                    f.write(f"## InShorts Short Summary\n{short_summary}\n\n---\n\n")
                    f.write("## 🔵 Version A — TranscriptAPI Digest\n")
                    f.write((summary_api or "*Not available*") + "\n\n---\n\n")
                    f.write("## 🟢 Version B — Local Fallback Digest\n")
                    f.write((summary_local or "*Not available*") + "\n")

                # Insert video record into DB
                video_record = Video(
                    video_id=video_id,
                    channel_id=ch.channel_id,
                    channel_name=ch.name,
                    title=title,
                    published_at=published_dt.replace(tzinfo=None),
                    thumbnail_url=thumbnail_url,
                    short_summary=short_summary,
                    summary_file=filepath,
                    summary_api=summary_api,
                    summary_local=summary_local,
                    label_api="TranscriptAPI (transcriptapi.com)" if transcript_api else "Unavailable",
                    label_local="youtube-transcript-api / yt-dlp" if transcript_local else "Unavailable",
                    content_type=content_type,
                    processed_at=datetime.datetime.utcnow()
                )
                db.add(video_record)
                db.commit()
                processed_count += 1

        return {"processed": processed_count, "status": "success"}
    finally:
        if close_db_on_exit:
            db.close()
