from flask import Flask, render_template, send_from_directory
from flask import request, jsonify
from flask import redirect, url_for

import csv
import os

catalog = []
RESULTS_FILE = "data/results.csv"

with open("data/catalog.csv") as f:
    reader = csv.DictReader(f)
    catalog = list(reader)

app = Flask(__name__)

@app.route("/")
def home():
    return redirect(url_for("index", index=0))

@app.route("/<int:index>")
def index(index):
    print("Index route reached!")
    i = index
    galaxy = catalog[i]
    return render_template("index.html",galaxy=galaxy,index=i,total=len(catalog))

@app.route("/cluster/<cluster>")
def cluster(cluster):
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
    return send_from_directory("images", filename)

@app.route("/save", methods=["POST"])
def save():

    data = request.json
    rows = []
    # Read existing results if they exist
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    updated = False

    # Replace existing cluster if found
    for row in rows:
        if row["cluster"] == data["cluster"]:
            row["image"] = data.get("image", row["image"])
            row["x"] = data.get("x", "")
            row["y"] = data.get("y", "")
            row["ra"] = data.get("ra", "")
            row["dec"] = data.get("dec", "")
            row["skipped"] = str(data.get("skipped", False))

            updated = True
            break

    # Otherwise append a new one
    if not updated:
        rows.append({
            "cluster": data["cluster"],
            "image": data.get("image", ""),
            "x": data.get("x", ""),
            "y": data.get("y", ""),
            "ra": data.get("ra", ""),
            "dec": data.get("dec", ""),
            "skipped": str(data.get("skipped", False)),
        })

    # Rewrite the entire CSV
    with open(RESULTS_FILE, "w", newline="") as f:

        writer = csv.DictWriter(f, fieldnames=["cluster", "image", "x", "y", "ra", "dec", "skipped"])
        writer.writeheader()
        writer.writerows(rows)

    current_index = data["index"]
    if current_index < len(catalog) - 1:
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
    print("LOAD HIT:", cluster)
    if not os.path.exists(RESULTS_FILE):
        return jsonify({"exists": False})

    with open(RESULTS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["cluster"] == cluster:
                return jsonify({
                    "exists": True,
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "ra": float(row["ra"]),
                    "dec": float(row["dec"])
                })

    return jsonify({"exists": False})

@app.route("/progress")
def progress():

    total = len(catalog)
    done = 0
    skipped = 0

    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
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

if __name__ == "__main__":
    app.run(debug=True)
    