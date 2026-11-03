# Changelog

## 0.2.0

- Companion Voice app: runs the Voice Bridge (Wyoming, port 10700) for Home Assistant Assist.
- Options for the ci-server address and key, the model, the speech voice and the languages.
- `ci_server_url` is required. The app stops with a message in its log when it is empty.
- Built on the published bridge image `ci-ha-voice-bridge:1.0.0-rc.1`, pinned by digest.
