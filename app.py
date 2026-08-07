from flask import Flask, Response, current_app, jsonify, redirect, render_template, request
from flask import session
from flask import send_from_directory, url_for

import csv
import io
import os

import csv_store
from csv_store import ensure_csv_storage_dirs, list_result_usernames

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("BCG_PICKER_DATA_DIR", os.path.join(BASE_DIR, "data"))
IMAGES_DIR = os.environ.get("BCG_PICKER_IMAGES_DIR", os.path.join(BASE_DIR, "images"))
DEFAULT_CATALOG_FILE = os.environ.get(
    "BCG_PICKER_DEFAULT_CATALOG",
    os.path.join(DATA_DIR, "catalog.csv"),
)
DEFAULT_BOOTSTRAP_RESULTS_FILE = os.environ.get(
    "BCG_PICKER_BOOTSTRAP_RESULTS_FILE",
    os.path.join(DATA_DIR, "imports", "taweewat_results.csv"),
)
DEFAULT_BOOTSTRAP_USERNAME = os.environ.get(
    "BCG_PICKER_BOOTSTRAP_USERNAME",
    "taweewat",
)
UPLOADED_CATALOG_FILE = os.environ.get(
    "BCG_PICKER_UPLOADED_CATALOG",
    os.path.join(DATA_DIR, "uploaded_catalog.csv"),
)
RESULTS_DIR = os.environ.get(
    "BCG_PICKER_RESULTS_DIR",
    os.path.join(DATA_DIR, "results"),
)
IMPORTS_DIR = os.environ.get(
    "BCG_PICKER_IMPORTS_DIR",
    os.path.join(DATA_DIR, "imports"),
)
COMBINED_DIR = os.environ.get(
    "BCG_PICKER_COMBINED_DIR",
    os.path.join(DATA_DIR, "combined"),
)
CATALOG_FIELDS = {"cluster", "image", "ra", "dec", "redshift", "pixscale"}
CATALOG_FIELDNAMES = ["cluster", "image", "ra", "dec", "redshift", "pixscale"]
RESULTS_FIELDNAMES = csv_store.RESULTS_FIELDNAMES
ALL_RESULTS_FIELDNAMES = ["username", "cluster", "image", "x", "y", "ra", "dec", "skipped", "flagged", "note", "updated_at"]
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "bcg-picker-dev-secret")
REVIEW_MARKER_COLORS = [
    "#e53935",
    "#1e88e5",
    "#43a047",
    "#8e24aa",
    "#fb8c00",
    "#00897b",
]
CATALOG_FILTER_ALL = "all"
CATALOG_FILTER_SKIPPED = "skipped"
CATALOG_FILTER_FLAGGED = "flagged"
VALID_CATALOG_FILTERS = {
    CATALOG_FILTER_ALL,
    CATALOG_FILTER_SKIPPED,
    CATALOG_FILTER_FLAGGED,
}
IMAGE_VARIANT_SPECS = [
    {
        "key": "nonotation",
        "label": "No Notation",
        "build_path": lambda stem, ext: f"with_nonotion/{stem}_nonotation{ext}",
    },
    {
        "key": "withnotation",
        "label": "With Notation",
        "build_path": lambda stem, ext: f"with_notation/{stem}_withnotation{ext}",
    },
    {
        "key": "member",
        "label": "Member",
        "build_path": lambda stem, ext: f"member/{stem}_member{ext}",
    },
]


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
    app.config["CATALOG_WITH_ORDER"] = [
        dict(row, catalog_order=index)
        for index, row in enumerate(rows)
    ]


def load_runtime_catalog(app):
    return load_catalog(app.config["DEFAULT_CATALOG_FILE"])


def get_current_username():
    return session.get("username")


def bootstrap_default_results(app):
    bootstrap_path = app.config.get("BOOTSTRAP_RESULTS_FILE", "")
    bootstrap_username = app.config.get("BOOTSTRAP_USERNAME", "").strip()
    if not bootstrap_path or not bootstrap_username:
        return

    if not os.path.exists(bootstrap_path):
        return

    if csv_store.results_file_exists(app.config["RESULTS_DIR"], bootstrap_username):
        return

    rows = csv_store.read_results_rows(bootstrap_path)
    if not rows:
        return

    normalized_rows = csv_store.normalize_imported_results_rows(
        rows,
        fallback_username=bootstrap_username,
    )
    csv_store.import_results_rows(
        app.config["RESULTS_DIR"],
        app.config["IMPORTS_DIR"],
        bootstrap_username,
        normalized_rows,
        replace=False,
    )


def get_catalog_filter_mode():
    filter_mode = session.get("catalog_filter", CATALOG_FILTER_ALL)
    if filter_mode not in VALID_CATALOG_FILTERS:
        return CATALOG_FILTER_ALL
    return filter_mode


def get_existing_usernames():
    return list_result_usernames(current_app.config["RESULTS_DIR"])


def get_catalog_maps(rows):
    return {
        "index": {
            row["cluster"]: index
            for index, row in enumerate(rows)
        },
        "by_cluster": {
            row["cluster"]: row
            for row in rows
        },
    }


def get_visible_catalog(username=None, filter_mode=None):
    selected_username = username if username is not None else get_current_username()
    selected_filter = filter_mode or get_catalog_filter_mode()

    if selected_filter == CATALOG_FILTER_ALL:
        return get_catalog()

    if not selected_username:
        return []

    return csv_store.fetch_catalog_rows_for_user_filter(
        current_app.config["RESULTS_DIR"],
        selected_username,
        selected_filter,
        get_catalog(),
    )


def get_filtered_next_cluster(rows, current_cluster, current_index):
    if not rows:
        return None

    for index, row in enumerate(rows):
        if row["cluster"] != current_cluster:
            continue

        if index + 1 < len(rows):
            return rows[index + 1]["cluster"]
        if index > 0:
            return rows[index - 1]["cluster"]
        return rows[index]["cluster"]

    if current_index is not None:
        bounded_index = max(0, min(current_index, len(rows) - 1))
        return rows[bounded_index]["cluster"]

    return rows[0]["cluster"]


def build_user_summary():
    total = len(get_catalog())
    current_user = get_current_username()
    if not current_user:
        return {"current": None}

    progress = csv_store.get_user_progress(current_app.config["RESULTS_DIR"], current_user)
    return {
        "current": {
            "username": current_user,
            "done": progress["done"],
            "skipped": progress["skipped"],
            "flagged": progress["flagged"],
            "remaining": total - progress["done"] - progress["skipped"] - progress["flagged"],
        }
    }


def build_review_summary(review_groups):
    total_clusters = len(review_groups)
    disagreement_count = sum(1 for group in review_groups if group["has_disagreement"])
    return {
        "annotated_clusters": total_clusters,
        "disagreement_clusters": disagreement_count,
        "agreement_clusters": total_clusters - disagreement_count,
    }


def get_catalog_order_lookup():
    return {
        row["cluster"]: row
        for row in current_app.config.get("CATALOG_WITH_ORDER", [])
    }


def add_review_marker_colors(review_group):
    if review_group is None:
        return None

    colored_annotations = []
    for index, annotation in enumerate(review_group["annotations"]):
        colored_annotation = dict(annotation)
        colored_annotation["marker_color"] = REVIEW_MARKER_COLORS[index % len(REVIEW_MARKER_COLORS)]
        colored_annotations.append(colored_annotation)

    review_group = dict(review_group)
    review_group["annotations"] = colored_annotations
    return review_group


def build_image_variants(image_name):
    stem, ext = os.path.splitext(image_name)
    variants = []

    for spec in IMAGE_VARIANT_SPECS:
        relative_path = spec["build_path"](stem, ext)
        absolute_path = os.path.join(IMAGES_DIR, relative_path)
        if not os.path.exists(absolute_path):
            continue
        variants.append({
            "key": spec["key"],
            "label": spec["label"],
            "path": relative_path,
        })

    return variants


def enrich_galaxy(row):
    enriched = dict(row)
    enriched["image_variants"] = build_image_variants(row["image"])
    enriched["primary_image_variant"] = (
        enriched["image_variants"][0]
        if enriched["image_variants"]
        else None
    )
    return enriched


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["DEFAULT_CATALOG_FILE"] = DEFAULT_CATALOG_FILE
    app.config["BOOTSTRAP_RESULTS_FILE"] = DEFAULT_BOOTSTRAP_RESULTS_FILE
    app.config["BOOTSTRAP_USERNAME"] = DEFAULT_BOOTSTRAP_USERNAME
    app.config["UPLOADED_CATALOG_FILE"] = UPLOADED_CATALOG_FILE
    app.config["RESULTS_DIR"] = RESULTS_DIR
    app.config["IMPORTS_DIR"] = IMPORTS_DIR
    app.config["COMBINED_DIR"] = COMBINED_DIR
    app.config["SECRET_KEY"] = SECRET_KEY
    if test_config:
        app.config.update(test_config)
    ensure_csv_storage_dirs(
        app.config["RESULTS_DIR"],
        app.config["IMPORTS_DIR"],
        app.config["COMBINED_DIR"],
    )
    bootstrap_default_results(app)
    set_catalog(app, load_runtime_catalog(app))

    @app.before_request
    def ensure_default_user():
        if get_current_username():
            return

        bootstrap_username = current_app.config.get("BOOTSTRAP_USERNAME", "").strip()
        if not bootstrap_username:
            return

        if bootstrap_username not in get_existing_usernames():
            return

        session["username"] = bootstrap_username

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
            set_catalog(current_app, rows)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        return jsonify({
            "status": "ok",
            "total": len(get_catalog())
        })

    @app.route("/import_results", methods=["POST"])
    def import_results():
        file = request.files.get("file")
        replace_existing = request.form.get("replace_existing", "").strip().lower() == "true"

        if not file:
            return jsonify({"status": "error", "message": "No results CSV uploaded"}), 400

        try:
            rows = csv_store.read_uploaded_results_file(file)
            username = csv_store.detect_results_username(rows)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        if csv_store.results_file_exists(current_app.config["RESULTS_DIR"], username) and not replace_existing:
            return jsonify({
                "status": "error",
                "message": (
                    f'Results for user "{username}" already exist. '
                    "Import again with replace enabled to overwrite them."
                ),
                "collision": True,
                "username": username,
            }), 409

        try:
            csv_store.import_results_rows(
                current_app.config["RESULTS_DIR"],
                current_app.config["IMPORTS_DIR"],
                username,
                rows,
                replace=replace_existing,
            )
        except FileExistsError:
            return jsonify({
                "status": "error",
                "message": f'Results for user "{username}" already exist.',
                "collision": True,
                "username": username,
            }), 409

        return jsonify({
            "status": "ok",
            "username": username,
            "rows_imported": len(rows),
            "replaced": replace_existing,
        })

    @app.route("/reset_catalog", methods=["POST"])
    def reset_catalog():
        set_catalog(current_app, load_catalog(current_app.config["DEFAULT_CATALOG_FILE"]))

        return jsonify({
            "status": "ok",
            "total": len(get_catalog())
        })

    @app.route("/")
    def home():
        return redirect(url_for("index", index=0))

    @app.route("/<int:index>")
    def index(index):
        catalog = get_visible_catalog()
        if not catalog:
            return render_template(
                "index.html",
                galaxy=None,
                index=0,
                total=0,
                current_user=get_current_username(),
                existing_users=get_existing_usernames(),
                user_summary=build_user_summary(),
                catalog_filter_mode=get_catalog_filter_mode(),
            )

        if index < 0 or index >= len(catalog):
            return "Cluster index out of range", 404

        galaxy = enrich_galaxy(catalog[index])
        return render_template(
            "index.html",
            galaxy=galaxy,
            index=index,
            total=len(catalog),
            current_user=get_current_username(),
            existing_users=get_existing_usernames(),
            user_summary=build_user_summary(),
            catalog_filter_mode=get_catalog_filter_mode(),
        )

    @app.route("/cluster/<cluster>")
    def cluster(cluster):
        catalog = get_visible_catalog()
        if not catalog:
            return render_template(
                "index.html",
                galaxy=None,
                index=0,
                total=0,
                current_user=get_current_username(),
                existing_users=get_existing_usernames(),
                user_summary=build_user_summary(),
                catalog_filter_mode=get_catalog_filter_mode(),
            )

        catalog_maps = get_catalog_maps(catalog)
        galaxy = catalog_maps["by_cluster"].get(cluster)
        if galaxy is None:
            return redirect(url_for("cluster", cluster=catalog[0]["cluster"]))
        index = catalog_maps["index"][cluster]
        galaxy = enrich_galaxy(galaxy)
        return render_template(
            "index.html",
            galaxy=galaxy,
            index=index,
            total=len(catalog),
            current_user=get_current_username(),
            existing_users=get_existing_usernames(),
            user_summary=build_user_summary(),
            catalog_filter_mode=get_catalog_filter_mode(),
        )

    @app.route("/set_catalog_filter", methods=["POST"])
    def set_catalog_filter():
        data = request.get_json(silent=True) or request.form
        filter_mode = data.get("filter_mode", CATALOG_FILTER_ALL)
        current_cluster = data.get("cluster")

        if filter_mode not in VALID_CATALOG_FILTERS:
            return jsonify({
                "status": "error",
                "message": "Unsupported catalog filter"
            }), 400

        if filter_mode != CATALOG_FILTER_ALL and not get_current_username():
            return jsonify({
                "status": "error",
                "message": "Set a user before filtering skipped or flagged objects"
            }), 400

        session["catalog_filter"] = filter_mode
        catalog = get_visible_catalog(filter_mode=filter_mode)

        next_url = url_for("index", index=0)
        if current_cluster and any(row["cluster"] == current_cluster for row in catalog):
            next_url = url_for("cluster", cluster=current_cluster)
        elif catalog:
            next_url = url_for("cluster", cluster=catalog[0]["cluster"])

        return jsonify({
            "status": "ok",
            "filter_mode": filter_mode,
            "total": len(catalog),
            "next_url": next_url,
        })

    @app.route("/images/<path:filename>")
    def images(filename):
        return send_from_directory(IMAGES_DIR, filename)

    @app.route("/download_results")
    def download_results():
        username = get_current_username()
        if not username:
            return jsonify({
                "status": "error",
                "message": "Set a user before downloading results"
            }), 400

        rows = csv_store.export_user_annotations(current_app.config["RESULTS_DIR"], username)
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
                "Content-Disposition": (
                    f"attachment; filename={csv_store.build_results_filename(username)}"
                )
            },
        )

    @app.route("/download_catalog_subset/<filter_mode>")
    def download_catalog_subset(filter_mode):
        username = get_current_username()
        if not username:
            return jsonify({
                "status": "error",
                "message": "Set a user before downloading a filtered catalog"
            }), 400

        if filter_mode not in {CATALOG_FILTER_SKIPPED, CATALOG_FILTER_FLAGGED}:
            return jsonify({
                "status": "error",
                "message": "Unsupported catalog subset"
            }), 400

        rows = csv_store.fetch_catalog_rows_for_user_filter(
            current_app.config["RESULTS_DIR"],
            username,
            filter_mode,
            get_catalog(),
        )
        if not rows:
            label = "skipped" if filter_mode == CATALOG_FILTER_SKIPPED else "flagged"
            return jsonify({
                "status": "error",
                "message": f"No {label} objects available yet for this user"
            }), 404

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CATALOG_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": (
                    f"attachment; filename={username}_{filter_mode}_catalog.csv"
                )
            },
        )

    @app.route("/reset_user_results", methods=["POST"])
    def reset_user_results():
        username = get_current_username()
        if not username:
            return jsonify({
                "status": "error",
                "message": "Set a user before resetting results"
            }), 400

        csv_store.reset_annotations(current_app.config["RESULTS_DIR"], username)
        return jsonify({
            "status": "ok",
            "username": username,
        })

    @app.route("/download_all_results")
    def download_all_results():
        _, rows = csv_store.generate_combined_results(
            current_app.config["RESULTS_DIR"],
            current_app.config["COMBINED_DIR"],
        )
        if not rows:
            return jsonify({
                "status": "error",
                "message": "No annotations available yet"
            }), 404

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=ALL_RESULTS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=all_results.csv"
            },
        )

    @app.route("/admin/review")
    def admin_review():
        _, rows = csv_store.generate_combined_results(
            current_app.config["RESULTS_DIR"],
            current_app.config["COMBINED_DIR"],
        )
        review_groups = csv_store.build_review_groups(rows, get_catalog_order_lookup())
        return render_template(
            "admin_review.html",
            review_groups=review_groups,
            review_summary=build_review_summary(review_groups),
        )

    @app.route("/admin/review/<cluster>")
    def admin_review_cluster(cluster):
        _, rows = csv_store.generate_combined_results(
            current_app.config["RESULTS_DIR"],
            current_app.config["COMBINED_DIR"],
        )
        review_group = None
        for group in csv_store.build_review_groups(rows, get_catalog_order_lookup()):
            if group["cluster"] == cluster:
                review_group = group
                break
        review_group = add_review_marker_colors(review_group)
        if review_group is None:
            return "Cluster not found", 404

        galaxy = current_app.config["CATALOG_BY_CLUSTER"].get(cluster)
        if galaxy is None:
            return "Cluster not found", 404

        return render_template(
            "admin_review_cluster.html",
            review_group=review_group,
            galaxy=galaxy,
        )

    @app.route("/next_unannotated")
    def next_unannotated():
        username = get_current_username()
        if not username:
            return jsonify({
                "status": "error",
                "message": "Set a user before jumping to the next unannotated cluster"
            }), 400

        cluster_name = csv_store.get_next_unannotated_cluster(
            current_app.config["RESULTS_DIR"],
            username,
            get_catalog(),
        )
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
        flagged = bool(data.get("flagged", False))
        if skipped and flagged:
            return jsonify({
                "status": "error",
                "message": "An annotation cannot be skipped and flagged at the same time"
            }), 400

        if not skipped and not flagged:
            required_fields = ("image", "x", "y", "ra", "dec")
            missing_fields = [field for field in required_fields if data.get(field) in (None, "")]
            if missing_fields:
                return jsonify({
                    "status": "error",
                    "message": f"Missing fields: {', '.join(missing_fields)}"
                }), 400

        existing_row = csv_store.get_annotation_by_cluster(
            current_app.config["RESULTS_DIR"],
            username,
            cluster_name,
        )
        updated = existing_row is not None

        annotation = {
            "cluster": cluster_name,
            "image": data.get("image", ""),
            "x": None if skipped or flagged else data.get("x"),
            "y": None if skipped or flagged else data.get("y"),
            "ra": None if skipped or flagged else data.get("ra"),
            "dec": None if skipped or flagged else data.get("dec"),
            "skipped": skipped,
            "flagged": flagged,
            "note": (data.get("note") or "").strip(),
        }

        try:
            csv_store.upsert_annotation(current_app.config["RESULTS_DIR"], username, annotation)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        filter_mode = get_catalog_filter_mode()
        if filter_mode == CATALOG_FILTER_ALL:
            next_cluster = csv_store.get_next_unannotated_cluster(
                current_app.config["RESULTS_DIR"],
                username,
                get_catalog(),
            )
        else:
            current_index = data.get("index")
            if not isinstance(current_index, int):
                current_index = None
            visible_catalog = get_visible_catalog(username=username, filter_mode=filter_mode)
            next_cluster = get_filtered_next_cluster(visible_catalog, cluster_name, current_index)
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

        row = csv_store.get_annotation_by_cluster(
            current_app.config["RESULTS_DIR"],
            username,
            cluster,
        )
        if row is not None:
            if csv_store.parse_bool(row["skipped"]):
                return jsonify({
                    "exists": True,
                    "skipped": True,
                    "note": row.get("note", ""),
                })

            if csv_store.parse_bool(row["flagged"]):
                return jsonify({
                    "exists": True,
                    "skipped": False,
                    "flagged": True,
                    "note": row.get("note", ""),
                })

            return jsonify({
                "exists": True,
                "skipped": False,
                "flagged": False,
                "x": float(row["x"]) if row["x"] not in ("", None) else None,
                "y": float(row["y"]) if row["y"] not in ("", None) else None,
                "ra": float(row["ra"]) if row["ra"] not in ("", None) else None,
                "dec": float(row["dec"]) if row["dec"] not in ("", None) else None,
                "note": row.get("note", ""),
            })

        return jsonify({"exists": False})

    @app.route("/progress")
    def progress():
        total = len(get_catalog())
        username = get_current_username()
        if username:
            progress_data = csv_store.get_user_progress(current_app.config["RESULTS_DIR"], username)
            done = progress_data["done"]
            skipped = progress_data["skipped"]
            flagged = progress_data["flagged"]
        else:
            done = 0
            skipped = 0
            flagged = 0

        return jsonify({
            "total": total,
            "done": done,
            "skipped": skipped,
            "flagged": flagged,
            "remaining": total - done - skipped - flagged
        })

    return app


app = create_app()


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    app.run(host=host, port=port, debug=debug_enabled)
