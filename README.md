# ANA · Hermes Agent Mission Control

A local, voice-enabled ANA dashboard for [Hermes Agent](https://github.com/NousResearch/hermes-agent). It is a visual interface over your existing Hermes profile—not a second agent runtime—so it inherits the same tools, skills, memory, browser automation, MCP servers, and third-party integrations.

![ANA Hermes dashboard](docs/screenshot.png)

## What you get

- Futuristic browser-based mission-control HUD
- Natural conversational replies with a concise ANA voice persona
- Continuous voice conversation: listen → transcribe → answer → speak → listen
- Edge TTS (id-ID) for voice output
- Browser speech fallback when Edge TTS is unreachable
- Working command matrix and slash commands
- Hermes session continuity across voice turns
- Access to the active Hermes profile's tools, skills, browser, memory, and MCP integrations
- Local-only HTTP server bound to `127.0.0.1`

## Prerequisites

1. macOS or Linux with Python 3 and a modern Chromium browser.
2. Hermes Agent installed and configured:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes setup
```

Confirm that `hermes chat -q "Say online"` works before installing the dashboard.

## One-command install

```bash
git clone https://github.com/Itsme23476/ana-hermes-dashboard.git && \
cd ana-hermes-dashboard && \
./install.sh
```

The installer creates a private `.env`, optionally builds the minified UI bundle
(`npm run build:ui`, skip with `ANA_UI_BUILD=no`), starts the dashboard, and opens:

<http://127.0.0.1:8730>

No API keys are required for the basic dashboard. Browser speech APIs are used as a fallback.

## One-prompt installation with Hermes

Give this prompt to an already-installed Hermes Agent:

> Install and launch the ANA dashboard from https://github.com/Itsme23476/ana-hermes-dashboard. Clone or update it under ~/ana-hermes-dashboard, preserve any existing private .env file, run its installer, verify http://127.0.0.1:8730/api/status reports the Hermes runtime, and tell me the local dashboard URL. Do not print or expose any credentials.

Hermes can perform the clone, setup, launch, and health check with its terminal tools.

## Voice setup

Voice works without any API key: transcription uses the browser Web Speech API, voice
output uses Microsoft Edge TTS (id-ID). Set the voice in the UI or via `.env`:

```bash
ANA_VOICE_ID=id-ID-ArdiNeural
```

Restart the dashboard after editing `.env`. The key stays server-side and is never sent to frontend JavaScript.

## Hermes profile and tools

The dashboard uses the `default` Hermes profile unless overridden:

```bash
HERMES_PROFILE=work ./start.sh
```

If Hermes is installed at a nonstandard location:

```bash
HERMES_CMD="/absolute/path/to/hermes" ./start.sh
```

Third-party applications are connected in Hermes itself—not separately in this dashboard. Typical setup paths are:

```bash
hermes skills browse       # Gmail, Notion, Airtable, Google Workspace, etc.
hermes tools               # built-in toolsets
hermes mcp list            # external MCP servers
hermes gateway setup       # Telegram, Slack, Discord, WhatsApp, etc.
```

After changing Hermes tools or integrations, restart the dashboard or use `/new`.

## Command Matrix

Every button executes its base command immediately. Commands that accept a payload stay armed so the next typed or spoken phrase becomes `/command payload`.

| Command | Action |
|---|---|
| `/new` | Start a fresh Hermes thread |
| `/goal <text\|status\|clear>` | Set, read, or clear the standing objective |
| `/tools` | Run `hermes tools list` |
| `/browser <task>` | Ask Ana to use its browser/Chrome tools |
| `/background <mission>` | Run a background Ana mission |
| `/mission [task]` | Read or add to the local mission queue |
| `/personality <tone>` | Read or change the ANA tone overlay |
| `/commands` | Show all dashboard commands |
| `/toolsets` | Summarize enabled Hermes toolsets |
| `/connectors` | Explain integration inheritance |
| `/connect <name>` | Request Hermes-native connection guidance |
| `/status` | Show runtime/profile/voice status |

Normal text and voice requests go directly to Hermes Agent.

## Architecture

```text
Browser HUD
  ├─ microphone → browser Web Speech API (transkripsi di browser)
  ├─ POST /api/run → Python NDJSON server
  ├─ Hermes CLI quiet mode → active Hermes profile and tools
  └─ response → Edge TTS (server) or browser speech synthesis
```

Key files:

```text
server.py       local HTTP API and NDJSON streaming
runtime.py      Hermes CLI subprocess and session continuity
commands.py     dashboard slash commands and mission queue
voice.py        Edge TTS (id-ID), tanpa API key
persona.md      concise spoken ANA persona
ui/             dependency-free HTML/CSS/JavaScript HUD
install.sh      first-run setup and launch
start.sh        local launcher
```

## Security

- The server binds only to `127.0.0.1`; it is not exposed to the network.
- Browser auth uses an `HttpOnly` session cookie only; the master API token stays server-side and is never sent to the client (scripts on the host may still call the API with it).
- Same-origin + host-header allowlist (`ANA_ALLOWED_HOSTS`) guard every request; unauthenticated API traffic is rate-limited per IP, authenticated traffic per session.
- Agent runs are serialized so multiple tabs cannot race the shared Hermes session.
- Raw prompt logging is disabled unless `ANA_RAW_LOG` is explicitly configured; opt-in logs are created with mode `0600` and symlink protection.
- `.env`, state files, Python caches, and local credentials are ignored by Git.
- The dashboard never bundles Google, Zapier, Gmail, or Hermes credentials.
- Connected apps remain owned and authenticated by the user's Hermes profile.
- Review third-party skills and MCP servers before installing them.

## Manual start

```bash
cd ~/ana-hermes-dashboard
./start.sh
```

To use another port:

```bash
ANA_PORT=9000 ./start.sh
```

## Troubleshooting

### Hermes is not found

```bash
which hermes
hermes doctor
```

Then set `HERMES_CMD` in `.env` if needed.

### Microphone does not activate

Allow microphone access for `127.0.0.1` in the browser's site settings. Transcription needs a browser with Web Speech APIs; voice output uses Edge TTS.

### A newly connected tool is missing

Start a fresh session after changing Hermes tools:

```bash
hermes tools list
```

Then restart the dashboard and click `/new`.

## Credits and license

Originally inspired by [`Itsme23476/ana-os`](https://github.com/Itsme23476/ana-os), redesigned and adapted to use Hermes Agent as its runtime. Released under the MIT License; see [LICENSE](LICENSE).
