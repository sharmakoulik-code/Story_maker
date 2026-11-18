import ipaddress
import socket
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import SCHEMA_VERSION, Workspace

DRAFT = {
    "title": " After the rain ",
    "story": "A child finds a lantern on the hill.\nবনের আলো। जंगल की रोशनी।",
    "profile": {"duration_seconds": 45, "language": "bn", "style": "cel", "resolution": "540p", "fps": 18, "animation": "subtle"},
}


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(prefix="koma test ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def client(self, **kwargs):
        return TestClient(create_app(self.root, **kwargs), base_url="http://127.0.0.1:8765")

    def test_unicode_draft_and_profile_survive_backend_recreation(self):
        with self.client() as app:
            self.assertEqual(app.get("/api/projects").json(), [])
            response = app.post("/api/projects", json=DRAFT)
            self.assertEqual(response.status_code, 201, response.text)
            project = response.json()
            self.assertEqual(project["title"], "After the rain")
            self.assertTrue(Path(project["folder"]).is_dir())
            self.assertTrue(project["folder_exists"])
            path = f"/api/projects/{project['id']}"
            updated = app.put(path, json={**DRAFT, "title": "After the storm"}).json()
        with self.client() as app:
            self.assertEqual(app.get(path).json(), updated)
            self.assertEqual(updated["story"], DRAFT["story"])
            self.assertEqual(updated["profile"], DRAFT["profile"])
            self.assertEqual(app.get("/api/projects").json()[0]["title"], "After the storm")
            self.assertNotIn("story", app.get("/api/projects").json()[0])

    def test_archive_is_idempotent_and_keeps_files(self):
        with self.client() as app:
            project = app.post("/api/projects", json=DRAFT).json()
            location = Path(project["folder"]) / "fixture.txt"
            location.write_text("Reserve this file", encoding="utf-8")
            path = f"/api/projects/{project['id']}"
            archived = app.put(f"{path}/archive", json={"archived": True}).json()
            self.assertIsNotNone(archived["archived_at"])
            again = app.put(f"{path}/archive", json={"archived": True}).json()
            self.assertEqual(again, archived)
            self.assertEqual(app.put(path, json=DRAFT).status_code, 409)
            self.assertEqual(app.get(path).json()["story"], DRAFT["story"])
            restored = app.put(f"{path}/archive", json={"archived": False}).json()
            self.assertIsNone(restored["archived_at"])
            self.assertEqual(location.read_text(encoding="utf-8"), "Reserve this file")
            self.assertEqual(app.put(path, json=DRAFT).status_code, 200)

    def test_folder_settings_apply_only_to_new_projects_and_persist(self):
        with self.client() as app:
            previous = app.post("/api/projects", json=DRAFT).json()
            custom = self.root / "Custom media — draft projects"
            baseline = app.get("/api/settings").json()
            self.assertTrue(baseline["editable"])
            values = {**baseline["values"], "projects_dir": str(custom)}
            changed = app.put("/api/settings", json=values)
            self.assertEqual(changed.status_code, 200, changed.text)
            self.assertTrue(custom.is_dir())
        with self.client() as app:
            self.assertEqual(app.get("/api/settings").json()["values"]["projects_dir"], str(custom))
            new = app.post("/api/projects", json=DRAFT).json()
            self.assertEqual(Path(new["folder"]).parent, custom)
            self.assertEqual(app.get(f"/api/projects/{previous['id']}").json()["folder"], previous["folder"])
            self.assertTrue(Path(previous["folder"]).is_dir())

    def test_invalid_path_saves_no_settings_and_creates_no_folders(self):
        with self.client() as app:
            current = app.get("/api/settings").json()["values"]
            new_projects = self.root / "not committed"
            for unsafe in ("relative/path", r"\\network\share", str(self.root / "database" / "models")):
                response = app.put("/api/settings", json={**current, "projects_dir": str(new_projects), "models_dir": unsafe})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertFalse(new_projects.exists())
                self.assertEqual(app.get("/api/settings").json()["values"], current)

    def test_invalid_draft_does_not_echo_private_text(self):
        with self.client() as app:
            secret = "This draft must not be echoed in validation errors."
            bad = app.post("/api/projects", json={**DRAFT, "title": " ", "story": secret,
                                                   "profile": {**DRAFT["profile"], "duration_seconds": 0}})
            self.assertEqual(bad.status_code, 422)
            self.assertNotIn(secret, bad.text)
            self.assertEqual(app.get("/api/projects").json(), [])
            self.assertEqual(app.get("/api/projects/unknown").status_code, 404)

    def test_body_limit(self):
        with self.client() as app:
            response = app.post("/api/projects", content=b"x" * 1_500_001, headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 413, response.text[:100])

    def test_invalid_host_and_browser_origin_are_rejected(self):
        with self.client() as app:
            self.assertEqual(app.get("/api/health", headers={"Host": "other.example"}).status_code, 400)
            self.assertEqual(app.get("/api/health", headers={"Host": "5173-example.e2b.app"}).status_code, 400)
            self.assertEqual(app.post("/api/projects", json=DRAFT, headers={"Origin": "https://other.example"}).status_code, 403)
            self.assertEqual(app.get("/api/projects", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
            allow = app.post("/api/projects", json=DRAFT, headers={"Origin": "http://127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"})
            self.assertEqual(allow.status_code, 201)
            self.assertEqual(allow.headers["Cache-Control"], "no-store")
            self.assertIn("frame-ancestors 'none'", app.get("/").headers["Content-Security-Policy"])

    def test_demo_has_its_own_editable_samples_and_read_only_paths(self):
        with self.client(preview=True) as app:
            host = "5173-example.e2b.app"
            self.assertEqual(app.get("/api/health", headers={"Host": host}).json()["mode"], "preview")
            self.assertNotIn("frame-ancestors", app.get("/", headers={"Host": host}).headers["Content-Security-Policy"])
            demos = app.get("/api/projects").json()
            self.assertEqual(len(demos), 4)
            sample = next(project for project in demos if project["title"] == "The Blue Flower")
            board = app.get(f"/api/projects/{sample['id']}/storyboard").json()
            self.assertEqual([row["status"] for row in board["shots"]], ["approved", "review", "approved"])
            self.assertEqual([row["version_count"] for row in board["shots"]], [1, 2, 1])
            self.assertEqual(len(app.get("/api/characters").json()), 2)
            settings = app.get("/api/settings").json()
            self.assertFalse(settings["editable"])
            self.assertEqual(app.put("/api/settings", json=settings["values"]).status_code, 403)
            update = app.post("/api/projects", json=DRAFT, headers={"Host": host, "Origin": f"https://{host}"})
            self.assertEqual(update.status_code, 201)
            self.assertEqual(app.post("/api/projects", json=DRAFT, headers={"Host": host, "Origin": "https://other.example"}).status_code, 403)

    def test_foundation_requests_work_with_non_loopback_connections_blocked(self):
        real_connect = socket.socket.connect
        connections = []

        def guarded(sock, address):
            if isinstance(address, tuple):
                host, port = address[:2]
                connections.append((host, port))
                if not ipaddress.ip_address(host).is_loopback:
                    self.fail(f"Non-loopback connection attempted: {address}")
            return real_connect(sock, address)

        with patch.object(socket.socket, "connect", guarded), self.client() as app:
            self.assertEqual(app.get("/api/hardware?refresh=true").status_code, 200)
            self.assertEqual(app.post("/api/projects", json=DRAFT).status_code, 201)
            self.assertEqual(app.get("/api/projects").status_code, 200)
        self.assertEqual({port for _, port in connections}, {11434, 8188})

    def test_preserve_newer_schema_instead_of_overwriting(self):
        workspace = Workspace(self.root)
        workspace.initialize()
        with closing(sqlite3.connect(workspace.database)) as connection, connection:
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
            connection.execute("CREATE TABLE future_data (story TEXT)")
            connection.execute("INSERT INTO future_data VALUES ('preserve')")
        with self.assertRaisesRegex(RuntimeError, "newer version"):
            Workspace(self.root).initialize()
        with closing(sqlite3.connect(workspace.database)) as connection:
            self.assertEqual(connection.execute("SELECT story FROM future_data").fetchone()[0], "preserve")
