from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

import asyncio
import json
import time

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, nulls_last
from sqlalchemy.orm import Session

from auth import (
    SESSION_COOKIE_NAME,
    create_session_token,
    is_admin_request,
    require_admin,
    verify_admin_password,
)
from config import (
    CORS_ORIGINS,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_MAX_AGE,
    STATIC_DIR,
    sqlite_db_path,
)
from db.database import SessionLocal, get_db, init_db
from db.models import RoomState, Song, SyncRun
from services.enrichment import enrich_song, enrich_song_from_url, enrich_top_songs
from services.http_cache import bust_cache_for_song, clear_http_cache
from services.takeout_sync import detect_language, thumbnail_for, video_id

app = FastAPI(title="Sing-Along API", version="0.5.0")
api = APIRouter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SongOut(BaseModel):
    id: int
    yt_video_id: str
    title: str
    artist: str
    language: str
    play_count: int
    last_played_at: datetime | None
    thumbnail_url: str | None
    duration_sec: int | None
    source_status: str
    chord_source: str | None = None
    source_url: str | None = None
    enriched_at: datetime | None = None
    has_sheet: bool = False
    youtube_url: str | None = None

    model_config = {"from_attributes": True}


class SongDetailOut(SongOut):
    plain_lyrics: str | None = None
    synced_lyrics: str | None = None
    chordpro_full: str | None = None
    chordpro_easy: str | None = None
    easy_note_he: str | None = None
    easy_note_en: str | None = None
    enrich_error: str | None = None
    enrich_attempts: int = 0
    enrich_history: list[dict[str, Any]] = Field(default_factory=list)


class LibraryStatusOut(BaseModel):
    total_songs: int
    last_import: datetime | None
    imported_songs: int
    manual_songs: int
    ready_songs: int
    needs_chords_songs: int


class SongCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    artist: str = Field(default="", max_length=512)
    language: Literal["he", "en"] | None = None
    youtube_url: str | None = None
    play_count: int = Field(default=0, ge=0)


class SongSheetUpdateIn(BaseModel):
    chordpro_full: str | None = None
    chordpro_easy: str | None = None
    source_status: Literal["ready", "needs_chords", "needs_review"] | None = "ready"


class EnrichFromUrlIn(BaseModel):
    source_url: str = Field(min_length=8, max_length=2048)


class EnrichSummaryOut(BaseModel):
    processed: int
    ready: int
    needs_chords: int
    failed: int
    skipped: int
    skipped_max_attempts: int = 0


class SongListOut(BaseModel):
    items: list[SongOut]
    total: int
    limit: int
    offset: int


class RoomStateOut(BaseModel):
    song_id: int | None = None
    updated_at: datetime | None = None
    title: str | None = None
    artist: str | None = None


class RoomSyncIn(BaseModel):
    song_id: int = Field(ge=1)


class LoginIn(BaseModel):
    password: str = Field(min_length=1)


class AuthMeOut(BaseModel):
    admin: bool


AdminDep = Annotated[None, Depends(require_admin)]


def _active_songs(db: Session):
    return db.query(Song).filter(Song.deleted_at.is_(None))


def _get_active_song(db: Session, song_id: int) -> Song | None:
    return _active_songs(db).filter(Song.id == song_id).one_or_none()


def _youtube_url(song: Song) -> str | None:
    vid = song.yt_video_id
    if not vid or vid.startswith("manual-"):
        return None
    return f"https://www.youtube.com/watch?v={vid}"


def _song_out(song: Song) -> SongOut:
    return SongOut(
        id=song.id,
        yt_video_id=song.yt_video_id,
        title=song.title,
        artist=song.artist,
        language=song.language,
        play_count=song.play_count,
        last_played_at=song.last_played_at,
        thumbnail_url=song.thumbnail_url,
        duration_sec=song.duration_sec,
        source_status=song.source_status,
        chord_source=song.chord_source,
        source_url=song.source_url,
        enriched_at=song.enriched_at,
        has_sheet=bool(song.chordpro_full),
        youtube_url=_youtube_url(song),
    )


def _parse_enrich_history(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _song_detail(song: Song) -> SongDetailOut:
    base = _song_out(song).model_dump()
    return SongDetailOut(
        **base,
        plain_lyrics=song.plain_lyrics,
        synced_lyrics=song.synced_lyrics,
        chordpro_full=song.chordpro_full,
        chordpro_easy=song.chordpro_easy,
        easy_note_he=song.easy_note_he,
        easy_note_en=song.easy_note_en,
        enrich_error=song.enrich_error,
        enrich_attempts=song.enrich_attempts or 0,
        enrich_history=_parse_enrich_history(song.enrich_history),
    )


def _library_status(db: Session) -> LibraryStatusOut:
    last_run = db.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    visible = _active_songs(db)
    total_songs = visible.count()
    manual_songs = visible.filter(Song.source_status == "manual").count()
    ready_songs = visible.filter(Song.source_status == "ready").count()
    needs_chords_songs = visible.filter(Song.source_status == "needs_chords").count()
    return LibraryStatusOut(
        total_songs=total_songs,
        last_import=last_run.finished_at if last_run else None,
        imported_songs=total_songs - manual_songs,
        manual_songs=manual_songs,
        ready_songs=ready_songs,
        needs_chords_songs=needs_chords_songs,
    )


def _run_enrich_top(limit: int, force: bool) -> None:
    db = SessionLocal()
    try:
        enrich_top_songs(db, limit=limit, force=force)
    finally:
        db.close()


def _ensure_room_state(db: Session) -> RoomState:
    room = db.get(RoomState, 1)
    if room is None:
        room = RoomState(id=1)
        db.add(room)
        db.commit()
        db.refresh(room)
    return room


def _room_state_out(db: Session, room: RoomState) -> RoomStateOut:
    if not room.song_id:
        return RoomStateOut(song_id=None, updated_at=room.updated_at)
    song = _get_active_song(db, room.song_id)
    if not song:
        return RoomStateOut(song_id=None, updated_at=room.updated_at)
    return RoomStateOut(
        song_id=song.id,
        updated_at=room.updated_at,
        title=song.title,
        artist=song.artist,
    )


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        _ensure_room_state(db)
    finally:
        db.close()


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/auth/login")
def auth_login(payload: LoginIn, response: Response):
    if not verify_admin_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(),
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
        secure=SESSION_COOKIE_SECURE,
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return {"ok": True}


@api.post("/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite=SESSION_COOKIE_SAMESITE,
        secure=SESSION_COOKIE_SECURE,
    )
    return {"ok": True}


@api.get("/auth/me", response_model=AuthMeOut)
def auth_me(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    return AuthMeOut(admin=is_admin_request(request, x_admin_token))


@api.get("/library/status", response_model=LibraryStatusOut)
def library_status(db: Session = Depends(get_db)):
    return _library_status(db)


@api.get("/import/status", response_model=LibraryStatusOut)
def import_status_compat(db: Session = Depends(get_db)):
    return _library_status(db)


@api.post("/enrich/top", response_model=EnrichSummaryOut)
def enrich_top(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=200),
    force: bool = Query(default=False),
    background: bool = Query(default=False),
    _: AdminDep = None,
):
    if background:
        background_tasks.add_task(_run_enrich_top, limit, force)
        return EnrichSummaryOut(
            processed=0, ready=0, needs_chords=0, failed=0, skipped=0, skipped_max_attempts=0
        )

    summary = enrich_top_songs(db, limit=limit, force=force)
    return EnrichSummaryOut(**summary.__dict__)


@api.post("/songs/{song_id}/enrich", response_model=SongDetailOut)
def enrich_one_song(
    song_id: int,
    db: Session = Depends(get_db),
    force: bool = Query(default=True),
    bust_cache: bool = Query(default=False),
    _: AdminDep = None,
):
    song = _get_active_song(db, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    if bust_cache:
        deleted = bust_cache_for_song(
            song.title,
            song.artist,
            song.language,
            song.source_url,
        )
        print(f"Cache bust for song {song_id}: {deleted} entr(ies) deleted", flush=True)
    enrich_song(song, force=force)
    db.commit()
    db.refresh(song)
    return _song_detail(song)


@api.post("/admin/cache/clear")
def clear_scraper_cache(_: AdminDep = None):
    clear_http_cache()
    return {"cleared": True}


@api.post("/songs/{song_id}/enrich-from-url", response_model=SongDetailOut)
def enrich_one_song_from_url(
    song_id: int,
    payload: EnrichFromUrlIn,
    db: Session = Depends(get_db),
    _: AdminDep = None,
):
    song = _get_active_song(db, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    try:
        enrich_song_from_url(song, payload.source_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(song)
    return _song_detail(song)


@api.post("/songs", response_model=SongOut)
def create_song(
    payload: SongCreateIn,
    db: Session = Depends(get_db),
    _: AdminDep = None,
):

    title = payload.title.strip()
    artist = payload.artist.strip()
    language = payload.language or detect_language(title, artist)

    yt_video_id = video_id(payload.youtube_url) if payload.youtube_url else None
    if yt_video_id:
        existing = (
            db.query(Song).filter(Song.yt_video_id == yt_video_id).one_or_none()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Song already exists: {existing.title}",
            )
    else:
        yt_video_id = f"manual-{uuid4().hex[:12]}"

    now = datetime.utcnow()
    song = Song(
        yt_video_id=yt_video_id,
        title=title,
        artist=artist,
        language=language,
        play_count=payload.play_count,
        last_played_at=None,
        thumbnail_url=thumbnail_for(yt_video_id)
        if not yt_video_id.startswith("manual-")
        else None,
        duration_sec=None,
        source_status="manual",
        last_synced_at=now,
    )
    db.add(song)
    db.commit()
    db.refresh(song)
    return _song_out(song)


@api.get("/songs", response_model=SongListOut)
def list_songs(
    db: Session = Depends(get_db),
    lang: Literal["he", "en"] | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: Literal["play_count", "last_played_at"] = Query(default="play_count"),
    status: str | None = Query(default=None),
    ids: str | None = Query(default=None, description="Comma-separated song IDs"),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    query = _active_songs(db)

    if ids is not None:
        id_list = [int(part) for part in ids.split(",") if part.strip().isdigit()]
        if not id_list:
            return SongListOut(items=[], total=0, limit=limit, offset=offset)
        query = query.filter(Song.id.in_(id_list))

    if lang:
        query = query.filter(Song.language == lang)
    if status:
        status_list = [part.strip() for part in status.split(",") if part.strip()]
        if len(status_list) == 1:
            query = query.filter(Song.source_status == status_list[0])
        elif status_list:
            query = query.filter(Song.source_status.in_(status_list))
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(
            (Song.title.ilike(needle)) | (Song.artist.ilike(needle))
        )

    if sort == "last_played_at":
        query = query.order_by(nulls_last(desc(Song.last_played_at)), Song.title.asc())
    else:
        query = query.order_by(Song.play_count.desc(), Song.title.asc())

    total = query.count()
    songs = query.offset(offset).limit(limit).all()
    return SongListOut(
        items=[_song_out(song) for song in songs],
        total=total,
        limit=limit,
        offset=offset,
    )


@api.get("/songs/{song_id}", response_model=SongDetailOut)
def get_song(song_id: int, db: Session = Depends(get_db)):
    song = _get_active_song(db, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return _song_detail(song)


@api.delete("/songs/{song_id}")
def remove_song(
    song_id: int,
    db: Session = Depends(get_db),
    _: AdminDep = None,
):
    song = _get_active_song(db, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    song.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@api.patch("/songs/{song_id}/sheet", response_model=SongDetailOut)
def update_song_sheet(
    song_id: int,
    payload: SongSheetUpdateIn,
    db: Session = Depends(get_db),
    _: AdminDep = None,
):
    song = _get_active_song(db, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    if not payload.chordpro_full and not payload.chordpro_easy:
        raise HTTPException(status_code=400, detail="Provide chordpro_full and/or chordpro_easy")

    if payload.chordpro_full is not None:
        song.chordpro_full = payload.chordpro_full.strip()
    if payload.chordpro_easy is not None:
        song.chordpro_easy = payload.chordpro_easy.strip() or None

    song.source_status = payload.source_status or "ready"
    song.chord_source = "manual"
    song.enriched_at = datetime.utcnow()
    song.enrich_error = None
    db.commit()
    db.refresh(song)
    return _song_detail(song)


@api.get("/room/state", response_model=RoomStateOut)
def get_room_state(db: Session = Depends(get_db)):
    room = _ensure_room_state(db)
    return _room_state_out(db, room)


async def _room_state_event_stream():
    last_sent_at: datetime | None = None
    last_keepalive = time.monotonic()
    try:
        while True:
            db = SessionLocal()
            try:
                room = _ensure_room_state(db)
                if last_sent_at != room.updated_at:
                    state = _room_state_out(db, room)
                    yield f"data: {state.model_dump_json()}\n\n"
                    last_sent_at = room.updated_at
            finally:
                db.close()

            now = time.monotonic()
            if now - last_keepalive >= 15:
                yield ": keepalive\n\n"
                last_keepalive = now

            await asyncio.sleep(1)
    except asyncio.CancelledError:
        raise


@api.get("/room/stream")
async def stream_room_state():
    return StreamingResponse(
        _room_state_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@api.post("/room/sync", response_model=RoomStateOut)
def sync_room(payload: RoomSyncIn, db: Session = Depends(get_db), _: AdminDep = None):
    song = _get_active_song(db, payload.song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    if song.source_status != "ready":
        raise HTTPException(status_code=400, detail="Only ready songs can be synced to the room")

    room = _ensure_room_state(db)
    room.song_id = song.id
    room.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(room)
    return _room_state_out(db, room)


def _song_export_record(song: Song) -> dict[str, Any]:
    return _song_detail(song).model_dump(mode="json")


@api.get("/admin/export.json")
def export_songs_json(db: Session = Depends(get_db), _: AdminDep = None):
    songs = _active_songs(db).order_by(Song.id).all()
    return JSONResponse(
        {
            "exported_at": datetime.utcnow().isoformat(),
            "song_count": len(songs),
            "songs": [_song_export_record(song) for song in songs],
        }
    )


@api.get("/admin/db.sqlite")
def export_sqlite_db(_: AdminDep = None):
    db_path = sqlite_db_path()
    if db_path is None or not db_path.is_file():
        raise HTTPException(status_code=404, detail="SQLite database backup not available")
    return FileResponse(
        path=db_path,
        filename="singalong.db",
        media_type="application/octet-stream",
    )


app.include_router(api, prefix="/api")


@app.get("/health")
def root_health():
    return {"status": "ok"}


def _mount_frontend() -> None:
    if STATIC_DIR.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")


_mount_frontend()
