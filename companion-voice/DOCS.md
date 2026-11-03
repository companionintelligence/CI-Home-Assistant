# Companion Voice

Runs the Companion Voice Wyoming bridge inside Home Assistant. Home Assistant
connects to it on port 10700 through the Wyoming integration, and answers come
from your Companion Intelligence server (ci-server), grounded in Companion Memory.

## Setup

1. Set **ci_server_url** to your ci-server's address as Home Assistant can reach it, for example `http://192.168.1.20:8080`. It is required, and the app stops without it. The name `ci-server` only resolves inside the Docker Compose stack, so it won't work here.
2. Set **ci_server_api_key** to the ci-server master key.
3. Start the app. Then add the **Wyoming Protocol** integration with host
   `localhost` (or this machine's address) and port `10700`.
4. Under Voice assistants, pick `companion-conversation` as the conversation agent.

For control from Companion Hub and Companion Memory sign-in, install the
**Companion Voice** integration from HACS (see the repository README).

## Options

| Option | Default | Purpose |
|---|---|---|
| `ci_server_url` | none, required | ci-server base URL, reachable from Home Assistant |
| `ci_server_api_key` | empty | ci-server master key |
| `ci_model` | `ollama:llama3.2` | Model the bridge asks for |
| `ci_tts_voice` | `alloy` | Voice offered to Home Assistant |
| `languages` | `en` | Comma-separated languages |
