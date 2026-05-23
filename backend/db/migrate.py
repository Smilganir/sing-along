from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from db.database import engine


MIGRATIONS = [
    "ALTER TABLE songs ADD COLUMN plain_lyrics TEXT",
    "ALTER TABLE songs ADD COLUMN synced_lyrics TEXT",
    "ALTER TABLE songs ADD COLUMN chordpro_full TEXT",
    "ALTER TABLE songs ADD COLUMN chordpro_easy TEXT",
    "ALTER TABLE songs ADD COLUMN easy_note_he VARCHAR(512)",
    "ALTER TABLE songs ADD COLUMN easy_note_en VARCHAR(512)",
    "ALTER TABLE songs ADD COLUMN enrich_error TEXT",
    "ALTER TABLE songs ADD COLUMN chord_source VARCHAR(64)",
    "ALTER TABLE songs ADD COLUMN source_url VARCHAR(1024)",
    "ALTER TABLE songs ADD COLUMN enriched_at DATETIME",
    "ALTER TABLE songs ADD COLUMN deleted_at DATETIME",
    "ALTER TABLE songs ADD COLUMN enrich_attempts INTEGER DEFAULT 0",
    "ALTER TABLE songs ADD COLUMN enrich_history TEXT",
]


def _column_already_exists(exc: Exception) -> bool:
    message = str(exc).lower()
    return "duplicate column" in message or "already exists" in message


ROOM_STATE_MIGRATIONS = [
    "ALTER TABLE room_state ADD COLUMN scroll_anchor VARCHAR(64)",
]

INDEX_MIGRATIONS = [
    "CREATE INDEX IF NOT EXISTS ix_songs_deleted_at ON songs (deleted_at)",
    "CREATE INDEX IF NOT EXISTS ix_songs_play_count ON songs (play_count DESC)",
    "CREATE INDEX IF NOT EXISTS ix_songs_language ON songs (language)",
    "CREATE INDEX IF NOT EXISTS ix_songs_source_status ON songs (source_status)",
    "CREATE INDEX IF NOT EXISTS ix_songs_last_played_at ON songs (last_played_at)",
]


def _apply_column_migrations(connection, table: str, statements: list[str]) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(table)}
    for statement in statements:
        column_name = statement.split("ADD COLUMN ")[1].split()[0]
        if column_name in existing:
            continue
        try:
            connection.execute(text(statement))
            existing.add(column_name)
        except (ProgrammingError, OperationalError) as exc:
            if _column_already_exists(exc):
                existing.add(column_name)
                continue
            raise


def run_migrations() -> None:
    inspector = inspect(engine)
    if "songs" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("songs")}
    with engine.begin() as connection:
        for statement in MIGRATIONS:
            column_name = statement.split("ADD COLUMN ")[1].split()[0]
            if column_name in existing:
                continue
            try:
                connection.execute(text(statement))
                existing.add(column_name)
            except (ProgrammingError, OperationalError) as exc:
                if _column_already_exists(exc):
                    existing.add(column_name)
                    continue
                raise
        _apply_column_migrations(connection, "room_state", ROOM_STATE_MIGRATIONS)
        for statement in INDEX_MIGRATIONS:
            try:
                connection.execute(text(statement))
            except (ProgrammingError, OperationalError):
                pass
