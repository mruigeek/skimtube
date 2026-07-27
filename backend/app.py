import os
import sys
import datetime
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
import requests

# Add root project path to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, get_db, Channel, Video, SessionLocal
from backend.pipeline import process_all_channels, OLLAMA_API_URL, OLLAMA_MODEL

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

@app.on_event("startup")
def on_startup():
    init_db()
    # Schedule daily check at midnight or every 6 hours
    scheduler.add_job(process_all_channels, "interval", hours=6, id="daily_rss_check", replace_existing=True)
    scheduler.start()

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
    label_api: str | None = None
    label_local: str | None = None

    class Config:
        from_attributes = True

class VideoDetailResponse(VideoFeedResponse):
    summary_api: str | None = None
    summary_local: str | None = None
    summary_file: str | None = None


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


@app.get("/api/videos", response_model=list[VideoFeedResponse])
def get_videos(
    channel_id: str | None = None,
    category: str | None = None,
    bookmarked_only: bool = False,
    search: str | None = None,
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


@app.post("/api/channels", response_model=ChannelResponse)
def add_channel(channel: ChannelCreate, db: Session = Depends(get_db)):
    existing = db.query(Channel).filter(Channel.channel_id == channel.channel_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel already exists")

    new_ch = Channel(channel_id=channel.channel_id.strip(), name=channel.name.strip())
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
    background_tasks.add_task(process_all_channels)
    return {"status": "sync_started", "message": "Background feed sync & summary pipeline initiated."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
