"""Version 4 schema. Each statement participates in the workspace migration transaction."""

VISUAL_SCHEMA = (
    """
    CREATE TABLE cast_library (
        id TEXT PRIMARY KEY,
        design TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision > 0),
        active_reference TEXT REFERENCES studio_images(id),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        archived_at TEXT
    )
    """,
    """
    CREATE TABLE studio_images (
        id TEXT PRIMARY KEY,
        project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
        scene_id TEXT,
        character_id TEXT REFERENCES cast_library(id) ON DELETE CASCADE,
        number INTEGER NOT NULL CHECK (number > 0),
        original_name TEXT NOT NULL,
        source TEXT NOT NULL,
        license_note TEXT NOT NULL,
        width INTEGER NOT NULL CHECK (width > 0),
        height INTEGER NOT NULL CHECK (height > 0),
        bytes INTEGER NOT NULL CHECK (bytes > 0),
        created_at TEXT NOT NULL,
        last_approved_at TEXT,
        UNIQUE (project_id, scene_id, number),
        UNIQUE (character_id, number),
        CHECK ((project_id IS NOT NULL AND scene_id IS NOT NULL AND character_id IS NULL)
            OR (project_id IS NULL AND scene_id IS NULL AND character_id IS NOT NULL))
    )
    """,
    """
    CREATE TABLE board_shots (
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        scene_id TEXT NOT NULL,
        title TEXT NOT NULL,
        active_image TEXT NOT NULL REFERENCES studio_images(id),
        revision INTEGER NOT NULL CHECK (revision > 0),
        approved_at TEXT,
        approved_context TEXT,
        PRIMARY KEY (project_id, scene_id)
    )
    """,
)
