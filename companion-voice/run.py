"""Start the Voice Bridge from Home Assistant app options.

The Supervisor writes the app's options to /data/options.json. This maps each
option to the environment variable the bridge reads, then replaces this
process with main.py.
"""
import json
import os
import sys

OPTIONS_PATH = "/data/options.json"

OPTION_ENV = {
    "ci_server_url": "CI_SERVER_URL",
    "ci_server_api_key": "CI_SERVER_API_KEY",
    "ci_model": "CI_MODEL",
    "ci_tts_voice": "CI_TTS_VOICE",
    "languages": "LANGUAGES",
}


def main() -> None:
    with open(OPTIONS_PATH, encoding="utf-8") as handle:
        options = json.load(handle)

    if not options.get("ci_server_url"):
        sys.exit(
            "ci_server_url is not set. Set it in the app options to the address "
            "of your ci-server, as Home Assistant can reach it."
        )

    for option, env_name in OPTION_ENV.items():
        value = options.get(option)
        if value not in (None, ""):
            os.environ[env_name] = str(value)

    os.environ.setdefault("VOICE_BRIDGE_HOST", "0.0.0.0")
    os.environ.setdefault("VOICE_BRIDGE_PORT", "10700")
    os.execv(sys.executable, [sys.executable, "main.py"])


if __name__ == "__main__":
    main()
