SCHEMA = (
    """CREATE TABLE motion_sequences (
        id TEXT PRIMARY KEY, sample_key TEXT UNIQUE, revision INTEGER NOT NULL CHECK (revision > 0),
        title TEXT NOT NULL, frames INTEGER NOT NULL, shots INTEGER NOT NULL,
        document TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE motion_assets (
        id TEXT PRIMARY KEY, sequence_id TEXT NOT NULL REFERENCES motion_sequences(id),
        name TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL
    )""",
    "CREATE INDEX motion_assets_owner ON motion_assets(sequence_id)",
    """CREATE TABLE motion_jobs (
        id TEXT PRIMARY KEY, sequence_id TEXT NOT NULL REFERENCES motion_sequences(id),
        revision INTEGER NOT NULL, state TEXT NOT NULL,
        done INTEGER NOT NULL, frames INTEGER NOT NULL, encoder TEXT, message TEXT NOT NULL,
        folder TEXT NOT NULL, filename TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX motion_jobs_sequence ON motion_jobs(sequence_id, created_at DESC)",
)
