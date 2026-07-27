import os
import json
import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "summarizer.db")
ENGINE = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

Base = declarative_base()


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    videos = relationship("Video", back_populates="channel_obj", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True, nullable=False)
    channel_id = Column(String, ForeignKey("channels.channel_id"), nullable=False)
    channel_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    thumbnail_url = Column(String, nullable=False)
    short_summary = Column(Text, nullable=False)
    summary_file = Column(String, nullable=True)
    summary_api = Column(Text, nullable=True)
    summary_local = Column(Text, nullable=True)
    label_api = Column(String, nullable=True)
    label_local = Column(String, nullable=True)
    content_type = Column(String, default="general")
    is_bookmarked = Column(Boolean, default=False)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)

    channel_obj = relationship("Channel", back_populates="videos")


def init_db():
    Base.metadata.create_all(bind=ENGINE)
    seed_from_existing_json()


def seed_from_existing_json():
    """Migrate channels.json into SQLite if database is fresh."""
    db = SessionLocal()
    try:
        channels_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "channels.json")
        if os.path.exists(channels_file):
            with open(channels_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                channels = data.get("channels", [])
                for ch in channels:
                    cid = ch.get("channel_id")
                    cname = ch.get("name", "Unknown")
                    if cid and not db.query(Channel).filter(Channel.channel_id == cid).first():
                        db.add(Channel(channel_id=cid, name=cname))
                db.commit()
    except Exception as e:
        print(f"[!] Warning: Seeding channels failed: {e}")
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
