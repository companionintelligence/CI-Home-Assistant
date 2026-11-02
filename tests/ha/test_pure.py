"""Tests for the dependency-free parts of the Companion Voice integration.

These load the modules by path so they run without Home Assistant installed:
  python3 -m unittest discover -s tests/ha -t tests/ha
"""
import base64
import hashlib
import importlib.util
import json
import pathlib
import re
import unittest

PKG = pathlib.Path(__file__).resolve().parents[2] / "custom_components" / "companion_voice"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, PKG / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pkce = _load("pkce")
commands = _load("commands")

ALLOWED = ["light", "switch", "script"]


class PkceTests(unittest.TestCase):
    def test_verifier_is_43_url_safe_characters(self):
        verifier = pkce.new_code_verifier()
        self.assertEqual(len(verifier), 43)
        self.assertRegex(verifier, r"^[A-Za-z0-9_-]+$")

    def test_challenge_is_s256_of_verifier(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        self.assertEqual(pkce.code_challenge(verifier), expected)
        # RFC 7636 appendix B test vector
        self.assertEqual(pkce.code_challenge(verifier), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_authorize_url_carries_pkce_and_state(self):
        url = pkce.authorize_url(
            "https://hub.ci.computer/api/auth/oauth2/authorize",
            "ci-home-assistant",
            "http://192.168.1.10:8123/api/companion_voice/oauth/callback",
            "openid profile email",
            "state123",
            "challenge",
        )
        self.assertIn("response_type=code", url)
        self.assertIn("client_id=ci-home-assistant", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("state=state123", url)
        self.assertIn("code_challenge=challenge", url)


class CommandValidationTests(unittest.TestCase):
    def test_rejects_non_object_body(self):
        self.assertIsNotNone(commands.validate("light.on", ALLOWED))

    def test_rejects_unknown_command(self):
        self.assertIsNotNone(commands.validate({"command": "restart"}, ALLOWED))

    def test_get_state_needs_entity_id(self):
        self.assertIsNone(commands.validate({"command": "get_state", "entity_id": "light.kitchen"}, ALLOWED))
        self.assertIsNotNone(commands.validate({"command": "get_state", "entity_id": "kitchen"}, ALLOWED))

    def test_call_service_limited_to_allowed_domains(self):
        ok = {"command": "call_service", "domain": "light", "service": "turn_on", "data": {"entity_id": "light.a"}}
        self.assertIsNone(commands.validate(ok, ALLOWED))
        bad = dict(ok, domain="lock")
        self.assertIn("not allowed", commands.validate(bad, ALLOWED))

    def test_call_service_rejects_odd_service_names(self):
        bad = {"command": "call_service", "domain": "light", "service": "turn_on; rm"}
        self.assertIsNotNone(commands.validate(bad, ALLOWED))

    def test_call_service_data_must_be_object(self):
        bad = {"command": "call_service", "domain": "light", "service": "turn_on", "data": ["x"]}
        self.assertIsNotNone(commands.validate(bad, ALLOWED))


class ManifestTests(unittest.TestCase):
    def test_manifest_has_hacs_required_keys(self):
        manifest = json.loads((PKG / "manifest.json").read_text())
        for key in ("domain", "documentation", "issue_tracker", "codeowners", "name", "version"):
            self.assertIn(key, manifest)
        self.assertEqual(manifest["domain"], "companion_voice")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
