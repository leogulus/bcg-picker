import csv
import importlib
import os
import tempfile
import unittest

try:
    app_module = importlib.import_module("app")
    IMPORT_ERROR = None
except ModuleNotFoundError as error:
    app_module = None
    IMPORT_ERROR = error


@unittest.skipIf(IMPORT_ERROR is not None, f"Missing dependency: {IMPORT_ERROR}")
class BCGPickerAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.catalog_path = os.path.join(self.temp_dir.name, "catalog.csv")
        self.upload_path = os.path.join(self.temp_dir.name, "uploaded_catalog.csv")
        self.database_path = os.path.join(self.temp_dir.name, "bcg_picker.sqlite3")
        self.schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "schema.sql",
        )

        with open(self.catalog_path, "w", newline="") as file_obj:
            writer = csv.DictWriter(
                file_obj,
                fieldnames=["cluster", "image", "ra", "dec", "redshift", "pixscale"],
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "cluster": "Cluster0000",
                        "image": "cluster000.jpg",
                        "ra": "3.1",
                        "dec": "-32.9",
                        "redshift": "0.25",
                        "pixscale": "0.262",
                    },
                    {
                        "cluster": "Cluster0001",
                        "image": "cluster001.jpg",
                        "ra": "6.5",
                        "dec": "-32.6",
                        "redshift": "0.43",
                        "pixscale": "0.262",
                    },
                ]
            )

        self.app = app_module.create_app({
            "TESTING": True,
            "DEFAULT_CATALOG_FILE": self.catalog_path,
            "UPLOADED_CATALOG_FILE": self.upload_path,
            "DATABASE_PATH": self.database_path,
            "DATABASE_SCHEMA": self.schema_path,
            "SECRET_KEY": "test-secret",
        })
        app_module.set_catalog(self.app, app_module.load_catalog(self.catalog_path))
        self.client = self.app.test_client()

        with self.app.app_context():
            app_module.replace_catalog_rows(
                app_module.load_catalog(self.catalog_path),
                self.app.config["DEFAULT_CATALOG_SOURCE"],
            )

        with self.client.session_transaction() as session:
            session["username"] = "tester"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_annotation(self):
        response = self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 100.5,
                "y": 120.5,
                "ra": 3.123,
                "dec": -32.987,
                "index": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["next_url"], "/1")

        load_response = self.client.get("/load/Cluster0000")
        self.assertEqual(load_response.status_code, 200)
        self.assertEqual(
            load_response.get_json(),
            {
                "exists": True,
                "skipped": False,
                "x": 100.5,
                "y": 120.5,
                "ra": 3.123,
                "dec": -32.987,
            },
        )

    def test_skip_updates_progress(self):
        response = self.client.post(
            "/save",
            json={
                "cluster": "Cluster0001",
                "image": "cluster001.jpg",
                "skipped": True,
                "index": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["next_url"])

        progress_response = self.client.get("/progress")
        self.assertEqual(
            progress_response.get_json(),
            {
                "total": 2,
                "done": 0,
                "skipped": 1,
                "remaining": 1,
            },
        )

    def test_save_rejects_missing_fields(self):
        response = self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 100.5,
                "index": 0,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing fields", response.get_json()["message"])

    def test_invalid_index_returns_404(self):
        response = self.client.get("/99")
        self.assertEqual(response.status_code, 404)

    def test_save_requires_user(self):
        with self.client.session_transaction() as session:
            session.pop("username", None)

        response = self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 100.5,
                "y": 120.5,
                "ra": 3.123,
                "dec": -32.987,
                "index": 0,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Set a user", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
