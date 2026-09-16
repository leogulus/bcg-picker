"""Build the static guest site for Nginx deployment."""
import json
import shutil
from pathlib import Path

import app as app_module
import csv_store

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist" / "bcg-picker"

def write_page(client, index, output_directory=None):
    response = client.get(f"/{index}")
    if response.status_code != 200:
        raise RuntimeError(f"Could not render cluster {index}")
    prefix = "" if output_directory is None else "../"
    html = response.get_data(as_text=True)
    html = html.replace("href=\"/static/", f"href=\"{prefix}static/")
    html = html.replace("src=\"/images/", f"src=\"{prefix}images/")
    html = html.replace("src=\"/static/", f"src=\"{prefix}static/")
    html = html.replace("const exampleResultsUrl = \"/example_results\";", f"const exampleResultsUrl = \"{prefix}data/example_results.json\";")
    html = html.replace("const assetPrefix = \"/\";\nconst pageUrl = (index) => \"/\" + index;", f"const assetPrefix = \"{prefix}\";\nconst pageUrl = (targetIndex) => \"{prefix}\" + targetIndex + \"/\";")
    target = OUTPUT / "index.html" if output_directory is None else OUTPUT / str(output_directory) / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)

def main():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    shutil.copytree(ROOT / "static", OUTPUT / "static")
    (OUTPUT / "data").mkdir()
    rows = csv_store.read_results_rows(app_module.DEFAULT_EXAMPLE_RESULTS_FILE)
    (OUTPUT / "data" / "example_results.json").write_text(json.dumps({"status": "ok", "annotations": rows}))
    with app_module.app.test_client() as client:
        write_page(client, 0)
        for index in range(len(app_module.app.config["CATALOG"])):
            write_page(client, index, output_directory=index)
    print(f"Built {len(app_module.app.config[chr(67)+chr(65)+chr(84)+chr(65)+chr(76)+chr(79)+chr(71)])} pages in {OUTPUT}")

if __name__ == "__main__":
    main()
