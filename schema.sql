CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    display_name TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_name TEXT NOT NULL,
    image TEXT NOT NULL,
    ra_center REAL NOT NULL,
    dec_center REAL NOT NULL,
    redshift REAL,
    pixscale REAL NOT NULL,
    catalog_source TEXT NOT NULL DEFAULT 'default',
    catalog_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (catalog_source, cluster_name)
);

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    cluster_id INTEGER NOT NULL,
    x REAL,
    y REAL,
    ra REAL,
    dec REAL,
    skipped INTEGER NOT NULL DEFAULT 0,
    flagged INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id),
    UNIQUE (user_id, cluster_id)
);

CREATE TABLE IF NOT EXISTS catalog_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    uploaded_by INTEGER,
    filename TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_annotations_user_id ON annotations(user_id);
CREATE INDEX IF NOT EXISTS idx_annotations_cluster_id ON annotations(cluster_id);
CREATE INDEX IF NOT EXISTS idx_clusters_source_name ON clusters(catalog_source, cluster_name);
