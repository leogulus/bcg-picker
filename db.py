import math
import sqlite3
from pathlib import Path

import click
from flask import current_app, g


DEFAULT_SCHEMA_FILE = Path(__file__).with_name("schema.sql")
REVIEW_CONFLICT_THRESHOLD_DEG = 1.5 / 3600.0


def connect_db(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def get_db():
    if "db" not in g:
        g.db = connect_db(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(error=None):
    del error
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db(schema_path=None):
    schema_file = Path(schema_path or current_app.config["DATABASE_SCHEMA"])
    database = get_db()
    with schema_file.open() as file_obj:
        database.executescript(file_obj.read())
    database.commit()


def ensure_db():
    init_db()
    ensure_annotations_schema()


def ensure_annotations_schema():
    database = get_db()
    columns = {
        row["name"]
        for row in database.execute("PRAGMA table_info(annotations)").fetchall()
    }
    if "flagged" not in columns:
        database.execute(
            "ALTER TABLE annotations ADD COLUMN flagged INTEGER NOT NULL DEFAULT 0"
        )
        database.commit()


def fetch_catalog_rows(catalog_source="default"):
    rows = get_db().execute(
        """
        SELECT cluster_name, image, ra_center, dec_center, redshift, pixscale
        FROM clusters
        WHERE catalog_source = ?
        ORDER BY catalog_order, id
        """,
        (catalog_source,),
    ).fetchall()
    return [
        {
            "cluster": row["cluster_name"],
            "image": row["image"],
            "ra": row["ra_center"],
            "dec": row["dec_center"],
            "redshift": row["redshift"],
            "pixscale": row["pixscale"],
        }
        for row in rows
    ]


def fetch_catalog_rows_for_user_filter(username, filter_mode, catalog_source="default"):
    if filter_mode not in {"skipped", "flagged"}:
        raise ValueError("Unsupported catalog filter mode")

    filter_column = "a.skipped" if filter_mode == "skipped" else "a.flagged"
    rows = get_db().execute(
        f"""
        SELECT
            c.cluster_name,
            c.image,
            c.ra_center,
            c.dec_center,
            c.redshift,
            c.pixscale
        FROM clusters AS c
        JOIN annotations AS a ON a.cluster_id = c.id
        JOIN users AS u ON u.id = a.user_id
        WHERE u.username = ?
          AND c.catalog_source = ?
          AND {filter_column} = 1
        ORDER BY c.catalog_order, c.id
        """
        ,
        (username, catalog_source),
    ).fetchall()
    return [
        {
            "cluster": row["cluster_name"],
            "image": row["image"],
            "ra": row["ra_center"],
            "dec": row["dec_center"],
            "redshift": row["redshift"],
            "pixscale": row["pixscale"],
        }
        for row in rows
    ]


def replace_catalog_rows(rows, catalog_source="default"):
    database = get_db()
    database.execute(
        "DELETE FROM clusters WHERE catalog_source = ?",
        (catalog_source,),
    )
    database.executemany(
        """
        INSERT INTO clusters (
            cluster_name,
            image,
            ra_center,
            dec_center,
            redshift,
            pixscale,
            catalog_source,
            catalog_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["cluster"],
                row["image"],
                row["ra"],
                row["dec"],
                row["redshift"] if row["redshift"] != "" else None,
                row["pixscale"],
                catalog_source,
                order,
            )
            for order, row in enumerate(rows)
        ],
    )
    database.commit()


def get_or_create_user(username):
    database = get_db()
    row = database.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is not None:
        return row

    cursor = database.execute(
        "INSERT INTO users (username, display_name) VALUES (?, ?)",
        (username, username),
    )
    database.commit()
    return database.execute(
        "SELECT * FROM users WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()


def get_user_by_username(username):
    return get_db().execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()


def list_usernames():
    rows = get_db().execute(
        """
        SELECT username
        FROM users
        ORDER BY lower(username), username
        """
    ).fetchall()
    return [row["username"] for row in rows]


def get_annotation_for_user(cluster_name, username):
    return get_db().execute(
        """
        SELECT
            a.x,
            a.y,
            a.ra,
            a.dec,
            a.skipped,
            a.flagged
        FROM annotations AS a
        JOIN users AS u ON u.id = a.user_id
        JOIN clusters AS c ON c.id = a.cluster_id
        WHERE u.username = ? AND c.cluster_name = ? AND c.catalog_source = ?
        """,
        (username, cluster_name, current_app.config["CURRENT_CATALOG_SOURCE"]),
    ).fetchone()


def upsert_annotation(username, annotation):
    user = get_or_create_user(username)
    database = get_db()
    cluster = database.execute(
        """
        SELECT id
        FROM clusters
        WHERE cluster_name = ? AND catalog_source = ?
        """,
        (annotation["cluster"], current_app.config["CURRENT_CATALOG_SOURCE"]),
    ).fetchone()
    if cluster is None:
        raise ValueError("Cluster not found in database")

    database.execute(
        """
        INSERT INTO annotations (
            user_id,
            cluster_id,
            x,
            y,
            ra,
            dec,
            skipped,
            flagged,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, cluster_id)
        DO UPDATE SET
            x = excluded.x,
            y = excluded.y,
            ra = excluded.ra,
            dec = excluded.dec,
            skipped = excluded.skipped,
            flagged = excluded.flagged,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user["id"],
            cluster["id"],
            annotation.get("x"),
            annotation.get("y"),
            annotation.get("ra"),
            annotation.get("dec"),
            1 if annotation.get("skipped") else 0,
            1 if annotation.get("flagged") else 0,
        ),
    )
    database.commit()


def get_user_progress(username):
    rows = get_db().execute(
        """
        SELECT a.x, a.skipped, a.flagged
        FROM annotations AS a
        JOIN users AS u ON u.id = a.user_id
        JOIN clusters AS c ON c.id = a.cluster_id
        WHERE u.username = ? AND c.catalog_source = ?
        """,
        (username, current_app.config["CURRENT_CATALOG_SOURCE"]),
    ).fetchall()

    done = 0
    skipped = 0
    flagged = 0
    for row in rows:
        if row["skipped"]:
            skipped += 1
        elif row["flagged"]:
            flagged += 1
        elif row["x"] is not None:
            done += 1

    return {
        "done": done,
        "skipped": skipped,
        "flagged": flagged,
    }


def reset_user_annotations(username):
    database = get_db()
    database.execute(
        """
        DELETE FROM annotations
        WHERE user_id = (
            SELECT id FROM users WHERE username = ?
        )
        AND cluster_id IN (
            SELECT id
            FROM clusters
            WHERE catalog_source = ?
        )
        """,
        (username, current_app.config["CURRENT_CATALOG_SOURCE"]),
    )
    database.commit()


def get_next_unannotated_cluster(username):
    row = get_db().execute(
        """
        SELECT c.cluster_name
        FROM clusters AS c
        LEFT JOIN users AS u
            ON u.username = ?
        LEFT JOIN annotations AS a
            ON a.cluster_id = c.id
           AND a.user_id = u.id
        WHERE c.catalog_source = ?
          AND a.id IS NULL
        ORDER BY c.catalog_order, c.id
        LIMIT 1
        """,
        (username, current_app.config["CURRENT_CATALOG_SOURCE"]),
    ).fetchone()
    if row is None:
        return None
    return row["cluster_name"]


def export_user_annotations(username):
    rows = get_db().execute(
        """
        SELECT
            c.cluster_name AS cluster,
            c.image AS image,
            a.x,
            a.y,
            a.ra,
            a.dec,
            a.skipped,
            a.flagged
        FROM annotations AS a
        JOIN users AS u ON u.id = a.user_id
        JOIN clusters AS c ON c.id = a.cluster_id
        WHERE u.username = ? AND c.catalog_source = ?
        ORDER BY c.catalog_order, c.id
        """,
        (username, current_app.config["CURRENT_CATALOG_SOURCE"]),
    ).fetchall()
    return [
        {
            "cluster": row["cluster"],
            "image": row["image"],
            "x": row["x"] if row["x"] is not None else "",
            "y": row["y"] if row["y"] is not None else "",
            "ra": row["ra"] if row["ra"] is not None else "",
            "dec": row["dec"] if row["dec"] is not None else "",
            "skipped": "True" if row["skipped"] else "False",
            "flagged": "True" if row["flagged"] else "False",
        }
        for row in rows
    ]


def export_all_annotations():
    rows = get_db().execute(
        """
        SELECT
            u.username AS username,
            c.cluster_name AS cluster,
            c.image AS image,
            a.x,
            a.y,
            a.ra,
            a.dec,
            a.skipped,
            a.flagged,
            a.updated_at
        FROM annotations AS a
        JOIN users AS u ON u.id = a.user_id
        JOIN clusters AS c ON c.id = a.cluster_id
        WHERE c.catalog_source = ?
        ORDER BY lower(u.username), u.username, c.catalog_order, c.id
        """,
        (current_app.config["CURRENT_CATALOG_SOURCE"],),
    ).fetchall()
    return [
        {
            "username": row["username"],
            "cluster": row["cluster"],
            "image": row["image"],
            "x": row["x"] if row["x"] is not None else "",
            "y": row["y"] if row["y"] is not None else "",
            "ra": row["ra"] if row["ra"] is not None else "",
            "dec": row["dec"] if row["dec"] is not None else "",
            "skipped": "True" if row["skipped"] else "False",
            "flagged": "True" if row["flagged"] else "False",
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def fetch_review_annotations():
    rows = get_db().execute(
        """
        SELECT
            c.cluster_name AS cluster,
            c.image AS image,
            c.catalog_order AS catalog_order,
            u.username AS username,
            a.x,
            a.y,
            a.ra,
            a.dec,
            a.skipped,
            a.flagged,
            a.updated_at
        FROM annotations AS a
        JOIN users AS u ON u.id = a.user_id
        JOIN clusters AS c ON c.id = a.cluster_id
        WHERE c.catalog_source = ?
        ORDER BY c.catalog_order, c.id, lower(u.username), u.username
        """,
        (current_app.config["CURRENT_CATALOG_SOURCE"],),
    ).fetchall()

    grouped = []
    current_cluster = None
    current_group = None
    decision_points = []

    for row in rows:
        cluster_name = row["cluster"]
        if cluster_name != current_cluster:
            if current_group is not None:
                current_group["has_disagreement"] = has_review_disagreement(decision_points)
                grouped.append(current_group)

            current_cluster = cluster_name
            current_group = {
                "cluster": cluster_name,
                "image": row["image"],
                "catalog_order": row["catalog_order"],
                "annotations": [],
                "has_disagreement": False,
            }
            decision_points = []

        annotation = {
            "username": row["username"],
            "x": row["x"] if row["x"] is not None else "",
            "y": row["y"] if row["y"] is not None else "",
            "ra": row["ra"] if row["ra"] is not None else "",
            "dec": row["dec"] if row["dec"] is not None else "",
            "skipped": bool(row["skipped"]),
            "flagged": bool(row["flagged"]),
            "updated_at": row["updated_at"],
        }
        current_group["annotations"].append(annotation)
        decision_points.append(annotation)

    if current_group is not None:
        current_group["has_disagreement"] = has_review_disagreement(decision_points)
        grouped.append(current_group)

    return grouped


def fetch_review_cluster(cluster_name):
    for group in fetch_review_annotations():
        if group["cluster"] == cluster_name:
            return group
    return None


def has_review_disagreement(annotations):
    if not annotations:
        return False

    states = {
        "skipped" if annotation["skipped"] else
        "flagged" if annotation["flagged"] else
        "marked"
        for annotation in annotations
    }
    if len(states) > 1:
        return True
    if "skipped" in states or "flagged" in states:
        return False

    reference = annotations[0]
    reference_ra = float(reference["ra"])
    reference_dec = float(reference["dec"])

    for annotation in annotations[1:]:
        delta_ra = float(annotation["ra"]) - reference_ra
        delta_dec = float(annotation["dec"]) - reference_dec
        separation_deg = math.sqrt(delta_ra ** 2 + delta_dec ** 2)
        if separation_deg > REVIEW_CONFLICT_THRESHOLD_DEG:
            return True

    return False


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Initialized the SQLite database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
