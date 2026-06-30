# AGENT.md — YouTube Summarizer Project Context

## Project Overview

A local-first Python script that monitors YouTube channels for new videos (last 24h), fetches their transcripts, and generates high-quality structured summaries using a local Ollama LLM (Gemma 3 4B).

## Architecture

```
channels.json       → list of channels to monitor (name + channel_id)
state.json          → deduplication log of processed video IDs
main.py             → single-file orchestration script
summaries/          → output .md files, one per video
downloads/          → temp folder for yt-dlp subtitle files (auto-cleaned)
```

## Data Flow

1. Load `channels.json` → iterate each channel
2. Fetch YouTube RSS feed (`feedparser`) → filter videos published in last 24h
3. Skip already-processed video IDs (checked against `state.json`)
4. Fetch transcript via two fallback methods:
   - Primary: `youtube-transcript-api`
   - Fallback: `yt-dlp` subtitle download → VTT → plain text
5. Send transcript + video title to local Ollama API → get summary
6. Save summary as `.md` in `summaries/` and print to terminal
7. Mark video ID as processed in `state.json`

## Known Issues (Pre-Fix State)

- **Vague summaries**: The LLM prompt was too generic — summaries read as paraphrased titles rather than distilled content
- **Hard truncation**: Transcripts >30k chars were cut off, losing content from the second half of the video
- **No structure enforcement**: The output format was loosely defined, causing the model to drift into filler text despite CRITICAL RULES
- **No density check**: Short transcripts and long transcripts were treated identically — no adaptive prompt
- **Channel-agnostic prompting**: A BBC news video and a tech/AI tutorial need different summarization styles

## Target Quality Bar

Summaries should feel like notes from an expert who watched the video, not a bot that skimmed the title. Specifically:

- Every bullet point must carry a concrete fact, name, number, or actionable idea from the actual transcript
- Zero filler: no "the video covers", "as mentioned", "in conclusion" style fluff
- Structure: short TL;DR → key points (rich bullets) → technical/actionable takeaways
- If the video is news: WHO / WHAT / WHERE / WHEN / WHY format
- If the video is tutorial/tech: steps, tools, commands, decisions explained
- If the video is opinion/analysis: the actual argument chain, not a restatement of the topic

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Full pipeline logic |
| `channels.json` | Channel registry |
| `state.json` | Processed video deduplication |
| `requirements.txt` | Python deps (feedparser, requests, youtube-transcript-api, yt-dlp) |

## Environment

- Python 3.8+
- Ollama running locally at `http://localhost:11434`
- Model: `gemma3:4b` (can be swapped via `OLLAMA_MODEL` constant)
- No external API keys required

## Improvement Goals (This Session)

1. **Redesign the summarization prompt** to force concrete, specific extraction from transcript text
2. **Fix transcript handling** — replace hard truncation with smarter chunking that preserves coverage across the full video
3. **Add channel-type awareness** — detect content type (news vs tech/AI vs general) and adapt the prompt accordingly
4. **Enforce strict output schema** in the prompt so the model cannot produce generic output
5. **Improve transcript cleaning** — ensure VTT deduplication is robust and produces coherent readable text before it hits the LLM
