from flask import Flask, render_template, send_from_directory
from flask import request, jsonify

import csv
import os

catalog = []
RESULTS_FILE = "data/results.csv"

with open("data/catalog.csv") as f:
    reader = csv.DictReader(f)
    catalog = list(reader)

app = Flask(__name__)

@app.route("/")
def index():
    print("Index route reached!")
    i = 0
    galaxy = catalog[i]
    return render_template("index.html",galaxy=galaxy,index=i,total=len(catalog))

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
            row["image"] = data["image"]
            row["x"] = data["x"]
            row["y"] = data["y"]
            row["ra"] = data["ra"]
            row["dec"] = data["dec"]

            updated = True
            break

    # Otherwise append a new one
    if not updated:
        rows.append({
            "cluster": data["cluster"],
            "image": data["image"],
            "x": data["x"],
            "y": data["y"],
            "ra": data["ra"],
            "dec": data["dec"],
        })

    # Rewrite the entire CSV
    with open(RESULTS_FILE, "w", newline="") as f:

        writer = csv.DictWriter(f,fieldnames=["cluster", "image", "x", "y", "ra", "dec"])
        writer.writeheader()
        writer.writerows(rows)

    return jsonify({
        "status": "ok",
        "updated": updated
    })

@app.route("/load/<cluster>")
def load(cluster):

    if not os.path.exists(RESULTS_FILE):
        return jsonify({"exists": False})

    with open(RESULTS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["cluster"] == cluster:
                return jsonify({
                    "exists": True,"x": float(row["x"]),
                    "y": float(row["y"]),
                    "ra": float(row["ra"]),
                    "dec": float(row["dec"])
                })

    return jsonify({"exists": False})


if __name__ == "__main__":
    app.run(debug=True)
    