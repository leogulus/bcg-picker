import csv
import importlib
import io
import os
import tempfile
import unittest

import csv_store

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
        self.results_dir = os.path.join(self.temp_dir.name, "results")
        self.imports_dir = os.path.join(self.temp_dir.name, "imports")
        self.combined_dir = os.path.join(self.temp_dir.name, "combined")

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
            "RESULTS_DIR": self.results_dir,
            "IMPORTS_DIR": self.imports_dir,
            "COMBINED_DIR": self.combined_dir,
            "SECRET_KEY": "test-secret",
        })
        app_module.set_catalog(self.app, app_module.load_catalog(self.catalog_path))
        self.client = self.app.test_client()

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
        self.assertEqual(payload["next_url"], "/cluster/Cluster0001")

        load_response = self.client.get("/load/Cluster0000")
        self.assertEqual(load_response.status_code, 200)
        self.assertEqual(
            load_response.get_json(),
            {
                "exists": True,
                "skipped": False,
                "flagged": False,
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
        self.assertEqual(response.get_json()["next_url"], "/cluster/Cluster0000")

        progress_response = self.client.get("/progress")
        self.assertEqual(
            progress_response.get_json(),
            {
                "total": 2,
                "done": 0,
                "skipped": 1,
                "flagged": 0,
                "remaining": 1,
            },
        )

    def test_flagged_updates_progress_and_load(self):
        response = self.client.post(
            "/save",
            json={
                "cluster": "Cluster0001",
                "image": "cluster001.jpg",
                "flagged": True,
                "index": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["next_url"], "/cluster/Cluster0000")

        progress_response = self.client.get("/progress")
        self.assertEqual(
            progress_response.get_json(),
            {
                "total": 2,
                "done": 0,
                "skipped": 0,
                "flagged": 1,
                "remaining": 1,
            },
        )

        load_response = self.client.get("/load/Cluster0001")
        self.assertEqual(
            load_response.get_json(),
            {
                "exists": True,
                "skipped": False,
                "flagged": True,
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

    def test_set_user_requires_selection_or_new_name(self):
        response = self.client.post(
            "/set_user",
            data={
                "selected_username": "",
                "username": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose an existing user", response.get_json()["message"])

    def test_set_user_accepts_existing_username_selection(self):
        response = self.client.post(
            "/set_user",
            data={
                "selected_username": "tester",
                "username": "",
                "next_url": "/0",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/0")

        with self.client.session_transaction() as session:
            self.assertEqual(session["username"], "tester")

    def test_sanitize_username_builds_safe_results_filename(self):
        self.assertEqual(
            csv_store.build_results_filename("John Smith"),
            "john_smith_results.csv",
        )
        self.assertEqual(
            csv_store.build_results_filename(" Dr. A/B "),
            "dr._a_b_results.csv",
        )

    def test_build_results_filename_rejects_empty_username(self):
        with self.assertRaises(ValueError):
            csv_store.build_results_filename("   ")

    def test_list_result_usernames_reads_embedded_username(self):
        path = os.path.join(self.results_dir, "john_smith_results.csv")
        csv_store.write_results_rows(path, [{
            "username": "John Smith",
            "cluster": "Cluster0000",
            "image": "cluster000.jpg",
            "x": "1.0",
            "y": "2.0",
            "ra": "3.0",
            "dec": "4.0",
            "skipped": "False",
            "flagged": "False",
            "updated_at": "2026-07-07T00:00:00",
        }])

        self.assertEqual(
            csv_store.list_result_usernames(self.results_dir),
            ["John Smith"],
        )

    def test_save_creates_sanitized_results_file(self):
        self.client.post(
            "/set_user",
            data={
                "username": "John Smith",
                "selected_username": "",
            },
        )

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
        self.assertTrue(
            os.path.exists(os.path.join(self.results_dir, "john_smith_results.csv"))
        )

    def test_progress_reads_from_csv_results(self):
        csv_store.write_results_rows(
            os.path.join(self.results_dir, "tester_results.csv"),
            [{
                "username": "tester",
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": "100.5",
                "y": "120.5",
                "ra": "3.123",
                "dec": "-32.987",
                "skipped": "False",
                "flagged": "False",
                "updated_at": "2026-07-07T00:00:00+00:00",
            }],
        )

        response = self.client.get("/progress")
        self.assertEqual(
            response.get_json(),
            {
                "total": 2,
                "done": 1,
                "skipped": 0,
                "flagged": 0,
                "remaining": 1,
            },
        )

    def test_download_all_results_reads_from_csv_results(self):
        csv_store.write_results_rows(
            os.path.join(self.results_dir, "tester_results.csv"),
            [{
                "username": "tester",
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": "100.5",
                "y": "120.5",
                "ra": "3.123",
                "dec": "-32.987",
                "skipped": "False",
                "flagged": "False",
                "updated_at": "2026-07-07T00:00:00+00:00",
            }],
        )

        response = self.client.get("/download_all_results")

        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], "tester")
        self.assertTrue(
            os.path.exists(os.path.join(self.combined_dir, "all_results.csv"))
        )

    def test_admin_review_reads_from_csv_results(self):
        csv_store.write_results_rows(
            os.path.join(self.results_dir, "tester_results.csv"),
            [{
                "username": "tester",
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": "100.5",
                "y": "120.5",
                "ra": "3.123",
                "dec": "-32.987",
                "skipped": "False",
                "flagged": "False",
                "updated_at": "2026-07-07T00:00:00+00:00",
            }],
        )

        response = self.client.get("/admin/review")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cluster0000", page)

    def test_index_lists_users_from_results_directory(self):
        path = os.path.join(self.results_dir, "john_smith_results.csv")
        csv_store.write_results_rows(path, [{
            "username": "John Smith",
            "cluster": "Cluster0000",
            "image": "cluster000.jpg",
            "x": "1.0",
            "y": "2.0",
            "ra": "3.0",
            "dec": "4.0",
            "skipped": "False",
            "flagged": "False",
            "updated_at": "2026-07-07T00:00:00",
        }])

        response = self.client.get("/0")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('option value="John Smith"', page)

    def test_import_results_creates_results_file(self):
        results_csv = io.BytesIO(
            (
                "username,cluster,image,x,y,ra,dec,skipped,flagged,updated_at\n"
                "Alice,Cluster0000,cluster000.jpg,100.5,120.5,3.123,-32.987,False,False,2026-07-07T00:00:00+00:00\n"
            ).encode("utf-8")
        )

        response = self.client.post(
            "/import_results",
            data={"file": (results_csv, "alice_results.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["username"], "Alice")
        self.assertTrue(
            os.path.exists(os.path.join(self.results_dir, "alice_results.csv"))
        )

    def test_import_results_refuses_collision_without_replace(self):
        csv_store.write_results_rows(
            os.path.join(self.results_dir, "alice_results.csv"),
            [{
                "username": "Alice",
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": "1.0",
                "y": "2.0",
                "ra": "3.0",
                "dec": "4.0",
                "skipped": "False",
                "flagged": "False",
                "updated_at": "2026-07-07T00:00:00+00:00",
            }],
        )

        results_csv = io.BytesIO(
            (
                "username,cluster,image,x,y,ra,dec,skipped,flagged,updated_at\n"
                "Alice,Cluster0001,cluster001.jpg,100.5,120.5,6.5,-32.6,False,False,2026-07-07T00:00:00+00:00\n"
            ).encode("utf-8")
        )

        response = self.client.post(
            "/import_results",
            data={"file": (results_csv, "alice_results.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.get_json()["collision"])

    def test_import_results_replaces_when_confirmed(self):
        csv_store.write_results_rows(
            os.path.join(self.results_dir, "alice_results.csv"),
            [{
                "username": "Alice",
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": "1.0",
                "y": "2.0",
                "ra": "3.0",
                "dec": "4.0",
                "skipped": "False",
                "flagged": "False",
                "updated_at": "2026-07-07T00:00:00+00:00",
            }],
        )

        results_csv = io.BytesIO(
            (
                "username,cluster,image,x,y,ra,dec,skipped,flagged,updated_at\n"
                "Alice,Cluster0001,cluster001.jpg,100.5,120.5,6.5,-32.6,False,False,2026-07-07T00:00:00+00:00\n"
            ).encode("utf-8")
        )

        response = self.client.post(
            "/import_results",
            data={
                "file": (results_csv, "alice_results.csv"),
                "replace_existing": "true",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        rows = csv_store.read_results_rows(os.path.join(self.results_dir, "alice_results.csv"))
        self.assertEqual(rows[0]["cluster"], "Cluster0001")

    def test_import_results_rejects_multi_user_file(self):
        results_csv = io.BytesIO(
            (
                "username,cluster,image,x,y,ra,dec,skipped,flagged,updated_at\n"
                "Alice,Cluster0000,cluster000.jpg,100.5,120.5,3.123,-32.987,False,False,2026-07-07T00:00:00+00:00\n"
                "Bob,Cluster0001,cluster001.jpg,100.5,120.5,6.5,-32.6,False,False,2026-07-07T00:00:00+00:00\n"
            ).encode("utf-8")
        )

        response = self.client.post(
            "/import_results",
            data={"file": (results_csv, "mixed_results.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("more than one username", response.get_json()["message"])

    def test_import_results_accepts_legacy_export_format_using_filename(self):
        results_csv = io.BytesIO(
            (
                "cluster,image,x,y,ra,dec,skipped,flagged\n"
                "Cluster0000,cluster000.jpg,100.5,120.5,3.123,-32.987,False,False\n"
            ).encode("utf-8")
        )

        response = self.client.post(
            "/import_results",
            data={"file": (results_csv, "john_smith_results.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["username"], "john smith")
        rows = csv_store.read_results_rows(os.path.join(self.results_dir, "john_smith_results.csv"))
        self.assertEqual(rows[0]["username"], "john smith")
        self.assertTrue(rows[0]["updated_at"])

    def test_download_results_includes_username_and_updated_at(self):
        self.client.post(
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

        response = self.client.get("/download_results")

        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(rows[0]["username"], "tester")
        self.assertTrue(rows[0]["updated_at"])

    def test_next_unannotated_returns_first_remaining_cluster(self):
        self.client.post(
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

        response = self.client.get("/next_unannotated")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["next_url"],
            "/cluster/Cluster0001",
        )

    def test_next_unannotated_returns_none_when_user_finished(self):
        self.client.post(
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
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0001",
                "image": "cluster001.jpg",
                "skipped": True,
                "index": 1,
            },
        )

        response = self.client.get("/next_unannotated")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["next_url"])

    def test_save_advances_to_next_unannotated_cluster(self):
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
        self.assertEqual(response.get_json()["next_url"], "/cluster/Cluster0001")

    def test_set_catalog_filter_shows_skipped_only(self):
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0001",
                "image": "cluster001.jpg",
                "skipped": True,
                "index": 1,
            },
        )

        response = self.client.post(
            "/set_catalog_filter",
            json={
                "filter_mode": "skipped",
                "cluster": "Cluster0000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["filter_mode"], "skipped")
        self.assertEqual(response.get_json()["total"], 1)
        self.assertEqual(response.get_json()["next_url"], "/cluster/Cluster0001")

        page_response = self.client.get("/0")
        page = page_response.get_data(as_text=True)

        self.assertEqual(page_response.status_code, 200)
        self.assertIn("Cluster0001", page)
        self.assertIn("Galaxy 1 / 1", page)
        self.assertNotIn("Cluster0000</h2>", page)

    def test_set_catalog_filter_shows_flagged_only(self):
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "flagged": True,
                "index": 0,
            },
        )

        response = self.client.post(
            "/set_catalog_filter",
            json={
                "filter_mode": "flagged",
                "cluster": "Cluster0001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["filter_mode"], "flagged")
        self.assertEqual(response.get_json()["total"], 1)
        self.assertEqual(response.get_json()["next_url"], "/cluster/Cluster0000")

        page_response = self.client.get("/0")
        page = page_response.get_data(as_text=True)

        self.assertEqual(page_response.status_code, 200)
        self.assertIn("Cluster0000", page)
        self.assertIn("Galaxy 1 / 1", page)
        self.assertNotIn("Cluster0001</h2>", page)

    def test_set_catalog_filter_requires_active_user_for_filtered_views(self):
        with self.client.session_transaction() as session:
            session.pop("username", None)

        response = self.client.post(
            "/set_catalog_filter",
            json={"filter_mode": "skipped"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Set a user", response.get_json()["message"])

    def test_filtered_view_shows_empty_state_when_no_matches(self):
        response = self.client.post(
            "/set_catalog_filter",
            json={"filter_mode": "flagged"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 0)

        page_response = self.client.get("/0")
        page = page_response.get_data(as_text=True)

        self.assertEqual(page_response.status_code, 200)
        self.assertIn("No objects in this view", page)
        self.assertIn("No objects match this filter", page)

    def test_download_skipped_catalog_subset_returns_catalog_csv(self):
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0001",
                "image": "cluster001.jpg",
                "skipped": True,
                "index": 1,
            },
        )

        response = self.client.get("/download_catalog_subset/skipped")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn(
            "attachment; filename=tester_skipped_catalog.csv",
            response.headers["Content-Disposition"],
        )

        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(rows, [{
            "cluster": "Cluster0001",
            "image": "cluster001.jpg",
            "ra": "6.5",
            "dec": "-32.6",
            "redshift": "0.43",
            "pixscale": "0.262",
        }])

    def test_download_flagged_catalog_subset_returns_catalog_csv(self):
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "flagged": True,
                "index": 0,
            },
        )

        response = self.client.get("/download_catalog_subset/flagged")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn(
            "attachment; filename=tester_flagged_catalog.csv",
            response.headers["Content-Disposition"],
        )

        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(rows, [{
            "cluster": "Cluster0000",
            "image": "cluster000.jpg",
            "ra": "3.1",
            "dec": "-32.9",
            "redshift": "0.25",
            "pixscale": "0.262",
        }])

    def test_download_catalog_subset_requires_active_user(self):
        with self.client.session_transaction() as session:
            session.pop("username", None)

        response = self.client.get("/download_catalog_subset/skipped")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Set a user", response.get_json()["message"])

    def test_download_catalog_subset_returns_404_when_empty(self):
        response = self.client.get("/download_catalog_subset/skipped")

        self.assertEqual(response.status_code, 404)
        self.assertIn("No skipped objects available yet", response.get_json()["message"])

    def test_index_shows_current_user_summary(self):
        self.client.post(
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

        response = self.client.get("/0")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Current user: <b>tester</b>", page)
        self.assertIn("Done: 1", page)
        self.assertIn("Flagged: 0", page)
        self.assertIn("Remaining: 1", page)
        self.assertIn('id="reset-user-results"', page)
        self.assertIn('id="flag-interesting"', page)

    def test_index_lists_result_backed_users_in_picker_only(self):
        self.client.post(
            "/set_user",
            data={
                "username": "tester",
                "selected_username": "",
            },
        )
        self.client.post(
            "/set_user",
            data={
                "username": "second-user",
                "selected_username": "",
            },
        )
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 100.5,
                "y": 120.5,
                "ra": 3.123,
                "dec": -32.876,
            },
        )

        response = self.client.get("/0")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('option value="tester"', page)
        self.assertIn('option value="second-user"', page)
        self.assertNotIn("User Progress", page)
        self.assertNotIn("second-user —", page)

    def test_index_shows_admin_export_button(self):
        response = self.client.get("/0")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin Tools", page)
        self.assertIn('id="download-all-results"', page)
        self.assertIn("Review All Results", page)

    def test_download_all_results_returns_combined_csv(self):
        self.client.post(
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
        self.client.post(
            "/set_user",
            data={
                "username": "second-user",
                "selected_username": "",
            },
        )
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0001",
                "image": "cluster001.jpg",
                "skipped": True,
                "index": 1,
            },
        )

        response = self.client.get("/download_all_results")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("attachment; filename=all_results.csv", response.headers["Content-Disposition"])

        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["username"], "second-user")
        self.assertEqual(rows[0]["cluster"], "Cluster0001")
        self.assertEqual(rows[0]["skipped"], "True")
        self.assertEqual(rows[1]["username"], "tester")
        self.assertEqual(rows[1]["cluster"], "Cluster0000")
        self.assertEqual(rows[1]["ra"], "3.123")
        self.assertTrue(rows[0]["updated_at"])

    def test_download_all_results_returns_404_when_empty(self):
        response = self.client.get("/download_all_results")

        self.assertEqual(response.status_code, 404)
        self.assertIn("No annotations available yet", response.get_json()["message"])

    def test_reset_user_results_requires_active_user(self):
        with self.client.session_transaction() as session:
            session.pop("username", None)

        response = self.client.post("/reset_user_results")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Set a user", response.get_json()["message"])

    def test_reset_user_results_clears_only_current_user_annotations(self):
        self.client.post(
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
        self.client.post(
            "/set_user",
            data={
                "username": "second-user",
                "selected_username": "",
            },
        )
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0001",
                "image": "cluster001.jpg",
                "x": 150.0,
                "y": 180.0,
                "ra": 6.6,
                "dec": -32.5,
                "index": 1,
            },
        )
        self.client.post("/reset_user_results")

        progress_response = self.client.get("/progress")
        self.assertEqual(
            progress_response.get_json(),
            {
                "total": 2,
                "done": 0,
                "skipped": 0,
                "flagged": 0,
                "remaining": 2,
            },
        )

        load_response = self.client.get("/load/Cluster0001")
        self.assertEqual(load_response.get_json(), {"exists": False})

        self.client.post(
            "/set_user",
            data={
                "username": "tester",
                "selected_username": "",
            },
        )
        tester_load_response = self.client.get("/load/Cluster0000")
        self.assertEqual(tester_load_response.status_code, 200)
        self.assertEqual(tester_load_response.get_json()["exists"], True)

    def test_admin_review_shows_empty_state(self):
        response = self.client.get("/admin/review")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("No annotations available yet.", page)
        self.assertIn("Annotated clusters: 0", page)

    def test_admin_review_marks_disagreement(self):
        self.client.post(
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
        self.client.post(
            "/set_user",
            data={
                "username": "second-user",
                "selected_username": "",
            },
        )
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 150.0,
                "y": 180.0,
                "ra": 3.2,
                "dec": -33.0,
                "index": 0,
            },
        )

        response = self.client.get("/admin/review")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cluster0000", page)
        self.assertIn("Disagreement", page)
        self.assertIn("tester", page)
        self.assertIn("second-user", page)
        self.assertIn("Annotated clusters: 1", page)
        self.assertIn("Disagreement: 1", page)

    def test_admin_review_ignores_small_offset_under_threshold(self):
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 100.5,
                "y": 120.5,
                "ra": 3.1230000,
                "dec": -32.9870000,
                "index": 0,
            },
        )
        self.client.post(
            "/set_user",
            data={
                "username": "second-user",
                "selected_username": "",
            },
        )
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 101.0,
                "y": 121.0,
                "ra": 3.1232500,
                "dec": -32.9872500,
                "index": 0,
            },
        )

        response = self.client.get("/admin/review")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cluster0000", page)
        self.assertIn("Agreement", page)
        self.assertIn("Disagreement: 0", page)

    def test_admin_review_cluster_shows_overlay_markers(self):
        self.client.post(
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
        self.client.post(
            "/set_user",
            data={
                "username": "second-user",
                "selected_username": "",
            },
        )
        self.client.post(
            "/save",
            json={
                "cluster": "Cluster0000",
                "image": "cluster000.jpg",
                "x": 150.0,
                "y": 180.0,
                "ra": 3.2,
                "dec": -33.0,
                "index": 0,
            },
        )

        response = self.client.get("/admin/review/Cluster0000")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cluster0000", page)
        self.assertIn('class="review-marker"', page)
        self.assertIn('data-x="100.5"', page)
        self.assertIn('data-x="150.0"', page)
        self.assertIn("tester", page)
        self.assertIn("second-user", page)
        self.assertIn("Open picker view", page)

    def test_admin_review_cluster_returns_404_for_unknown_cluster(self):
        response = self.client.get("/admin/review/DoesNotExist")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
