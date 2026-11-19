import io
import ipaddress
import socket
import sqlite3
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.images import MAX_IMPORT_BYTES
from backend.storage import SCHEMA_VERSION, Workspace

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "backend" / "demo_art"
STORY = (ROOT / "tests" / "fixtures" / "blue_flower.txt").read_text(encoding="utf-8").strip()
DRAFT = {"title": "The blue flower", "story": STORY, "profile": {"duration_seconds": 30}}


def image_bytes(format="PNG", size=(540, 960), color="#314975", animated=False, orientation=None):
    buffer = io.BytesIO()
    with Image.new("RGB", size, color) as image:
        if orientation:
            tags = image.getexif()
            tags[274] = orientation  # Portrait orientation stored by some cameras.
            tags[270] = "Do not retain source camera notes"
            image.save(buffer, format=format, exif=tags)
        elif animated:
            with Image.new("RGB", size, "#a3b39b") as second:
                image.save(buffer, format=format, save_all=True, append_images=[second], duration=100)
        else:
            image.save(buffer, format=format)
    return buffer.getvalue()


class VisualTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="Koma visual test বাগান ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def client(self, **kwargs):
        return TestClient(create_app(self.root), base_url="http://127.0.0.1:8765", **kwargs)

    def project(self, app, approve=False):
        response = app.post("/api/projects", json=DRAFT)
        self.assertEqual(response.status_code, 201, response.text)
        path = "/api/projects/" + response.json()["id"]
        plan = app.post(f"{path}/plan", json={}).raise_for_status().json()["plan"]
        if approve:
            plan = app.put(f"{path}/plan/approval", json={"revision": plan["revision"], "approved": True}).raise_for_status().json()["plan"]
        return path, plan

    def frame(self, app, path, plan, ordinal, *, revision=0, data=None, name=None, **credits):
        names = ("flower.webp", "old-tree.webp", "forest-lights.webp")
        if data is None:
            data = (ART / names[ordinal]).read_bytes()
        scene = plan["document"]["scenes"][ordinal]["id"]
        return app.post(f"{path}/storyboard/{scene}/frames", files={"image": (name or names[ordinal], data, "image/webp")},
                        data={"plan_revision": plan["revision"], "shot_revision": revision, **credits})

    def review(self, app, path, plan, *rows, approved=True):
        return app.post(f"{path}/storyboard/review", json={"plan_revision": plan["revision"], "approved": approved,
                        "targets": [{key: row[key] for key in ("scene_id", "revision")} for row in rows]})

    def reference(self, app, entry, data=None, name="reference.webp"):
        return app.post(f"/api/characters/{entry['id']}/references", files={"image": (name, data if data is not None else (ART / "traveler-reference.webp").read_bytes(), "image/webp")},
                        data={"revision": entry["revision"], "source": "Original fixture", "license_note": "CC0-1.0"})

    def test_import_batch_approve_replace_one_and_restart(self):
        with self.client() as app:
            path, plan = self.project(app, approve=True)
            for i in range(3):
                response = self.frame(app, path, plan, i, source="Koma original", license_note="CC0-1.0")
                self.assertEqual(response.status_code, 201, response.text)
            before = self.review(app, path, plan, *response.json()["shots"]).raise_for_status().json()["shots"]
            self.assertEqual([item["status"] for item in before], ["approved"] * 3)
            old = before[1]["active"]
            old_url = f"/api/images/{old['id']}"
            earlier_bytes = app.get(old_url).raise_for_status().content
            updated = self.frame(app, path, plan, 1, revision=before[1]["revision"], data=(ART / "old-tree-study.webp").read_bytes(),
                                 source="Original study", license_note="CC0-1.0").raise_for_status().json()["shots"]
            self.assertEqual([item["status"] for item in updated], ["approved", "review", "approved"])
            self.assertEqual((updated[0], updated[2]), (before[0], before[2]))
            self.assertEqual(updated[1]["active"]["number"], 2)
            self.assertEqual(earlier_bytes, app.get(old_url).raise_for_status().content)
            self.assertNotEqual(earlier_bytes, app.get(f"/api/images/{updated[1]['active']['id']}").raise_for_status().content)
            response = app.get(f"{old_url}?thumbnail=true").raise_for_status()
            self.assertEqual(response.headers["Content-Type"], "image/webp")
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            with Image.open(io.BytesIO(response.content)) as thumb:
                self.assertEqual(thumb.size, (360, 640))
            version_url = f"{path}/storyboard/{before[1]['scene_id']}"
        with self.client() as app:
            self.assertEqual(app.get(f"{path}/storyboard").json()["shots"], updated)
            history = app.get(f"{version_url}/frames").json()["versions"]
            self.assertEqual([version["number"] for version in history], [2, 1])
            self.assertEqual(history[1]["id"], old["id"])
            self.assertEqual(history[1]["last_approved_at"], old["last_approved_at"])
            self.assertIn("attachment", app.get(old_url + "?download=true").headers["Content-Disposition"])
            restored = app.put(f"{version_url}/frame", json={"plan_revision": plan["revision"], "shot_revision": updated[1]["revision"], "image_id": old["id"]}).raise_for_status().json()["shots"]
            self.assertEqual(restored[1]["active"]["id"], old["id"])
            self.assertEqual(restored[1]["status"], "review")
            approved = self.review(app, path, plan, restored[1]).raise_for_status().json()["shots"]
            self.assertEqual([item["status"] for item in approved], ["approved"] * 3)

    def test_archive_and_restore_library_reference_without_affecting_pinned_designs(self):
        with self.client() as app:
            design = {"name": "Mina • বনযাত্রী", "face": "Round cheeks", "body": "Chibi proportions", "hair": "Short plum hair",
                      "eyes": "Teal", "clothing": "Mint coat", "accessories": "Gold pin", "generation_notes": "Keep the star pin."}
            entry = app.post("/api/characters", json=design).raise_for_status().json()
            original = self.reference(app, entry).raise_for_status().json()
            pin = {"character_id": entry["id"], "image_id": original["reference"]["id"]}
            links = []
            for _ in range(2):
                path, plan = self.project(app)
                cast = plan["document"]["bible"]["characters"][0]
                name, cast_id = cast["name"], cast["id"]
                cast.update({**original["design"], "name": name, "library_pin": pin})
                draft = app.put(f"{path}/plan", json={"revision": plan["revision"], "document": plan["document"]}).raise_for_status().json()["plan"]
                self.assertIn("accessories: Gold pin", draft["timing"]["scenes"][0]["image_prompt"])
                self.assertEqual(draft["document"]["scenes"][0]["cast"][0]["character_id"], cast_id)
                links.append(path)
            library = f"/api/characters/{entry['id']}"
            edited = app.put(library, json={"revision": original["revision"], "design": {**original["design"], "clothing": "Violet cape"}}).raise_for_status().json()
            replacement = self.reference(app, edited, data=image_bytes(), name="another version.png").raise_for_status().json()
            self.assertEqual(replacement["reference_count"], 2)
            self.assertNotEqual(original["reference"]["id"], replacement["reference"]["id"])
            archived = app.put(f"{library}/archive", json={"revision": replacement["revision"], "archived": True}).raise_for_status().json()
            self.assertIsNotNone(archived["archived_at"])
            self.assertEqual(self.reference(app, archived).status_code, 409)
            for path in links:
                still_pinned = app.get(f"{path}/plan").json()["plan"]["document"]["bible"]["characters"][0]
                self.assertEqual(still_pinned["library_pin"], pin)
                self.assertEqual(still_pinned["clothing"], "Mint coat")
            self.assertEqual(app.get(f"/api/images/{pin['image_id']}").status_code, 200)
        with self.client() as app:
            restored = app.put(f"{library}/archive", json={"revision": archived["revision"], "archived": False}).raise_for_status().json()
            self.assertIsNone(restored["archived_at"])
            selected = app.put(f"{library}/reference", json={"revision": restored["revision"], "image_id": pin["image_id"]}).raise_for_status().json()
            self.assertEqual(selected["reference"]["number"], 1)
            self.assertEqual(selected["design"]["clothing"], "Violet cape")

    def test_scene_specific_invalidation_reorder_remove_and_regenerate(self):
        with self.client() as app:
            path, plan = self.project(app, approve=True)
            self.frame(app, path, plan, 0).raise_for_status()
            imported = self.frame(app, path, plan, 1).raise_for_status().json()["shots"]
            first, second, _ = self.review(app, path, plan, *imported[:2]).raise_for_status().json()["shots"]
            document = deepcopy(plan["document"])
            document["scenes"][1]["camera"] = "New angle under the old tree."
            document["scenes"][1]["title"] = "Under the roots"
            document["scenes"][0]["narration"] = "She finds a blue flower."
            document["scenes"][0], document["scenes"][1] = document["scenes"][1], document["scenes"][0]
            edited = app.put(f"{path}/plan", json={"revision": plan["revision"], "document": document}).raise_for_status().json()["plan"]
            board = app.get(f"{path}/storyboard").json()
            self.assertEqual([shot["scene_id"] for shot in board["shots"][:2]], [second["scene_id"], first["scene_id"]])
            self.assertEqual([shot["status"] for shot in board["shots"]], ["changed", "approved", "empty"])
            removed = deepcopy(edited["document"])
            removed["scenes"].pop(0)
            after = app.put(f"{path}/plan", json={"revision": edited["revision"], "document": removed}).raise_for_status().json()["plan"]
            board = app.get(f"{path}/storyboard").json()
            self.assertEqual(board["off_board_count"], 1)
            self.assertEqual(board["off_board"][0]["scene_id"], second["scene_id"])
            self.assertEqual(board["off_board"][0]["title"], "Under the roots")
            self.assertEqual(app.get(f"/api/images/{second['active']['id']}").status_code, 200)
            restored = app.put(f"{path}/plan/restore", json={"revision": after["revision"], "version": edited["revision"]}).raise_for_status().json()["plan"]
            self.assertEqual(app.get(f"{path}/storyboard").json()["shots"][0]["active"]["id"], second["active"]["id"])
            app.post(f"{path}/plan", json={"expected_revision": restored["revision"]}).raise_for_status()
            new = app.get(f"{path}/storyboard").json()
            self.assertEqual([shot["status"] for shot in new["shots"]], ["empty"] * 3)
            self.assertEqual(new["off_board_count"], 2)
            self.assertFalse({first["scene_id"], second["scene_id"]} & {item["scene_id"] for item in new["shots"]})

    def test_pinning_a_new_design_only_marks_scenes_using_that_character(self):
        with self.client() as app:
            path, plan = self.project(app, approve=True)
            for index in range(3):
                imported = self.frame(app, path, plan, index).raise_for_status().json()["shots"]
            reviewed = self.review(app, path, plan, *imported).raise_for_status().json()["shots"]
            item = app.post("/api/characters", json={"name": "Pip", "generation_notes": "Amber light"}).raise_for_status().json()
            reference = self.reference(app, item, data=(ART / "creature-reference.webp").read_bytes()).raise_for_status().json()["reference"]
            edited = deepcopy(plan["document"])
            person = edited["bible"]["characters"][1]
            person["library_pin"] = {"character_id": item["id"], "image_id": reference["id"]}
            person["generation_notes"] = "Amber light"
            app.put(f"{path}/plan", json={"revision": plan["revision"], "document": edited}).raise_for_status()
            shots = app.get(f"{path}/storyboard").json()["shots"]
            self.assertEqual(shots[0], reviewed[0])
            self.assertEqual([shot["status"] for shot in shots], ["approved", "changed", "changed"])
            self.assertEqual([shot["active"]["id"] for shot in shots], [shot["active"]["id"] for shot in reviewed])

    def test_batch_is_atomic_and_requires_current_plan_and_existing_images(self):
        with self.client() as app:
            path, plan = self.project(app)
            imported = self.frame(app, path, plan, 0).raise_for_status().json()["shots"]
            self.assertEqual(self.review(app, path, plan, imported[0]).status_code, 409)
            approved = app.put(f"{path}/plan/approval", json={"revision": plan["revision"], "approved": True}).raise_for_status().json()["plan"]
            self.assertEqual(self.review(app, path, approved, *imported[:2]).status_code, 422)
            self.assertEqual(app.get(f"{path}/storyboard").json()["shots"], imported)
            self.assertEqual(self.frame(app, path, approved, 0).status_code, 409)
            self.assertEqual(self.frame(app, path, plan, 1).status_code, 409)
            copy = app.get(path).json()
            media = Path(copy["folder"]) / "stills" / imported[0]["active"]["id"] / "image.webp"
            media.unlink()
            self.assertEqual(app.get(f"{path}/storyboard").json()["shots"][0]["status"], "missing")
            self.assertEqual(self.review(app, path, approved, imported[0]).status_code, 422)
            app.put(f"{path}/archive", json={"archived": True}).raise_for_status()
            self.assertEqual(self.frame(app, path, approved, 2).status_code, 409)

    def test_import_bounds_and_metadata_cleanup(self):
        with self.client() as app:
            path, plan = self.project(app)
            for data in (b"not an image", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                         image_bytes(size=(6001, 1)), image_bytes(animated=True), image_bytes()[:38]):
                response = self.frame(app, path, plan, 0, data=data)
                self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.frame(app, path, plan, 0, data=b'a' * (MAX_IMPORT_BYTES + 1)).status_code, 413)
            oriented = image_bytes(format="JPEG", size=(960, 540), orientation=6)
            imported = self.frame(app, path, plan, 0, data=oriented, name=r"C:\not uploaded\বাংলা.jpg").raise_for_status().json()["shots"][0]
            self.assertEqual(imported["version_count"], 1)
            self.assertEqual(imported["active"]["original_name"], "বাংলা.jpg")
            self.assertEqual((imported["active"]["width"], imported["active"]["height"]), (540, 960))
            response = app.get(f"/api/images/{imported['active']['id']}").raise_for_status()
            self.assertEqual(response.headers["Content-Type"], "image/webp")
            with Image.open(io.BytesIO(response.content)) as output:
                self.assertFalse(output.getexif())
            # Real PNG above the ordinary JSON request limit; allowed only on the bounded image route.
            big = io.BytesIO()
            with Image.effect_noise((2120, 1920), 50) as noise:
                noise.save(big, format="PNG")
            self.assertGreater(big.tell(), 1_500_000)
            self.assertEqual(self.frame(app, path, plan, 1, data=big.getvalue()).status_code, 201)

    def test_failed_activation_removes_staged_version_and_keeps_previous(self):
        with self.client(raise_server_exceptions=False) as app:
            path, plan = self.project(app)
            original = self.frame(app, path, plan, 0).raise_for_status().json()["shots"][0]
            folder = Path(app.get(path).json()["folder"]) / "stills"
            self.assertEqual([item.name for item in folder.iterdir()], [original["active"]["id"]])
            with patch("backend.storyboard.StoryboardStore.activate", side_effect=sqlite3.OperationalError("activation fixture failure")):
                reply = self.frame(app, path, plan, 0, revision=original["revision"])
            self.assertEqual(reply.status_code, 503)
            self.assertEqual([item.name for item in folder.iterdir()], [original["active"]["id"]])
        with self.client() as app:
            self.assertEqual(app.get(f"{path}/storyboard").json()["shots"][0], original)

    def test_reference_owner_and_cross_origin_guard(self):
        with self.client() as app:
            path, plan = self.project(app)
            one = app.post("/api/characters", json={"name": "One"}).raise_for_status().json()
            two = app.post("/api/characters", json={"name": "Two"}).raise_for_status().json()
            held = self.reference(app, one).raise_for_status().json()["reference"]
            invalid = deepcopy(plan["document"])
            invalid["bible"]["characters"][0]["library_pin"] = {"character_id": two["id"], "image_id": held["id"]}
            rejects = app.put(f"{path}/plan", json={"revision": plan["revision"], "document": invalid})
            self.assertEqual(rejects.status_code, 422)
            self.assertEqual(app.put(f"/api/characters/{two['id']}/reference", json={"revision": two["revision"], "image_id": held["id"]}).status_code, 404)
            self.assertEqual(app.get(f"/api/images/{held['id']}", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)

    def test_import_and_review_are_local_with_egress_guard(self):
        connect = socket.socket.connect
        connections = []

        def guarded(sock, address):
            if isinstance(address, tuple):
                connections.append(address)
                self.assertTrue(ipaddress.ip_address(address[0]).is_loopback)
            return connect(sock, address)

        with patch.object(socket.socket, "connect", guarded), self.client() as app:
            path, plan = self.project(app, approve=True)
            connections.clear()
            imported = self.frame(app, path, plan, 0).raise_for_status().json()["shots"][0]
            self.review(app, path, plan, imported).raise_for_status()
            app.get(f"/api/images/{imported['active']['id']}").raise_for_status()
            self.assertEqual(connections, [])

    def test_v3_migration_preserves_approved_plan_and_library_starts_empty(self):
        with self.client() as app:
            path, plan = self.project(app, approve=True)
            before = app.get(path).json()
        workspace = Workspace(self.root)
        with workspace.connect() as db:
            for table in ("motion_jobs", "motion_assets", "motion_sequences", "board_shots", "studio_images", "cast_library"):
                db.execute(f"DROP TABLE {table}")
            db.execute("PRAGMA user_version = 3")
        with self.client() as app:
            self.assertEqual(app.get(path).json(), before)
            self.assertEqual(app.get(f"{path}/storyboard").json()["plan"]["plan"], plan)
            self.assertEqual(app.get("/api/characters").json(), [])
            self.assertEqual(app.get(f"{path}/plan/history").json()["versions"][0]["revision"], plan["revision"])
        with workspace.connect() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
