import ipaddress
import socket
import sqlite3
import unittest
from contextlib import closing
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.plan_timing import timing_for
from backend.planner import build_plan
from backend.schemas import DraftProfile
from backend.storage import SCHEMA_VERSION, Workspace
from backend.story_text import passages, words

SAMPLE = (Path(__file__).parent / "fixtures" / "blue_flower.txt").read_text(encoding="utf-8").strip()
BENGALI = "একটি ছোট মেয়ে বনে একটি জ্বলজ্বলে নীল ফুল খুঁজে পায়।সে পুরনো গাছের নিচে আটকে থাকা একটি জাদুকরী প্রাণী দেখে।সে প্রাণীটিকে মুক্ত করে। বন আলোয় ভরে যায়।"
HINDI = "एक छोटी लड़की को जंगल में एक चमकता नीला फूल मिलता है। वह पुराने पेड़ के नीचे फँसे एक नन्हे जीव को बचाती है। दोनों जंगल में जगमग रोशनी देखते हैं।"


class OfflinePlannerTests(unittest.TestCase):
    def test_user_sample_is_timed_and_reuses_cast_and_prop_ids(self):
        profile = DraftProfile(duration_seconds=30)
        document, source = build_plan(SAMPLE, profile)
        self.assertEqual((document, source), build_plan(SAMPLE, profile))
        self.assertEqual(source.source_beats, 3)
        self.assertEqual(source.spoken_beats, 3)
        self.assertEqual([scene.duration_seconds for scene in document.scenes], [10, 10, 10])
        self.assertEqual(" ".join(scene.narration for scene in document.scenes), SAMPLE)
        self.assertEqual(document.analysis.emotional_development, "Curiosity → Concern → Relief → Wonder")
        self.assertIn("trapped", document.analysis.conflict)
        self.assertIn("helps", document.analysis.climax)
        self.assertIn("illuminated", document.analysis.ending)
        self.assertEqual([person.name for person in document.bible.characters], ["Little chibi girl", "Tiny magical creature"])
        self.assertEqual([place.name for place in document.bible.locations], ["Mysterious forest", "Old tree"])
        self.assertEqual([prop.name for prop in document.bible.props], ["Glowing blue flower", "Magical lights"])
        main = document.bible.characters[0].id
        flower = document.bible.props[0].id
        self.assertTrue(all(main in [appearance.character_id for appearance in scene.cast] for scene in document.scenes))
        self.assertEqual([scene.prop_ids for scene in document.scenes[:2]], [[flower], [flower]])
        timing = timing_for(document, profile)
        self.assertTrue(timing.can_approve)
        self.assertEqual(timing.spoken_words, 43)
        self.assertEqual([metric.number for metric in timing.scenes], [1, 2, 3])
        self.assertTrue(all("9:16" in metric.image_prompt and "Little chibi girl" in metric.image_prompt for metric in timing.scenes))

    def test_tight_target_keeps_whole_spoken_passages_and_prioritizes_opening_and_ending(self):
        opening = "A girl crosses the hill."
        closing = "She smiles as the lanterns glow."
        long_story = opening + " " + ("The quiet village stands beneath a sky full of sparkling golden lanterns. " * 28) + closing
        profile = DraftProfile(duration_seconds=10)
        document, source = build_plan(long_story, profile)
        self.assertEqual(source.source_beats, 30)
        self.assertLess(source.spoken_beats, source.source_beats)
        self.assertEqual(" ".join(scene.narration for scene in document.scenes), opening + " " + closing)
        self.assertTrue(timing_for(document, profile).can_approve)

    def test_hindi_bengali_script_tokens_remain_intact_under_danda(self):
        self.assertEqual(words("मेरा जंगल।নীল ফুল।"), ["मेरा", "जंगल", "নীল", "ফুল"])
        self.assertEqual(len(passages(BENGALI)), 4)
        for story, language, script, expected_character in ((BENGALI, "bn", "Bengali", "ছোট মেয়ে"), (HINDI, "hi", "Devanagari", "छोटी लड़की")):
            with self.subTest(language=language):
                profile = DraftProfile(language=language, duration_seconds=30)
                doc, source = build_plan(story, profile)
                self.assertEqual(source.script_hint, script)
                self.assertEqual(doc.bible.characters[0].name, expected_character)
                self.assertGreater(source.spoken_beats, 0)
                self.assertTrue(timing_for(doc, profile).can_approve)
        english = DraftProfile(duration_seconds=30)
        doc, _ = build_plan(BENGALI, english)
        result = timing_for(doc, english)
        self.assertEqual(result.words_per_minute, 104)
        self.assertTrue(any("does not translate" in message for message in result.cautions))

    def test_quotes_and_labelled_dialogue_are_not_double_counted(self):
        profile = DraftProfile(duration_seconds=40)
        source = 'Dr. Mina opens the gate. Mina said, “Follow the blue light.”\nAri: I am right behind you.\n“Wait,” said Mina.'
        doc, _ = build_plan(source, profile)
        self.assertEqual(len(passages(source)), 4)
        cast = {person.id: person.name for person in doc.bible.characters}
        dialogue = [line for scene in doc.scenes for line in scene.dialogue]
        self.assertEqual([(cast[line.character_id], line.text) for line in dialogue], [("Mina", "Follow the blue light."), ("Ari", "I am right behind you."), ("Mina", "Wait,")])
        self.assertNotIn("Follow the blue light", " ".join(scene.narration for scene in doc.scenes))
        result = timing_for(doc, profile)
        self.assertEqual(result.spoken_words, 15)
        self.assertTrue(result.can_approve)

    def test_overlong_run_on_is_reference_not_unrealistic_narration(self):
        profile = DraftProfile(duration_seconds=10)
        doc, source = build_plan("The voyager walks over the hill " * 200, profile)
        self.assertEqual(source.spoken_beats, 0)
        self.assertTrue(source.excerpts)
        self.assertFalse(doc.scenes[0].narration)
        metrics = timing_for(doc, profile)
        self.assertTrue(metrics.scenes[0].fits)
        self.assertFalse(metrics.can_approve)
        self.assertIn("No narration", metrics.issues[0])

    def test_duration_presets_sum_exactly_and_all_generated_speech_fits(self):
        for target in [10, 30, 60, 90, 120, 180, 900]:
            with self.subTest(target=target):
                profile = DraftProfile(duration_seconds=target)
                doc, _ = build_plan(" ".join([SAMPLE] * 25), profile)
                timing = timing_for(doc, profile)
                self.assertEqual(timing.planned_seconds, target)
                self.assertTrue(all(scene.fits for scene in timing.scenes))
                self.assertLessEqual(len(doc.scenes), 40)


class PlanningApiTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="koma plan tests ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.draft = {"title": "Blue flower", "story": SAMPLE, "profile": {"duration_seconds": 30}}

    def client(self):
        return TestClient(create_app(self.root), base_url="http://127.0.0.1:8765")

    def project(self, client, draft=None):
        response = client.post("/api/projects", json=draft if draft is not None else self.draft)
        self.assertEqual(response.status_code, 201, response.text)
        record = response.json()
        path = f"/api/projects/{record['id']}"
        return path, Path(record["folder"])

    def generate(self, client, project, expected=None):
        response = client.post(f"{project}/plan", json={"expected_revision": expected})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["plan"]

    def save(self, client, path, plan, document, fit=False):
        response = client.put(f"{path}/plan", json={"revision": plan["revision"], "document": document, "fit_duration": fit})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["plan"]

    def approve(self, client, path, plan):
        response = client.put(f"{path}/plan/approval", json={"revision": plan["revision"], "approved": True})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["plan"]

    def test_edit_approve_reopen_and_reuse_prompts_without_media_work(self):
        with self.client() as app:
            path, folder = self.project(app)
            self.assertIsNone(app.get(f"{path}/plan").json()["plan"])
            initial = self.generate(app, path)
            self.assertEqual(initial["revision"], 1)
            self.assertEqual(app.get(path).json()["plan_status"], "draft")
            document = deepcopy(initial["document"])
            document["bible"]["characters"][0]["clothing"] = "A blue cloak"
            document["bible"]["locations"][1]["description"] = "Mossy exposed roots"
            document["bible"]["props"][0]["description"] = "Five luminous petals"
            document["scenes"][2]["image_prompt_override"] = "Custom final shot, portrait."
            saved = self.save(app, path, initial, document)
            self.assertTrue(all("A blue cloak" in item["image_prompt"] for item in saved["timing"]["scenes"][:2]))
            self.assertIn("Mossy exposed roots", saved["timing"]["scenes"][1]["image_prompt"])
            self.assertNotIn("Mossy exposed roots", saved["timing"]["scenes"][0]["image_prompt"])
            self.assertTrue(all("Five luminous petals" in item["image_prompt"] for item in saved["timing"]["scenes"][:2]))
            self.assertEqual(saved["timing"]["scenes"][2]["image_prompt"], "Custom final shot, portrait.")
            approved = self.approve(app, path, saved)
            self.assertIsNotNone(approved["approved_at"])
            self.assertEqual(approved["status"], "approved")
            self.assertEqual([entry.name for entry in folder.iterdir()], [])
        with self.client() as app:
            reopened = app.get(f"{path}/plan").json()["plan"]
            self.assertEqual(reopened, approved)
            self.assertEqual(app.get(path).json()["story"], SAMPLE)
            self.assertEqual(app.get("/api/projects").json()[0]["plan_status"], "approved")
            changed = deepcopy(reopened["document"])
            changed["scenes"][0]["title"] = "Find the flower"
            self.assertEqual(self.save(app, path, reopened, changed)["status"], "draft")

    def test_server_rejects_approval_when_saved_narration_does_not_fit(self):
        with self.client() as app:
            path, _ = self.project(app)
            plan = self.generate(app, path)
            edited = deepcopy(plan["document"])
            edited["scenes"][0]["narration"] = "Too much story for this duration. " * 20
            saved = self.save(app, path, plan, edited)
            self.assertFalse(saved["timing"]["can_approve"])
            self.assertIn("Scene 1 needs at least", saved["timing"]["issues"][0])
            check = app.put(f"{path}/plan/approval", json={"revision": saved["revision"], "approved": True})
            self.assertEqual(check.status_code, 422, check.text)
            check = app.put(f"{path}/plan", json={"revision": saved["revision"], "document": edited, "fit_duration": True})
            self.assertEqual(check.status_code, 422, check.text)
            self.assertEqual(app.get(f"{path}/plan").json()["plan"], saved)
            repaired = self.save(app, path, saved, plan["document"], fit=True)
            self.assertTrue(repaired["timing"]["can_approve"])
            self.assertEqual(self.approve(app, path, repaired)["status"], "approved")

    def test_target_only_change_can_adopt_new_duration_without_erasing_script(self):
        with self.client() as app:
            path, _ = self.project(app)
            plan = self.generate(app, path)
            document = deepcopy(plan["document"])
            document["scenes"][0]["title"] = "My scene title"
            reviewed = self.approve(app, path, self.save(app, path, plan, document))
            response = app.put(path, json={**self.draft, "profile": {"duration_seconds": 60}})
            self.assertEqual(response.json()["plan_status"], "stale")
            stale = app.get(f"{path}/plan").json()
            self.assertTrue(stale["can_adopt_target"])
            self.assertEqual(stale["plan"]["document"], reviewed["document"])
            self.assertIsNone(stale["plan"]["approved_at"])
            app.put(path, json={**self.draft, "profile": {"duration_seconds": 90}}).raise_for_status()
            self.assertEqual(app.put(f"{path}/plan/target", json={"revision": stale["plan"]["revision"]}).status_code, 409)
            app.put(path, json={**self.draft, "profile": {"duration_seconds": 60}}).raise_for_status()
            latest = app.get(f"{path}/plan").json()["plan"]
            adoption = app.put(f"{path}/plan/target", json={"revision": latest["revision"]})
            self.assertEqual(adoption.status_code, 200, adoption.text)
            adopted = adoption.json()["plan"]
            self.assertEqual(adopted["status"], "draft")
            self.assertEqual(adopted["timing"]["target_seconds"], 60)
            self.assertTrue(adopted["timing"]["issues"])
            retimed = self.save(app, path, adopted, adopted["document"], fit=True)
            self.assertEqual(retimed["document"]["scenes"][0]["title"], "My scene title")
            self.assertEqual(retimed["timing"]["planned_seconds"], 60)
            self.assertTrue(retimed["timing"]["can_approve"])

    def test_story_change_preserves_last_plan_and_requires_explicit_regeneration(self):
        with self.client() as app:
            path, _ = self.project(app)
            plan = self.approve(app, path, self.generate(app, path))
            self.assertEqual(app.put(path, json={**self.draft, "title": "New title"}).json()["plan_status"], "approved")
            self.assertEqual(app.put(path, json={**self.draft, "story": SAMPLE + " Night falls."}).json()["plan_status"], "stale")
            stale_view = app.get(f"{path}/plan").json()
            stale = stale_view["plan"]
            self.assertEqual(stale["document"], plan["document"])
            self.assertFalse(stale_view["can_adopt_target"])
            self.assertEqual(app.put(f"{path}/plan/target", json={"revision": stale["revision"]}).status_code, 409)
            self.assertEqual(app.post(f"{path}/plan", json={}).status_code, 409)
            self.assertEqual(app.put(f"{path}/plan/approval", json={"revision": stale["revision"], "approved": True}).status_code, 409)
            next_plan = self.generate(app, path, expected=stale["revision"])
            self.assertEqual(next_plan["status"], "draft")
            self.assertIn("Night falls", next_plan["document"]["analysis"]["ending"])

    def test_old_revisions_missing_references_blank_drafts_and_archives_are_safe(self):
        with self.client() as app:
            blank, _ = self.project(app, {"title": "Blank", "story": "..."})
            self.assertEqual(app.post(f"{blank}/plan", json={}).status_code, 422)
            self.assertIsNone(app.get(f"{blank}/plan").json()["plan"])
            project, _ = self.project(app)
            plan = self.generate(app, project)
            document = deepcopy(plan["document"])
            document["scenes"][0]["cast"].append({"character_id": "missing", "emotion": ""})
            response = app.put(f"{project}/plan", json={"document": document, "revision": plan["revision"]})
            self.assertEqual(response.status_code, 422)
            approved = self.approve(app, project, plan)
            response = app.put(f"{project}/plan", json={"document": plan["document"], "revision": plan["revision"]})
            self.assertEqual(response.status_code, 409)
            app.put(f"{project}/archive", json={"archived": True}).raise_for_status()
            self.assertEqual(app.post(f"{project}/plan", json={"expected_revision": approved["revision"]}).status_code, 409)
            self.assertEqual(app.get(f"{project}/plan").json()["plan"], approved)

    def test_v1_migration_retains_existing_story_and_settings(self):
        # Create a real v1-shaped file without going through the current migration code.
        workspace = Workspace(self.root)
        workspace.database.parent.mkdir()
        with workspace.connect() as db:
            db.executescript("""
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, story TEXT NOT NULL, profile TEXT NOT NULL,
                    folder TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT
                );
                CREATE INDEX projects_recent ON projects (updated_at DESC, id);
                CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL);
                PRAGMA user_version = 1;
            """)
            db.execute("INSERT INTO projects(id, title, story, profile, folder, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                       ("old", "Existing draft", SAMPLE, DraftProfile().model_dump_json(), str(self.root / "legacy"), "prior", "prior"))
            db.execute("INSERT INTO settings(id, data) VALUES (1, ?)", (workspace.defaults.model_dump_json(),))
        with self.client() as app:
            self.assertEqual(app.get("/api/projects/old").json()["story"], SAMPLE)
            self.assertEqual(app.get("/api/settings").json()["values"], workspace.defaults.model_dump())
            self.generate(app, "/api/projects/old")
        with closing(sqlite3.connect(workspace.database)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_v2_migration_backfills_current_approval_as_snapshot(self):
        with self.client() as app:
            project, _ = self.project(app)
            plan = self.approve(app, project, self.generate(app, project))
        with Workspace(self.root).connect() as db:
            for table in ("motion_jobs", "motion_assets", "motion_sequences", "board_shots", "studio_images", "cast_library", "story_plan_versions"):
                db.execute(f"DROP TABLE {table}")
            db.execute("PRAGMA user_version = 2")
        with self.client() as app:
            self.assertEqual(app.get(f"{project}/plan").json()["plan"], plan)
            history = app.get(f"{project}/plan/history").json()["versions"]
            self.assertEqual([item["revision"] for item in history], [plan["revision"]])
            self.assertEqual(history[0]["approved_at"], plan["approved_at"])

    def test_approved_snapshot_survives_reopen_regeneration_and_restore(self):
        with self.client() as app:
            project, _ = self.project(app)
            path = f"{project}/plan"
            plan = self.generate(app, project)
            reviewed = deepcopy(plan["document"])
            reviewed["scenes"][0]["title"] = "My approved opener"
            approved = self.approve(app, project, self.save(app, project, plan, reviewed))
            rev = approved["revision"]
            response = app.put(f"{path}/approval", json={"revision": rev, "approved": False})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["plan"]["status"], "draft")
            next_version = deepcopy(reviewed)
            next_version["scenes"][0]["title"] = "Unapproved experiment"
            draft = self.save(app, project, response.json()["plan"], next_version)
            fresh = self.generate(app, project, expected=draft["revision"])
            self.assertNotEqual(fresh["document"], reviewed)
        with self.client() as app:
            versions = app.get(f"{path}/history").json()["versions"]
            self.assertEqual([version["revision"] for version in versions], [draft["revision"], rev])
            response = app.get(f"{path}/history/{rev}")
            self.assertEqual(response.json()["document"], reviewed)
            self.assertIn("attachment;", response.headers["Content-Disposition"])
            response = app.put(f"{path}/restore", json={"revision": fresh["revision"], "version": rev})
            self.assertEqual(response.status_code, 200, response.text)
            restored = response.json()["plan"]
            self.assertEqual(restored["status"], "draft")
            self.assertGreater(restored["revision"], fresh["revision"])
            self.assertEqual(restored["document"], reviewed)
            self.assertEqual(app.get(f"{path}/history/{draft['revision']}").json()["document"], next_version)
            self.assertEqual(app.get(f"{path}/history/{fresh['revision']}").json()["document"], fresh["document"])
            app.put(project, json={**self.draft, "story": SAMPLE + " Rain falls."}).raise_for_status()
            stale = app.get(path).json()["plan"]
            self.assertEqual(app.put(f"{path}/restore", json={"revision": stale["revision"], "version": rev}).status_code, 409)
            self.assertFalse(app.get(f"{path}/history").json()["versions"][-1]["can_restore"])
            self.assertEqual(app.get(f"{path}/history/{rev}").json()["document"], reviewed)

    def test_history_paginates_and_targets_the_requested_project(self):
        with self.client() as app:
            project, _ = self.project(app)
            plan = self.generate(app, project)
            for _ in range(13):
                plan = self.generate(app, project, expected=plan["revision"])
            history = f"{project}/plan/history"
            page = app.get(history).json()
            self.assertEqual([item["revision"] for item in page["versions"]], list(range(13, 1, -1)))
            self.assertEqual(page["next_before"], 2)
            previous = app.get(history, params={"before": page["next_before"]}).json()
            self.assertEqual([item["revision"] for item in previous["versions"]], [1])
            self.assertIsNone(previous["next_before"])
            self.assertEqual(app.get(f"{history}/{10**30}").status_code, 422)
            other, _ = self.project(app)
            self.assertEqual(app.get(f"{other}/plan/history/1").status_code, 404)

    def test_generate_review_and_approve_with_egress_guard(self):
        real = socket.socket.connect
        targets = []

        def guarded(sock, address):
            if isinstance(address, tuple):
                targets.append(address[1])
                if not ipaddress.ip_address(address[0]).is_loopback:
                    self.fail(f"Non-loopback connection attempted: {address}")
            return real(sock, address)

        with patch.object(socket.socket, "connect", guarded), self.client() as app:
            path, _ = self.project(app)
            targets.clear()
            draft = self.generate(app, path)
            self.approve(app, path, draft)
            self.assertEqual(targets, [])
