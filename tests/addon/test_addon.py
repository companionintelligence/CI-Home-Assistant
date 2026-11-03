"""Tests for the Home Assistant app in companion-voice/.

The launcher (run.py) is tested with a temporary options file and a patched
os.execv, so nothing is started. The packaging checks read config.yaml,
CHANGELOG.md, the Dockerfile and the icon, so drift between them fails here
instead of on a Supervisor.

Run from the repository root:
  python3 -m unittest discover -s tests/addon -t tests/addon
"""
import importlib.util
import json
import os
import pathlib
import re
import struct
import sys
import tempfile
import unittest
from unittest import mock

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "companion-voice"
BRIDGE_ENV = (
    "CI_SERVER_URL",
    "CI_SERVER_API_KEY",
    "CI_MODEL",
    "CI_TTS_VOICE",
    "LANGUAGES",
    "VOICE_BRIDGE_HOST",
    "VOICE_BRIDGE_PORT",
)


def _load_run():
    spec = importlib.util.spec_from_file_location("run", APP / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _png_size(path):
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG file")
    return struct.unpack(">II", header[16:24])


run = _load_run()


class LauncherTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.options_path = pathlib.Path(tmp.name) / "options.json"
        self._patch(mock.patch.object(run, "OPTIONS_PATH", str(self.options_path)))
        self._patch(mock.patch.dict(os.environ))
        for name in BRIDGE_ENV:
            os.environ.pop(name, None)
        self.execv = self._patch(mock.patch.object(run.os, "execv"))

    def _patch(self, patcher):
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def write_options(self, **options):
        self.options_path.write_text(json.dumps(options))

    def test_refuses_to_start_when_ci_server_url_is_empty(self):
        self.write_options(ci_server_url="", ci_server_api_key="key")
        with self.assertRaises(SystemExit) as stop:
            run.main()
        self.assertIn("ci_server_url is not set", str(stop.exception))
        self.execv.assert_not_called()

    def test_refuses_to_start_when_ci_server_url_is_absent(self):
        self.write_options(ci_server_api_key="key")
        with self.assertRaises(SystemExit):
            run.main()
        self.execv.assert_not_called()

    def test_exports_options_and_replaces_itself_with_the_bridge(self):
        self.write_options(
            ci_server_url="http://192.168.1.20:8080",
            ci_server_api_key="key",
            ci_model="ollama:llama3.2",
            ci_tts_voice="alloy",
            languages="en,fr",
        )
        run.main()
        self.assertEqual(os.environ["CI_SERVER_URL"], "http://192.168.1.20:8080")
        self.assertEqual(os.environ["CI_SERVER_API_KEY"], "key")
        self.assertEqual(os.environ["CI_MODEL"], "ollama:llama3.2")
        self.assertEqual(os.environ["CI_TTS_VOICE"], "alloy")
        self.assertEqual(os.environ["LANGUAGES"], "en,fr")
        self.execv.assert_called_once_with(sys.executable, [sys.executable, "main.py"])

    def test_empty_optional_options_are_not_exported(self):
        self.write_options(ci_server_url="http://ci:8080", ci_server_api_key="", ci_model="", languages=None)
        run.main()
        self.assertNotIn("CI_SERVER_API_KEY", os.environ)
        self.assertNotIn("CI_MODEL", os.environ)
        self.assertNotIn("LANGUAGES", os.environ)

    def test_bridge_listens_on_all_interfaces_at_10700_by_default(self):
        self.write_options(ci_server_url="http://ci:8080")
        run.main()
        self.assertEqual(os.environ["VOICE_BRIDGE_HOST"], "0.0.0.0")
        self.assertEqual(os.environ["VOICE_BRIDGE_PORT"], "10700")

    def test_bridge_settings_already_in_the_environment_win(self):
        os.environ["VOICE_BRIDGE_PORT"] = "10800"
        self.write_options(ci_server_url="http://ci:8080")
        run.main()
        self.assertEqual(os.environ["VOICE_BRIDGE_PORT"], "10800")


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load((APP / "config.yaml").read_text())

    def test_every_option_is_typed_and_passed_to_the_bridge(self):
        options = set(self.config["options"])
        self.assertEqual(options, set(self.config["schema"]))
        self.assertEqual(set(run.OPTION_ENV), options)

    def test_ci_server_url_is_a_url_with_no_default(self):
        self.assertEqual(self.config["schema"]["ci_server_url"], "url")
        self.assertEqual(self.config["options"]["ci_server_url"], "")

    def test_exposes_the_wyoming_port_and_has_no_init_system(self):
        self.assertEqual(self.config["ports"], {"10700/tcp": 10700})
        self.assertIs(self.config["init"], False)
        self.assertEqual(sorted(self.config["arch"]), ["aarch64", "amd64"])

    def test_store_metadata_is_present(self):
        for key in ("name", "version", "slug", "description", "url"):
            self.assertTrue(self.config.get(key), key)
        self.assertRegex(self.config["version"], r"^\d+\.\d+\.\d+$")

    def test_changelog_starts_with_the_current_version(self):
        first = re.search(r"^## (\S+)", (APP / "CHANGELOG.md").read_text(), re.MULTILINE)
        self.assertIsNotNone(first)
        self.assertEqual(first.group(1), self.config["version"])

    def test_base_image_is_pinned_by_tag_and_digest(self):
        froms = [line for line in (APP / "Dockerfile").read_text().splitlines() if line.startswith("FROM ")]
        self.assertEqual(len(froms), 1)
        self.assertRegex(
            froms[0],
            r"^FROM ghcr\.io/companionintelligence/ci-ha-voice-bridge:[\w.\-]+@sha256:[0-9a-f]{64}$",
        )

    def test_store_icon_is_128_pixels_square(self):
        self.assertEqual(_png_size(APP / "icon.png"), (128, 128))


if __name__ == "__main__":
    unittest.main()
