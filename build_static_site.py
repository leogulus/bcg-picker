"""Build the static guest site and optionally copy it to an Nginx web directory."""
import argparse
import json
import os
import shutil
from pathlib import Path

import app as app_module
import csv_store

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist" / "bcg-picker"
DEFAULT_DEPLOY_DIR = "/srv/www/bcg-picker"

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

def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deploy-dir",
        default=os.environ.get("BCG_PICKER_STATIC_DEPLOY_DIR", DEFAULT_DEPLOY_DIR),
        help=(
            "Directory served by Nginx for /bcg-picker/. Defaults to "
            "/srv/www/bcg-picker, or BCG_PICKER_STATIC_DEPLOY_DIR when set."
        ),
    )
    return parser.parse_args()


def deploy_site(destination):
    deploy_directory = Path(destination).expanduser().resolve()
    if deploy_directory == OUTPUT.resolve():
        raise ValueError("The deployment directory must be different from the build output directory.")

    deploy_directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(OUTPUT, deploy_directory, dirs_exist_ok=True)
    print(f"Published static site to {deploy_directory}")


def main():
    arguments = parse_arguments()
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
    print(f"Built {len(app_module.app.config['CATALOG'])} pages in {OUTPUT}")
    if arguments.deploy_dir:
        deploy_site(arguments.deploy_dir)

if __name__ == "__main__":
    main()
