from __future__ import annotations
import os
import sys
import re
import json
from typing import Optional
import datetime
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
import requests

# Add root project path to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.database import init_db, get_db, Channel, Video, SessionLocal
    from backend.pipeline import process_all_channels, OLLAMA_API_URL, OLLAMA_MODEL
except ModuleNotFoundError:
    from database import init_db, get_db, Channel, Video, SessionLocal
    from pipeline import process_all_channels, OLLAMA_API_URL, OLLAMA_MODEL

app = FastAPI(
    title="YouTube Summarizer & InShorts API",
    description="Backend API serving byte-sized video summaries for Android and iOS mobile app.",
    version="1.0.0",
)

# CORS setup with configurable origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Scheduler for daily background feed processing
scheduler = BackgroundScheduler()

def load_schedule_settings():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_settings.json")
    if not os.path.exists(path):
        default = {"enabled": True, "hour": 8, "minute": 0}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                raise ValueError("Empty file")
            return json.loads(content)
    except Exception:
        default = {"enabled": True, "hour": 8, "minute": 0}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f)
        return default

def save_schedule_settings(settings):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f)

def update_active_scheduler_job():
    settings = load_schedule_settings()
    
    # Remove existing job if it exists
    if scheduler.get_job("daily_rss_check"):
        scheduler.remove_job("daily_rss_check")
        
    if settings.get("enabled", True):
        scheduler.add_job(
            process_all_channels,
            "cron",
            hour=settings.get("hour", 8),
            minute=settings.get("minute", 0),
            id="daily_rss_check",
            replace_existing=True
        )

@app.on_event("startup")
def on_startup():
    init_db()
    scheduler.start()
    update_active_scheduler_job()

@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ChannelCreate(BaseModel):
    channel_id: str
    name: str

class ChannelResponse(BaseModel):
    id: int
    channel_id: str
    name: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class VideoFeedResponse(BaseModel):
    id: int
    video_id: str
    channel_id: str
    channel_name: str
    title: str
    published_at: datetime.datetime
    thumbnail_url: str
    short_summary: str
    content_type: str
    is_bookmarked: bool
    label_api: Optional[str] = None
    label_local: Optional[str] = None

    class Config:
        from_attributes = True

class VideoDetailResponse(VideoFeedResponse):
    summary_api: Optional[str] = None
    summary_local: Optional[str] = None
    summary_file: Optional[str] = None

class ScheduleSettings(BaseModel):
    enabled: bool
    hour: int
    minute: int


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def check_health():
    ollama_status = False
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            ollama_status = True
    except Exception:
        ollama_status = False

    return {
        "status": "online",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "ollama_connected": ollama_status,
        "ollama_model": OLLAMA_MODEL,
    }

@app.get("/api/schedule", response_model=ScheduleSettings)
def get_schedule():
    return load_schedule_settings()

@app.post("/api/schedule", response_model=ScheduleSettings)
def post_schedule(settings: ScheduleSettings):
    data = settings.model_dump() if hasattr(settings, "model_dump") else settings.dict()
    save_schedule_settings(data)
    update_active_scheduler_job()
    return settings


@app.get("/api/videos", response_model=list[VideoFeedResponse])
def get_videos(
    channel_id: Optional[str] = None,
    category: Optional[str] = None,
    bookmarked_only: bool = False,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Video)

    if channel_id:
        query = query.filter(Video.channel_id == channel_id)
    if category and category.lower() != 'all':
        query = query.filter(Video.content_type == category.lower())
    if bookmarked_only:
        query = query.filter(Video.is_bookmarked == True)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Video.title.ilike(search_pattern)) | 
            (Video.short_summary.ilike(search_pattern)) | 
            (Video.channel_name.ilike(search_pattern))
        )

    videos = query.order_by(Video.published_at.desc()).all()
    return videos


@app.get("/api/videos/{video_id}", response_model=VideoDetailResponse)
def get_video_detail(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@app.post("/api/videos/{video_id}/bookmark")
def toggle_bookmark(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video.is_bookmarked = not video.is_bookmarked
    db.commit()
    return {"video_id": video_id, "is_bookmarked": video.is_bookmarked}


@app.get("/api/channels", response_model=list[ChannelResponse])
def get_channels(db: Session = Depends(get_db)):
    return db.query(Channel).order_by(Channel.name.asc()).all()


def resolve_channel_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    
    # 1. Check if it's already a valid channel ID
    if re.match(r"^UC[a-zA-Z0-9_-]{22}$", input_str):
        return input_str
        
    # 2. Extract handle or construct URL
    url = None
    if input_str.startswith("http://") or input_str.startswith("https://"):
        url = input_str
    elif input_str.startswith("@"):
        url = f"https://www.youtube.com/{input_str}"
    else:
        url = f"https://www.youtube.com/@{input_str}"
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
            
        html = resp.text
        
        # Method 1: Look for RSS feed link
        match = re.search(r"youtube\.com/feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_-]{22})", html)
        if match:
            return match.group(1)
            
        # Method 2: Look for itemprop="channelId"
        match = re.search(r'itemprop="channelId"\s+content="(UC[a-zA-Z0-9_-]{22})"', html)
        if match:
            return match.group(1)
            
        # Method 3: Look for link rel="alternate"
        match = re.search(r'href="https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})"', html)
        if match:
            return match.group(1)
            
    except Exception:
        pass
        
    return None


@app.post("/api/channels", response_model=ChannelResponse)
def add_channel(channel: ChannelCreate, db: Session = Depends(get_db)):
    resolved_id = resolve_channel_id(channel.channel_id)
    if not resolved_id:
        raise HTTPException(
            status_code=400,
            detail="Could not resolve the channel handle or URL to a valid YouTube Channel ID."
        )

    existing = db.query(Channel).filter(Channel.channel_id == resolved_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel already exists")

    new_ch = Channel(channel_id=resolved_id, name=channel.name.strip())
    db.add(new_ch)
    db.commit()
    db.refresh(new_ch)
    return new_ch


@app.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: str, db: Session = Depends(get_db)):
    ch = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.delete(ch)
    db.commit()
    return {"status": "deleted", "channel_id": channel_id}


@app.post("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        import backend.pipeline as pipeline
    except ModuleNotFoundError:
        import pipeline

    if getattr(pipeline, "IS_SYNCING", False):
        return {"status": "already_syncing", "message": "Feed sync & summary pipeline is already running."}

    background_tasks.add_task(process_all_channels)
    return {"status": "sync_started", "message": "Background feed sync & summary pipeline initiated."}


@app.get("/api/sync/status")
def get_sync_status():
    try:
        import backend.pipeline as pipeline
    except ModuleNotFoundError:
        import pipeline
    return {"is_syncing": getattr(pipeline, "IS_SYNCING", False)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
