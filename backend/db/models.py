from datetime import datetime



from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func

from sqlalchemy.orm import Mapped, mapped_column



from db.database import Base





class Song(Base):

    __tablename__ = "songs"



    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    yt_video_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    title: Mapped[str] = mapped_column(String(512))

    artist: Mapped[str] = mapped_column(String(512), default="")

    language: Mapped[str] = mapped_column(String(16), default="en")

    play_count: Mapped[int] = mapped_column(Integer, default=0)

    last_played_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_status: Mapped[str] = mapped_column(String(32), default="imported")

    last_synced_at: Mapped[datetime] = mapped_column(

        DateTime, server_default=func.now(), onupdate=func.now()

    )

    plain_lyrics: Mapped[str | None] = mapped_column(Text, nullable=True)

    synced_lyrics: Mapped[str | None] = mapped_column(Text, nullable=True)

    chordpro_full: Mapped[str | None] = mapped_column(Text, nullable=True)

    chordpro_easy: Mapped[str | None] = mapped_column(Text, nullable=True)

    easy_note_he: Mapped[str | None] = mapped_column(String(512), nullable=True)

    easy_note_en: Mapped[str | None] = mapped_column(String(512), nullable=True)

    enrich_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    chord_source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    enrich_attempts: Mapped[int] = mapped_column(Integer, default=0)

    enrich_history: Mapped[str | None] = mapped_column(Text, nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)





class SyncRun(Base):

    __tablename__ = "sync_runs"



    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    songs_added: Mapped[int] = mapped_column(Integer, default=0)

    songs_updated: Mapped[int] = mapped_column(Integer, default=0)

    history_items: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RoomState(Base):
    __tablename__ = "room_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scroll_anchor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Favorite(Base):
    __tablename__ = "favorites"

    song_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("songs.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

