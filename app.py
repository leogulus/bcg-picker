from flask import Flask, Response, current_app, jsonify, redirect, render_template, request
from flask import session
from flask import send_from_directory, url_for

import csv
import io
import os
import sqlite3

import click

from db import ensure_db, export_user_annotations, fetch_catalog_rows
from db import get_annotation_for_user, get_or_create_user, get_user_progress
from db import init_app as init_db_app, list_usernames, replace_catalog_rows
from db import get_next_unannotated_cluster, upsert_annotation

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CATALOG_FILE = os.path.join(BASE_DIR, "data", "catalog.csv")
UPLOADED_CATALOG_FILE = os.path.join(BASE_DIR, "data", "uploaded_catalog.csv")
DATABASE_PATH = os.path.join(BASE_DIR, "data", "bcg_picker.sqlite3")
DATABASE_SCHEMA = os.path.join(BASE_DIR, "schema.sql")
DEFAULT_CATALOG_SOURCE = "default"
UPLOADED_CATALOG_SOURCE = "uploaded"
CATALOG_FIELDS = {"cluster", "image", "ra", "dec", "redshift", "pixscale"}
RESULTS_FIELDNAMES = ["cluster", "image", "x", "y", "ra", "dec", "skipped"]
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "bcg-picker-dev-secret")


def read_csv_rows(path):
    with open(path, newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def validate_catalog_rows(rows):
    if not rows:
        raise ValueError("Catalog is empty")

    missing_fields = CATALOG_FIELDS - set(rows[0].keys())
    if missing_fields:
        missing_list = ", ".join(sorted(missing_fields))
        raise ValueError(f"Catalog is missing required columns: {missing_list}")


def load_catalog(path):
    rows = read_csv_rows(path)
    validate_catalog_rows(rows)
    return rows


def get_catalog():
    return current_app.config["CATALOG"]


def set_catalog(app, rows):
    app.config["CATALOG"] = rows
    app.config["CATALOG_INDEX"] = {
        row["cluster"]: index
        for index, row in enumerate(rows)
    }
    app.config["CATALOG_BY_CLUSTER"] = {
        row["cluster"]: row
        for row in rows
    }


def load_runtime_catalog(app):
    fallback_rows = load_catalog(app.config["DEFAULT_CATALOG_FILE"])

    if not os.path.exists(app.config["DATABASE_PATH"]):
        return fallback_rows

    try:
        with app.app_context():
            database_rows = fetch_catalog_rows(app.config["CURRENT_CATALOG_SOURCE"])
    except sqlite3.Error:
        return fallback_rows

    if not database_rows:
        with app.app_context():
            replace_catalog_rows(fallback_rows, app.config["DEFAULT_CATALOG_SOURCE"])
            database_rows = fetch_catalog_rows(app.config["DEFAULT_CATALOG_SOURCE"])

    return database_rows or fallback_rows


def get_current_username():
    return session.get("username")


def get_existing_usernames():
    return list_usernames()


def build_user_summary():
    total = len(get_catalog())
    current_user = get_current_username()
    if not current_user:
        return {"current": None}

    progress = get_user_progress(current_user)
    return {
        "current": {
            "username": current_user,
            "done": progress["done"],
            "skipped": progress["skipped"],
            "remaining": total - progress["done"] - progress["skipped"],
        }
    }


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["DEFAULT_CATALOG_FILE"] = DEFAULT_CATALOG_FILE
    app.config["UPLOADED_CATALOG_FILE"] = UPLOADED_CATALOG_FILE
    app.config["DATABASE_PATH"] = DATABASE_PATH
    app.config["DATABASE_SCHEMA"] = DATABASE_SCHEMA
    app.config["DEFAULT_CATALOG_SOURCE"] = DEFAULT_CATALOG_SOURCE
    app.config["UPLOADED_CATALOG_SOURCE"] = UPLOADED_CATALOG_SOURCE
    app.config["CURRENT_CATALOG_SOURCE"] = DEFAULT_CATALOG_SOURCE
    app.config["SECRET_KEY"] = SECRET_KEY
    if test_config:
        app.config.update(test_config)
    init_db_app(app)
    with app.app_context():
        ensure_db()
    set_catalog(app, load_runtime_catalog(app))

    @app.cli.command("import-catalog")
    @click.option("--path", "catalog_path", default=None, help="Path to a catalog CSV file.")
    @click.option("--source", "catalog_source", default=DEFAULT_CATALOG_SOURCE, help="Catalog source name in SQLite.")
    def import_catalog_command(catalog_path, catalog_source):
        source_path = catalog_path or current_app.config["DEFAULT_CATALOG_FILE"]
        rows = load_catalog(source_path)
        replace_catalog_rows(rows, catalog_source)
        click.echo(f"Imported {len(rows)} clusters into SQLite source '{catalog_source}'.")

    @app.route("/set_user", methods=["POST"])
    def set_user():
        selected_username = request.form.get("selected_username", "").strip()
        new_username = request.form.get("username", "").strip()
        username = new_username or selected_username
        if not username:
            return jsonify({
                "status": "error",
                "message": "Choose an existing user or enter a new username"
            }), 400

        get_or_create_user(username)
        session["username"] = username

        next_url = request.form.get("next_url")
        if next_url:
            return redirect(next_url)

        return jsonify({"status": "ok", "username": username})

    @app.route("/upload_catalog", methods=["POST"])
    def upload_catalog():
        file = request.files.get("file")

        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        upload_path = current_app.config["UPLOADED_CATALOG_FILE"]
        file.save(upload_path)

        try:
            rows = load_catalog(upload_path)
            replace_catalog_rows(rows, current_app.config["UPLOADED_CATALOG_SOURCE"])
            current_app.config["CURRENT_CATALOG_SOURCE"] = current_app.config["UPLOADED_CATALOG_SOURCE"]
            set_catalog(current_app, rows)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        return jsonify({
            "status": "ok",
            "total": len(get_catalog())
        })

    @app.route("/reset_catalog", methods=["POST"])
    def reset_catalog():
        current_app.config["CURRENT_CATALOG_SOURCE"] = current_app.config["DEFAULT_CATALOG_SOURCE"]
        set_catalog(current_app, load_runtime_catalog(current_app))

        return jsonify({
            "status": "ok",
            "total": len(get_catalog())
        })

    @app.route("/")
    def home():
        return redirect(url_for("index", index=0))

    @app.route("/<int:index>")
    def index(index):
        catalog = get_catalog()
        if index < 0 or index >= len(catalog):
            return "Cluster index out of range", 404

        galaxy = catalog[index]
        return render_template(
            "index.html",
            galaxy=galaxy,
            index=index,
            total=len(catalog),
            current_user=get_current_username(),
            existing_users=get_existing_usernames(),
            user_summary=build_user_summary(),
        )

    @app.route("/cluster/<cluster>")
    def cluster(cluster):
        catalog = get_catalog()
        galaxy = current_app.config["CATALOG_BY_CLUSTER"].get(cluster)
        if galaxy is None:
            return "Cluster not found", 404
        index = current_app.config["CATALOG_INDEX"][cluster]
        return render_template(
            "index.html",
            galaxy=galaxy,
            index=index,
            total=len(catalog),
            current_user=get_current_username(),
            existing_users=get_existing_usernames(),
            user_summary=build_user_summary(),
        )

    @app.route("/images/<filename>")
    def images(filename):
        return send_from_directory(os.path.join(BASE_DIR, "images"), filename)

    @app.route("/download_results")
    def download_results():
        username = get_current_username()
        if not username:
            return jsonify({
                "status": "error",
                "message": "Set a user before downloading results"
            }), 400

        rows = export_user_annotations(username)
        if not rows:
            return jsonify({
                "status": "error",
                "message": "No results available yet for this user"
            }), 404

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=RESULTS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={username}_results.csv"
            },
        )

    @app.route("/next_unannotated")
    def next_unannotated():
        username = get_current_username()
        if not username:
            return jsonify({
                "status": "error",
                "message": "Set a user before jumping to the next unannotated cluster"
            }), 400

        cluster_name = get_next_unannotated_cluster(username)
        if cluster_name is None:
            return jsonify({
                "status": "ok",
                "next_url": None,
                "message": "All clusters in this catalog are annotated for this user"
            })

        return jsonify({
            "status": "ok",
            "next_url": url_for("cluster", cluster=cluster_name)
        })

    @app.route("/save", methods=["POST"])
    def save():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        username = get_current_username()
        if not username:
            return jsonify({"status": "error", "message": "Set a user before saving"}), 400

        cluster_name = data.get("cluster")
        if not cluster_name:
            return jsonify({"status": "error", "message": "Missing cluster"}), 400

        skipped = bool(data.get("skipped", False))
        if not skipped:
            required_fields = ("image", "x", "y", "ra", "dec")
            missing_fields = [field for field in required_fields if data.get(field) in (None, "")]
            if missing_fields:
                return jsonify({
                    "status": "error",
                    "message": f"Missing fields: {', '.join(missing_fields)}"
                }), 400

        existing_row = get_annotation_for_user(cluster_name, username)
        updated = existing_row is not None

        annotation = {
            "cluster": cluster_name,
            "image": data.get("image", ""),
            "x": data.get("x", ""),
            "y": data.get("y", ""),
            "ra": data.get("ra", ""),
            "dec": data.get("dec", ""),
            "skipped": skipped,
        }

        try:
            upsert_annotation(username, annotation)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        next_cluster = get_next_unannotated_cluster(username)
        next_url = url_for("cluster", cluster=next_cluster) if next_cluster else None

        return jsonify({
            "status": "ok",
            "updated": updated,
            "next_url": next_url
        })

    @app.route("/load/<cluster>")
    def load(cluster):
        username = get_current_username()
        if not username:
            return jsonify({"exists": False})

        row = get_annotation_for_user(cluster, username)
        if row is not None:
            if row["skipped"]:
                return jsonify({
                    "exists": True,
                    "skipped": True
                })

            return jsonify({
                "exists": True,
                "skipped": False,
                "x": float(row["x"]) if row["x"] is not None else None,
                "y": float(row["y"]) if row["y"] is not None else None,
                "ra": float(row["ra"]) if row["ra"] is not None else None,
                "dec": float(row["dec"]) if row["dec"] is not None else None,
            })

        return jsonify({"exists": False})

    @app.route("/progress")
    def progress():
        total = len(get_catalog())
        username = get_current_username()
        if username:
            progress_data = get_user_progress(username)
            done = progress_data["done"]
            skipped = progress_data["skipped"]
        else:
            done = 0
            skipped = 0

        return jsonify({
            "total": total,
            "done": done,
            "skipped": skipped,
            "remaining": total - done - skipped
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
