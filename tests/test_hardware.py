import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from backend import hardware
from backend.storage import Workspace


class HardwareTests(unittest.TestCase):
    def test_windows_snapshot_conversion_reports_unreliable_vram_honestly(self):
        mock = {
            "caption": "Microsoft Windows 11 Pro", "cpu": [{"Name": "Test CPU", "NumberOfCores": 6, "NumberOfLogicalProcessors": 12}],
            "gpu": [{"Name": "Integrated Graphics", "AdapterRAM": 1073741824}, {"Name": "Other Graphics", "AdapterRAM": 0xFFFFFFFF}],
            "total_kib": 16 * 1024**2, "free_kib": 5 * 1024**2,
        }
        with patch.object(hardware, "windows_snapshot", return_value=mock):
            detected = hardware.windows_details()
        self.assertEqual(detected["os"], "Microsoft Windows 11 Pro")
        self.assertEqual(detected["cpu"], {"name": "Test CPU", "physical_cores": 6, "logical_cores": 12})
        self.assertEqual(detected["memory"]["available_bytes"], 5 * 1024**3)
        self.assertEqual(detected["gpus"][0]["memory_bytes"], 1024**3)
        self.assertIn("approximate", detected["gpus"][0]["memory_source"])
        self.assertIsNone(detected["gpus"][1]["memory_bytes"])

    def test_probe_parses_verified_banners_and_capabilities(self):
        responses = {("ffmpeg", "-version"): "ffmpeg version 7.1-static\n", ("ffprobe", "-version"): "ffprobe version 7.1-static\n",
                     ("ffmpeg", "-hide_banner", "-encoders"): " V....D libx264 H.264\n A....D aac AAC\n",
                     ("ffmpeg", "-hide_banner", "-filters"): " ... subtitles V->V Burn-in\n"}
        with TemporaryDirectory() as root:
            settings = Workspace(Path(root)).defaults
            with patch.object(hardware, "binary", side_effect=lambda name, _: name), patch.object(hardware, "run", side_effect=lambda *args: responses.get(args)):
                report = hardware.media_tools(settings)
        self.assertEqual(report["ffmpeg"]["version"], "7.1-static")
        self.assertEqual(report["ffprobe"]["state"], "ready")
        self.assertEqual(report["features"], {"h264": True, "aac": True, "subtitles": True})

    def test_missing_and_invalid_tools_are_distinct(self):
        with TemporaryDirectory() as root:
            settings = Workspace(Path(root)).defaults.model_copy(update={"ffprobe_path": str(Path(root) / "ffprobe.exe")})
            with patch.object(hardware, "binary", return_value=None):
                report = hardware.media_tools(settings)
        self.assertEqual(report["ffmpeg"]["state"], "missing")
        self.assertEqual(report["ffprobe"]["state"], "error")
        self.assertIsNone(report["features"]["subtitles"])

    def test_diagnostics_cache_expires_on_settings_change_or_refresh(self):
        with TemporaryDirectory() as root:
            base = Path(root)
            defaults = Workspace(base).defaults
            changed = defaults.model_copy(update={"outputs_dir": str(base / "different")})
            monitor = hardware.HardwareMonitor()
            with patch.object(hardware, "detect", side_effect=[{"read": 1}, {"read": 2}, {"read": 3}]) as detect:
                self.assertEqual(monitor.read(base, defaults), {"read": 1})
                self.assertEqual(monitor.read(base, defaults), {"read": 1})
                self.assertEqual(monitor.read(base, changed), {"read": 2})
                self.assertEqual(monitor.read(base, changed, refresh=True), {"read": 3})
                self.assertEqual(detect.call_count, 3)
