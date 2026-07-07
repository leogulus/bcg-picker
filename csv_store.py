import csv
import math
import shutil
import os
import re
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile


RESULTS_FIELDNAMES = [
    "username",
    "cluster",
    "image",
    "x",
    "y",
    "ra",
    "dec",
    "skipped",
    "flagged",
    "updated_at",
]
LEGACY_RESULTS_FIELDNAMES = [
    "cluster",
    "image",
    "x",
    "y",
    "ra",
    "dec",
    "skipped",
    "flagged",
]
COMBINED_RESULTS_FILENAME = "all_results.csv"
REVIEW_CONFLICT_THRESHOLD_DEG = 1.5 / 3600.0


def sanitize_username(username):
    cleaned = re.sub(r"\s+", "_", username.strip())
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned.lower()


def build_results_filename(username):
    sanitized = sanitize_username(username)
    if not sanitized:
        raise ValueError("Username must contain at least one valid filename character")
    return f"{sanitized}_results.csv"


def infer_username_from_results_filename(filename):
    basename = os.path.basename(filename or "")
    if basename.lower().endswith("_results.csv"):
        stem = basename[:-12]
        if stem:
            return stem.replace("_", " ")
    return ""


def build_results_path(results_dir, username):
    return os.path.join(results_dir, build_results_filename(username))


def ensure_csv_storage_dirs(results_dir, imports_dir, combined_dir):
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(imports_dir, exist_ok=True)
    os.makedirs(combined_dir, exist_ok=True)


def list_result_usernames(results_dir):
    if not os.path.isdir(results_dir):
        return []

    discovered = {}
    for entry in sorted(os.listdir(results_dir)):
        if not entry.endswith("_results.csv"):
            continue

        path = os.path.join(results_dir, entry)
        if not os.path.isfile(path):
            continue

        rows = read_results_rows(path)
        if rows and rows[0].get("username"):
            username = rows[0]["username"].strip()
            if username:
                discovered[username.lower()] = username
                continue

        stem = entry[:-12]
        if stem:
            discovered[stem.lower()] = stem

    return sorted(discovered.values(), key=lambda value: (value.lower(), value))


def read_results_rows(path):
    if not os.path.exists(path):
        return []

    with open(path, newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def write_results_rows(path, rows, fieldnames=None):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    target_fieldnames = fieldnames or RESULTS_FIELDNAMES
    with NamedTemporaryFile("w", newline="", delete=False, dir=directory or None) as temp_file:
        writer = csv.DictWriter(temp_file, fieldnames=target_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        temp_path = temp_file.name

    os.replace(temp_path, path)


def parse_bool(value):
    return str(value).strip().lower() == "true"


def get_timestamp_string():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_annotation_rows(results_dir, username):
    return read_results_rows(build_results_path(results_dir, username))


def get_annotation_by_cluster(results_dir, username, cluster_name):
    for row in get_annotation_rows(results_dir, username):
        if row.get("cluster") == cluster_name:
            return row
    return None


def upsert_annotation(results_dir, username, annotation):
    rows = get_annotation_rows(results_dir, username)
    updated_at = get_timestamp_string()
    normalized_row = {
        "username": username,
        "cluster": annotation["cluster"],
        "image": annotation.get("image", ""),
        "x": "" if annotation.get("x") is None else annotation.get("x"),
        "y": "" if annotation.get("y") is None else annotation.get("y"),
        "ra": "" if annotation.get("ra") is None else annotation.get("ra"),
        "dec": "" if annotation.get("dec") is None else annotation.get("dec"),
        "skipped": "True" if annotation.get("skipped") else "False",
        "flagged": "True" if annotation.get("flagged") else "False",
        "updated_at": updated_at,
    }

    replaced = False
    for index, row in enumerate(rows):
        if row.get("cluster") == annotation["cluster"]:
            rows[index] = normalized_row
            replaced = True
            break

    if not replaced:
        rows.append(normalized_row)

    write_results_rows(build_results_path(results_dir, username), rows)
    return normalized_row


def reset_annotations(results_dir, username):
    path = build_results_path(results_dir, username)
    write_results_rows(path, [])


def export_user_annotations(results_dir, username):
    rows = get_annotation_rows(results_dir, username)
    return [
        {
            "username": row["username"],
            "cluster": row["cluster"],
            "image": row["image"],
            "x": row["x"],
            "y": row["y"],
            "ra": row["ra"],
            "dec": row["dec"],
            "skipped": row["skipped"],
            "flagged": row["flagged"],
            "updated_at": row.get("updated_at", ""),
        }
        for row in rows
    ]


def get_user_progress(results_dir, username):
    rows = get_annotation_rows(results_dir, username)
    done = 0
    skipped = 0
    flagged = 0
    for row in rows:
        if parse_bool(row["skipped"]):
            skipped += 1
        elif parse_bool(row["flagged"]):
            flagged += 1
        elif row["x"] not in ("", None):
            done += 1

    return {
        "done": done,
        "skipped": skipped,
        "flagged": flagged,
    }


def get_next_unannotated_cluster(results_dir, username, catalog_rows):
    seen_clusters = {
        row["cluster"]
        for row in get_annotation_rows(results_dir, username)
    }
    for row in catalog_rows:
        if row["cluster"] not in seen_clusters:
            return row["cluster"]
    return None


def fetch_catalog_rows_for_user_filter(results_dir, username, filter_mode, catalog_rows):
    if filter_mode not in {"skipped", "flagged"}:
        raise ValueError("Unsupported catalog filter mode")

    annotations = {
        row["cluster"]: row
        for row in get_annotation_rows(results_dir, username)
    }
    filtered_rows = []
    for row in catalog_rows:
        annotation = annotations.get(row["cluster"])
        if annotation is None:
            continue
        if filter_mode == "skipped" and parse_bool(annotation["skipped"]):
            filtered_rows.append(row)
        if filter_mode == "flagged" and parse_bool(annotation["flagged"]):
            filtered_rows.append(row)
    return filtered_rows


def collect_all_annotations(results_dir):
    rows = []
    for username in list_result_usernames(results_dir):
        rows.extend(get_annotation_rows(results_dir, username))
    rows.sort(key=lambda row: (
        row.get("username", "").lower(),
        row.get("username", ""),
        row.get("cluster", ""),
    ))
    return rows


def build_combined_results_path(combined_dir):
    return os.path.join(combined_dir, COMBINED_RESULTS_FILENAME)


def validate_results_rows(rows):
    if not rows:
        raise ValueError("Results file is empty")

    missing = [
        field
        for field in RESULTS_FIELDNAMES
        if field not in rows[0]
    ]
    if missing:
        raise ValueError(f"Results file is missing required columns: {', '.join(missing)}")


def is_legacy_results_rows(rows):
    if not rows:
        return False
    row_keys = set(rows[0].keys())
    return (
        "username" not in row_keys
        and all(field in row_keys for field in LEGACY_RESULTS_FIELDNAMES)
    )


def normalize_imported_results_rows(rows, fallback_username=""):
    if not rows:
        raise ValueError("Results file is empty")

    if is_legacy_results_rows(rows):
        normalized_username = fallback_username.strip()
        if not normalized_username:
            raise ValueError(
                "Results file is missing required columns: username, updated_at"
            )
        normalized_rows = []
        for row in rows:
            normalized_row = {
                "username": normalized_username,
                "cluster": row.get("cluster", ""),
                "image": row.get("image", ""),
                "x": row.get("x", ""),
                "y": row.get("y", ""),
                "ra": row.get("ra", ""),
                "dec": row.get("dec", ""),
                "skipped": row.get("skipped", "False") or "False",
                "flagged": row.get("flagged", "False") or "False",
                "updated_at": row.get("updated_at", "") or get_timestamp_string(),
            }
            normalized_rows.append(normalized_row)
        return normalized_rows

    validate_results_rows(rows)
    normalized_rows = []
    for row in rows:
        normalized_row = dict(row)
        if not normalized_row.get("updated_at"):
            normalized_row["updated_at"] = get_timestamp_string()
        normalized_rows.append(normalized_row)
    return normalized_rows


def read_uploaded_results_file(file_storage):
    file_storage.stream.seek(0)
    text_stream = file_storage.stream.read().decode("utf-8-sig")
    rows = list(csv.DictReader(text_stream.splitlines()))
    return normalize_imported_results_rows(
        rows,
        fallback_username=infer_username_from_results_filename(file_storage.filename),
    )


def detect_results_username(rows):
    usernames = {
        row.get("username", "").strip()
        for row in rows
        if row.get("username", "").strip()
    }
    if not usernames:
        raise ValueError("Results file does not contain a username")
    if len(usernames) > 1:
        raise ValueError("Results file contains more than one username")
    return next(iter(usernames))


def results_file_exists(results_dir, username):
    return os.path.exists(build_results_path(results_dir, username))


def import_results_rows(results_dir, imports_dir, username, rows, replace=False):
    results_path = build_results_path(results_dir, username)
    if os.path.exists(results_path) and not replace:
        raise FileExistsError("Results file already exists for this user")

    import_path = os.path.join(imports_dir, build_results_filename(username))
    write_results_rows(import_path, rows)
    shutil.copyfile(import_path, results_path)
    return results_path


def generate_combined_results(results_dir, combined_dir):
    rows = collect_all_annotations(results_dir)
    path = build_combined_results_path(combined_dir)
    write_results_rows(path, rows)
    return path, rows


def has_review_disagreement(annotations):
    if not annotations:
        return False

    states = {
        "skipped" if parse_bool(annotation["skipped"]) else
        "flagged" if parse_bool(annotation["flagged"]) else
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


def build_review_groups(annotation_rows, catalog_by_cluster):
    grouped = []
    current_cluster = None
    current_group = None
    decision_points = []

    sorted_rows = sorted(
        annotation_rows,
        key=lambda row: (
            catalog_by_cluster.get(row["cluster"], {}).get("catalog_order", 10 ** 9),
            row["cluster"],
            row["username"].lower(),
            row["username"],
        ),
    )

    for row in sorted_rows:
        cluster_name = row["cluster"]
        if cluster_name != current_cluster:
            if current_group is not None:
                current_group["has_disagreement"] = has_review_disagreement(decision_points)
                grouped.append(current_group)

            current_cluster = cluster_name
            galaxy = catalog_by_cluster.get(cluster_name, {})
            current_group = {
                "cluster": cluster_name,
                "image": galaxy.get("image", row.get("image", "")),
                "catalog_order": galaxy.get("catalog_order", 10 ** 9),
                "annotations": [],
                "has_disagreement": False,
            }
            decision_points = []

        annotation = {
            "username": row["username"],
            "x": row["x"],
            "y": row["y"],
            "ra": row["ra"],
            "dec": row["dec"],
            "skipped": parse_bool(row["skipped"]),
            "flagged": parse_bool(row["flagged"]),
            "updated_at": row.get("updated_at", ""),
        }
        current_group["annotations"].append(annotation)
        decision_points.append(annotation)

    if current_group is not None:
        current_group["has_disagreement"] = has_review_disagreement(decision_points)
        grouped.append(current_group)

    return grouped
