from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from unittest import TestCase, mock
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image, ImageChops, ImageStat
from pydantic import ValidationError

from backend.app import create_app
from backend.motion.engine import FrameRenderer, evaluate, sample
from backend.motion.export import EncodeError, ExportService, encoder_choices, verify_video
from backend.motion.models import Camera, Pose, PoseKey, Sequence, Shot
from backend.motion.sample import ART, blue_flower
from backend.motion.store import MotionStore
from backend.storage import SCHEMA_VERSION, Workspace

API = '/api/animation'


def shot(**values) -> Shot:
    return Shot.model_validate({'id': 'cut', 'name': 'Cut', 'frames': 30, **values})


class AnimationEvaluatorTests(TestCase):
    def test_key_sampling_fractional_time_and_steps(self):
        base = Pose(x=0, opacity=1)
        end = PoseKey(frame=20, x=80, opacity=.2, visible=False, ease='linear')
        halfway = sample(base, [end], 10.5)
        self.assertAlmostEqual(halfway.x, 42)
        self.assertAlmostEqual(halfway.opacity, .58)
        self.assertTrue(halfway.visible)
        self.assertFalse(sample(base, [end], 20).visible)
        self.assertEqual(sample(base, [end.model_copy(update={'ease': 'hold'})], 19), base)
        self.assertAlmostEqual(sample(base, [end.model_copy(update={'ease': 'smooth'})], 5).x, 12.5)
        at_zero = PoseKey(frame=0, x=59)
        self.assertEqual(sample(base, [at_zero], 0).x, 59)

    def test_affine_pivot_parent_alpha_scale_and_draw_order(self):
        cut = shot(layers=[
            {'id': 'bg', 'name': 'Background', 'asset': 'forest'},
            {'id': 'hand', 'name': 'Hand', 'asset': 'glove', 'parent': 'arm', 'pivot_x': 5,
             'pose': {'x': 24, 'scale_x': 2, 'opacity': .4}},
            {'id': 'arm', 'name': 'Arm', 'parent': 'body', 'pose': {'rotation': 90, 'x': 16}},
            {'id': 'body', 'name': 'Body', 'pose': {'x': 100, 'y': 200, 'opacity': .5}},
            {'id': 'fg', 'name': 'Foreground', 'asset': 'leaves'},
        ])
        _, draws = evaluate(cut, 0)
        self.assertEqual([draw.id for draw in draws], ['bg', 'hand', 'fg'])
        hand = draws[1]
        x, y = hand.matrix.point(10, 0)  # 2× artwork pixel at the logical wrist pivot.
        self.assertAlmostEqual(x, 116)
        self.assertAlmostEqual(y, 224)
        self.assertAlmostEqual(hand.matrix.point(12, 0)[1], 226)
        self.assertAlmostEqual(hand.opacity, .2)
        cut.layers[3].pose.visible = False
        self.assertEqual([draw.id for draw in evaluate(cut, 0)[1]], ['bg', 'fg'])

    def test_camera_pans_zooms_tracks_and_ignores_keys_when_locked(self):
        cut = shot(speed=1.5, layers=[
            {'id': 'target', 'name': 'Traveler', 'pivot_x': 20, 'pose': {'x': 270, 'y': 480},
             'keys': [{'frame': 15, 'x': 345, 'y': 510, 'ease': 'linear'}]},
            {'id': 'bg', 'name': 'Background', 'asset': 'forest'},
        ])
        self.assertEqual(cut.output_frames, 20)
        cut.camera = Camera.model_validate({'mode': 'keyframed', 'keys': [
            {'frame': 15, 'x': 290, 'y': 460, 'zoom': 2, 'ease': 'linear'},
            {'frame': 28, 'x': 280, 'y': 485, 'zoom': .8},
        ]})
        matrix, _ = evaluate(cut, 10)
        self.assertEqual(matrix.point(290, 460), (270, 480))
        self.assertEqual(matrix.a, 2)
        self.assertEqual(evaluate(cut, 19)[0].a, .8)
        cut.camera.mode = 'locked'
        self.assertEqual(evaluate(cut, 0), evaluate(cut, 19))
        cut.camera = Camera.model_validate({'mode': 'tracking', 'target': 'target', 'pose': {'x': 0, 'y': 0, 'zoom': 1.2}})
        self.assertEqual(evaluate(cut, 0)[0].point(270, 480), (270, 480))
        matrix = evaluate(cut, 10)[0]
        self.assertAlmostEqual(matrix.point(345, 510)[0], 270)
        self.assertAlmostEqual(matrix.point(345, 510)[1], 480)
        self.assertNotEqual(evaluate(cut, 0)[1][0].matrix, evaluate(cut, 19)[1][0].matrix)

    def test_reject_invalid_graph_keys_and_length(self):
        for scopes in [
            {'layers': [{'id': 'a', 'name': 'A', 'parent': 'b'}, {'id': 'b', 'name': 'B', 'parent': 'a'}]},
            {'layers': [{'id': 'a', 'name': 'A', 'parent': 'missing'}]},
            {'layers': [{'id': 'a', 'name': 'A'}, {'id': 'a', 'name': 'Repeat'}]},
            {'layers': [{'id': 'a', 'name': 'A', 'keys': [{'frame': 30}]}]},
            {'layers': [{'id': 'a', 'name': 'A', 'keys': [{'frame': 8}, {'frame': 8}]}]},
            {'camera': {'mode': 'tracking', 'target': 'missing'}},
        ]:
            with self.subTest(fields=scopes), self.assertRaises(ValidationError):
                shot(**scopes)
        with self.assertRaises(ValidationError):
            Sequence(title='Too long', shots=[shot(frames=900, speed=.5), shot(id='extra')])

    def test_sample_locked_shot_still_forest_blink_and_reach(self):
        sequence = blue_flower()
        self.assertEqual([item.output_frames for item in sequence.shots], [96, 120, 78])
        reach = sequence.shots[1]
        baseline_camera, baseline = evaluate(reach, 0)
        fixed = {draw.id: draw for draw in baseline if draw.id in ('forest', 'ferns', 'petals')}
        for frame in range(reach.output_frames):
            camera, draws = evaluate(reach, frame)
            self.assertEqual(camera, baseline_camera)
            self.assertEqual({draw.id: draw for draw in draws if draw.id in fixed}, fixed)
        self.assertIn('eyes', {draw.id for draw in baseline})
        self.assertNotIn('eyes', {draw.id for draw in evaluate(reach, 30)[1]})
        self.assertIn('lids', {draw.id for draw in evaluate(reach, 30)[1]})
        self.assertIn('eyes', {draw.id for draw in evaluate(reach, 68)[1]})
        renderer = FrameRenderer(reach, {path.stem: path for path in ART.glob('*.webp')})
        opened, closed, reached = [renderer.frame(n).convert('RGB') for n in (0, 30, 68)]
        for a, b, roi in [(opened, closed, (174, 900, 460, 1000)), (opened, reached, (414, 996, 642, 1284))]:
            diff = ImageChops.difference(a, b)
            self.assertIsNone(diff.crop((80, 80, 1000, 580)).getbbox())
            self.assertGreater(sum(ImageStat.Stat(diff.crop(roi)).mean)/3, 9)
        self.assertLessEqual(renderer.cached_bytes, 32*1024**2)


class AnimationApiTests(TestCase):
    def setUp(self):
        folder = self.enterContext(TemporaryDirectory(prefix='Koma motion বাগান '))
        self.root = Path(folder)
        self.workspace = Workspace(self.root)

    def client(self):
        return TestClient(create_app(self.root), base_url='http://127.0.0.1:8765')

    def test_v4_workspace_migration_does_not_replace_old_data(self):
        with self.client() as client:
            settings = client.get('/api/settings').json()
        with self.workspace.connect() as db:
            for table in ('motion_jobs', 'motion_assets', 'motion_sequences'):
                db.execute(f'DROP TABLE {table}')
            db.execute('PRAGMA user_version = 4')
        with self.client() as client:
            self.assertEqual(client.get('/api/settings').json(), settings)
            self.assertEqual(client.get(API).json(), [])
            self.assertEqual(client.post(f'{API}/sample').status_code, 200)
        with self.workspace.connect() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_sample_creation_is_idempotent_and_edits_survive_restart(self):
        with self.client() as client:
            original = client.post(f'{API}/sample').json()
            self.assertEqual(original, client.post(f'{API}/sample').json())
            self.assertEqual(original['frames'], 294)
            self.assertEqual(len(original['assets']), 18)
            self.assertEqual(client.get(original['assets'][0]['url']).headers['content-type'], 'image/webp')
            path = f"{API}/{original['id']}"
            change = {'revision': original['revision'], 'document': deepcopy(original['document'])}
            change['document']['shots'][1]['speed'] = 2
            change['document']['shots'][1]['layers'][2]['pose']['opacity'] = 0.03
            response = client.put(path, json=change)
            self.assertEqual(response.status_code, 200, response.text)
            saved = response.json()
            self.assertEqual(saved['revision'], 2)
            self.assertEqual(saved['frames'], 234)
            self.assertEqual(client.put(path, json=change).status_code, 409)
        with self.client() as client:
            self.assertEqual(client.post(f'{API}/sample').json(), saved)

    def test_image_import_is_managed_bounded_and_scoped(self):
        raw = BytesIO()
        Image.new('RGBA', (1400, 2000), (63, 198, 233, 155)).save(raw, 'PNG')
        with self.client() as client:
            a, b = (client.post(API, json={'title': name}).json() for name in ('বনের আলো', 'Separate timeline'))
            path = f"{API}/{a['id']}"
            bad = client.post(f'{path}/assets', files={'image': ('invalid.jpg', b'not an image', 'image/jpeg')})
            self.assertEqual(bad.status_code, 422)
            response = client.post(f'{path}/assets', files={'image': ('Blue leaf.png', raw.getvalue(), 'image/png')})
            self.assertEqual(response.status_code, 201, response.text)
            asset = response.json()
            self.assertEqual((asset['width'], asset['height']), (1080, 1543))
            self.assertEqual(client.get(f"{API}/{b['id']}/assets/{asset['id']}").status_code, 404)
            data = client.get(asset['url']).content
            with Image.open(BytesIO(data)) as image:
                actual = image.getpixel((5, 5))
                self.assertEqual(actual[3], 155)
                self.assertLessEqual(max(abs(a-b) for a, b in zip(actual[:3], (63, 198, 233))), 2)
            layer = {'id': 'leaf', 'name': 'Leaf', 'asset': asset['id'], 'pose': {'x': 145, 'y': 600}}
            for sequence, expected in ((a, 200), (b, 422)):
                sequence['document']['shots'][0]['layers'].append(layer)
                response = client.put(f"{API}/{sequence['id']}", json={'revision': 1, 'document': sequence['document']})
                self.assertEqual(response.status_code, expected, response.text)
        with self.client() as client:
            restored = client.get(path).json()
            self.assertEqual(restored['document']['shots'][0]['layers'][0]['asset'], asset['id'])
            self.assertEqual(client.get(asset['url']).content, data)

    def test_missing_media_tools_are_explained_without_starting_a_job(self):
        with self.client() as client, mock.patch('backend.motion.export.binary', return_value=None):
            sample_doc = client.post(f'{API}/sample').json()
            path = f"{API}/{sample_doc['id']}/exports"
            response = client.post(path, json={'revision': 1})
            self.assertEqual(response.status_code, 422)
            self.assertIn('FFmpeg and FFprobe', response.text)
            self.assertEqual(client.get(path).json(), [])

    def test_recover_interrupted_job_and_hold_exclusive_workspace_lease(self):
        self.workspace.initialize()
        store = MotionStore(self.workspace)
        source = store.create(sample=True)
        folder = self.root / 'outputs'
        job, filename = uuid4().hex, 'unfinished.mp4'
        part = folder / f'.koma-{job}.part.mp4'
        for file in (part, folder / filename):
            file.write_bytes(b'not published')
        with self.workspace.connect() as db:
            db.execute('INSERT INTO motion_jobs VALUES (?, ?, 1, \'rendering\', 9, 294, \'libx264\', \'\', ?, ?, \'1\', \'1\')',
                       (job, source.id, str(folder), filename))
        first = ExportService(store)
        first.recover()
        self.addCleanup(first.close)
        self.assertFalse(part.exists())
        self.assertFalse((folder / filename).exists())
        self.assertEqual(first.get(source.id, job).state, 'failed')
        with self.client() as client:
            path = f'{API}/{source.id}/exports'
            self.assertEqual(client.get(f'{path}/{job}/video').status_code, 404)
            response = client.post(path, json={'revision': 1})
            self.assertEqual(response.status_code, 409)
            self.assertIn('another studio', response.text)

    def test_failed_probe_blocks_publication_and_hardware_failure_falls_back(self):
        # Test the failure/retry job state machine without pretending a GPU was available.
        attempted = []

        def encode(_self, _task, encoder, part):
            attempted.append(encoder)
            part.write_bytes(b'incomplete video')
            if encoder == 'h264_qsv':
                raise EncodeError('Hardware device failed')

        with self.client() as client, mock.patch('backend.motion.export.binary', return_value='unused'), \
                mock.patch('backend.motion.export.encoder_choices', return_value=['h264_qsv', 'libx264']), \
                mock.patch.object(ExportService, 'encode', encode), \
                mock.patch('backend.motion.export.run', return_value='{}'):
            timeline = client.post(f'{API}/sample').json()
            path = f"{API}/{timeline['id']}/exports"
            response = client.post(path, json={'revision': 1, 'mode': 'auto'})
            self.assertEqual(response.status_code, 202, response.text)
            job = response.json()
            deadline = monotonic() + 5
            while job['state'] in ('queued', 'rendering') and monotonic() < deadline:
                sleep(.05)
                job = client.get(f"{path}/{job['id']}").json()
            self.assertEqual(attempted, ['h264_qsv', 'libx264'])
            self.assertEqual(job['state'], 'failed')
            self.assertIn('did not validate', job['message'])
            self.assertIsNone(job['output_path'])
            self.assertEqual(client.get(f"{path}/{job['id']}/video").status_code, 404)
            self.assertEqual(list((self.root / 'outputs').iterdir()), [])

    def test_encoder_probe_requires_a_successful_encode_not_just_a_listing(self):
        with mock.patch('backend.motion.export.run', side_effect=[' V..... h264_qsv  Intel\n V..... h264_amf  AMD', None, '']) as run:
            self.assertEqual(encoder_choices('ffmpeg', 'auto'), ['h264_amf', 'libx264'])
            self.assertEqual(run.call_count, 3)
            self.assertIn('color=s=1080x1920:r=30', run.call_args.args)
        with mock.patch('backend.motion.export.run', return_value='{}'):
            with self.assertRaises(EncodeError):
                verify_video('ffprobe', self.root / 'x.mp4', 294)
