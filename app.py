from flask import Flask, current_app, jsonify, redirect, render_template, request
from flask import send_from_directory, url_for

import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(BASE_DIR, "data", "results.csv")
DEFAULT_CATALOG_FILE = os.path.join(BASE_DIR, "data", "catalog.csv")
UPLOADED_CATALOG_FILE = os.path.join(BASE_DIR, "data", "uploaded_catalog.csv")
CATALOG_FIELDS = {"cluster", "image", "ra", "dec", "redshift", "pixscale"}
RESULTS_FIELDNAMES = ["cluster", "image", "x", "y", "ra", "dec", "skipped"]


def read_csv_rows(path):
    with open(path, newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def read_results():
    results_file = current_app.config["RESULTS_FILE"]
    if not os.path.exists(results_file):
        return []
    return read_csv_rows(results_file)


def write_results(rows):
    results_file = current_app.config["RESULTS_FILE"]
    with open(results_file, "w", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=RESULTS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


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


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["RESULTS_FILE"] = RESULTS_FILE
    app.config["DEFAULT_CATALOG_FILE"] = DEFAULT_CATALOG_FILE
    app.config["UPLOADED_CATALOG_FILE"] = UPLOADED_CATALOG_FILE
    app.config["CATALOG"] = load_catalog(DEFAULT_CATALOG_FILE)

    @app.route("/upload_catalog", methods=["POST"])
    def upload_catalog():
        file = request.files.get("file")

        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        upload_path = current_app.config["UPLOADED_CATALOG_FILE"]
        file.save(upload_path)

        try:
            current_app.config["CATALOG"] = load_catalog(upload_path)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        return jsonify({
            "status": "ok",
            "total": len(get_catalog())
        })

    @app.route("/reset_catalog", methods=["POST"])
    def reset_catalog():
        default_catalog_file = current_app.config["DEFAULT_CATALOG_FILE"]
        current_app.config["CATALOG"] = load_catalog(default_catalog_file)

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
        return render_template("index.html", galaxy=galaxy, index=index, total=len(catalog))

    @app.route("/cluster/<cluster>")
    def cluster(cluster):
        catalog = get_catalog()
        galaxy = next(
            (g for g in catalog if g["cluster"] == cluster),
            None
        )
        if galaxy is None:
            return "Cluster not found", 404
        index = catalog.index(galaxy)
        return render_template(
            "index.html",
            galaxy=galaxy,
            index=index,
            total=len(catalog)
        )

    @app.route("/images/<filename>")
    def images(filename):
        return send_from_directory(os.path.join(BASE_DIR, "images"), filename)

    @app.route("/save", methods=["POST"])
    def save():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

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

        rows = read_results()
        updated = False

        for row in rows:
            if row["cluster"] == cluster_name:
                row["image"] = data.get("image", row["image"])
                row["x"] = data.get("x", "")
                row["y"] = data.get("y", "")
                row["ra"] = data.get("ra", "")
                row["dec"] = data.get("dec", "")
                row["skipped"] = str(skipped)
                updated = True
                break

        if not updated:
            rows.append({
                "cluster": cluster_name,
                "image": data.get("image", ""),
                "x": data.get("x", ""),
                "y": data.get("y", ""),
                "ra": data.get("ra", ""),
                "dec": data.get("dec", ""),
                "skipped": str(skipped),
            })

        write_results(rows)

        current_index = data.get("index")
        catalog = get_catalog()
        if isinstance(current_index, int) and current_index < len(catalog) - 1:
            next_url = url_for("index", index=current_index + 1)
        else:
            next_url = None

        return jsonify({
            "status": "ok",
            "updated": updated,
            "next_url": next_url
        })

    @app.route("/load/<cluster>")
    def load(cluster):
        for row in read_results():
            if row["cluster"] == cluster:
                if row.get("skipped", "False") == "True":
                    return jsonify({
                        "exists": True,
                        "skipped": True
                    })

                return jsonify({
                    "exists": True,
                    "skipped": False,
                    "x": float(row["x"]) if row["x"] else None,
                    "y": float(row["y"]) if row["y"] else None,
                    "ra": float(row["ra"]) if row["ra"] else None,
                    "dec": float(row["dec"]) if row["dec"] else None,
                })

        return jsonify({"exists": False})

    @app.route("/progress")
    def progress():
        total = len(get_catalog())
        done = 0
        skipped = 0

        for row in read_results():
            if row.get("skipped", "False") == "True":
                skipped += 1
            elif row.get("x"):
                done += 1

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
