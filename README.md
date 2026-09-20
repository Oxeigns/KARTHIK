# swagger

## Fictional HTTP sandbox (no external API needed)

For an existing Heroku app, deploy this branch (`codex/http-sandbox`) first,
then set `API_MODE=sandbox` and `BOT_MODE=polling`. Keep your BOT_TOKEN,
OWNER_ID and channel settings. API_BASE_URL and API_KEY can be removed:
sandbox mode ignores both, including previously saved values.
New app.json deployments and .env.example select sandbox mode.
The code default remains http when API_MODE is absent.

The bot starts its own fictional service on a random loopback port in the same
process. APIClient makes actual POST /info and POST /num requests to that service.
No separate app, paid API, public URL or TLS configuration is needed for the sandbox.
The local service does not call external APIs, store queries, or expose a public route.
Success results are always labelled DEMO, including numeric inputs.
It shuts down with the bot. Existing HTTPS validation stays in place for http mode.

Send `/start`, then `/info demo`. Owner/sudo can run repeated tests; ordinary users
still have one valid attempt per UTC day. Failures consume that attempt too.

| Command | Expected response |
| --- | --- |
| `/info demo` | Fictional test item, labelled DEMO |
| `/info test-not-found` | No record found (404) |
| `/info test-rate-limit` | Temporary error after retries (429) |
| `/info test-server-error` | Temporary error after retries (503) |
| `/info test-invalid-json` | Invalid JSON error |
| `/info test-timeout` | Unavailable after the client's 10-second deadline |

`mock` remains the older in-memory fixture mode; `sandbox` tests the real HTTP path.
To use an authorized metadata provider later, explicitly set API_MODE=http and
configure the documented compatible HTTPS contract below.

## Bot interface

Owner contact: [@Notethicals](https://t.me/Notethicals). This contact link does not
change OWNER_ID or grant administrative permissions.
Support: [community](https://t.me/+hQh4Azoq9BoxMjk1).
The support link is separate from the existing force-subscription channel.

/start shows the welcome screen; /help shows commands and privacy limits.
The home screen includes Search guide, My account, quota and announcement settings.
Owner/sudo users also see Control panel: overview, paginated users, API setup,
user-control instructions and a state-aware pause/resume button. Navigation edits
the current message, including repeated taps, instead of adding another message.
API setup reports configuration presence only; it does not claim connectivity.
The Home/Help, update opt-in and opt-out buttons use Telegram primary, success
and danger styles; rendering depends on the Telegram client version.

The supplied PrimeAPIs file is a sample personal-record response, not an API
specification. It is not committed or integrated. The file contains a response body, not a URL,
authentication scheme or request specification. It cannot establish a live connection.
Provider attribution has not been changed. No private-record dataset is included.


[Open @BIT_OSINTBOT](https://t.me/BIT_OSINTBOT)

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Oxeigns/KARTHIK/tree/codex/http-sandbox)

The button targets the feature branch containing this configuration. Enter a **new**
BOT_TOKEN in Heroku's deployment form; no real bot token is committed.
Heroku deployment may incur charges; SQLite on Heroku remains demo-only (see below).

## Required channel subscription

Join link: https://t.me/+-0Kkr0dspbhlOWZl

- Set FORCE_SUB_CHAT_ID to the exact private channel ID (`-100…`) in the deploy form.
  An invite link or a positive user ID cannot substitute for this ID.
- FORCE_SUB_URL is prefilled with the join link above.
- Set OWNER_ID to your confirmed numeric Telegram user ID.
- Make @BIT_OSINTBOT an administrator in the required channel.
- Users must join before /start or searches; membership is checked again before
  every search, before spending quota. Owner/sudo are exempt. Help and unsubscribe
  remain accessible without membership.
- The Join and Check buttons do not grant access by themselves. Telegram membership
  must be confirmed; pending join requests must first be approved.
- Lookup errors/timeouts block searches without spending quota.
- Both channel fields must be set together; clear both only to disable force-sub.

[Telegram getChatMember documentation](https://core.telegram.org/bots/api#getchatmember)
requires bot administrator status for reliable checks of other users.

Source repository: [Oxeigns/KARTHIK](https://github.com/Oxeigns/KARTHIK).
Application files are at the repository root; do not set a nested build directory.
The original `swagger.zip` is retained as a snapshot, not the deployment source.

Modular Python 3.11+ Telegram bot using aiogram 3.x, aiohttp and aiosqlite.
The sample environment and Heroku deploy form select **sandbox mode**.
For external HTTP mode, explicitly set `API_MODE=http` and configure `API_BASE_URL`.
The separate `API_MODE=mock` option returns an in-memory fictional response.
HTTP errors never fall back to fictional results.
No real personal-record provider is included.

## Status and operational limits

The repository includes working application code, tests, CI and deployment templates.
It has been tested locally without a real bot token or provider credentials.
A live Telegram smoke test and provider-specific integration remain required before
production use. The pinned versions are a tested baseline, not a claim to be the latest.

- Exactly one valid search **attempt** per user per UTC calendar day across both
  commands. Failed requests also consume the attempt; admin can reset it.
- Atomic SQLite UPSERT prevents concurrent requests from spending quota twice.
- Owner/sudo bypass daily quota and maintenance. Searches are private-chat only.
- Use **one process and one replica**, with a writable persistent local volume.
  This is not a horizontally scaled database design.
- A durable queue schedules deletion of query and final response 60 seconds after
  the final edit. Poll interval is 0.5 seconds; retries, downtime, permissions and
  Telegram limits can delay or prevent deletion. It is not permanent secrecy.
- Query/result bodies are not stored in SQLite or application logs. Search logs
  contain only kind, outcome and timestamp, retained for 30 days. User IDs and
  broadcast preferences persist. Pending deletion records contain chat/message IDs.
- Protect-content reduces casual forwarding but cannot stop screenshots or copies.
- Broadcasts require explicit opt-in and admin confirmation. They are paced at
  approximately 10 messages/second. Restart interrupts an in-flight broadcast;
  confirmation previews expire after two minutes and are not persisted.
- No payments, automatic upgrades or paid quota tiers are implemented. Contact Owner
  simply opens the configured owner's Telegram contact.

## Quick start

Create a bot with BotFather and obtain your numeric Telegram user ID.

```bash
git clone https://github.com/Oxeigns/KARTHIK.git
cd KARTHIK
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: BOT_TOKEN and OWNER_ID are required.
# .env.example selects sandbox; HTTP mode additionally needs API_BASE_URL.
# Set API_KEY if your authorized metadata provider requires a bearer token.
python bot.py
```

Start a private chat and send `/start`. Use Search guide for command syntax.
HTTP mode sends your query to the configured metadata adapter; no data is fabricated.
For offline UI testing, explicitly set `API_MODE=mock` and send `/info demo`.
A second standard-user request is blocked until midnight UTC.
Use a non-admin account to test quota; owner/sudo are exempt.

## Environment

| Variable | Required / default | Purpose |
| --- | --- | --- |
| BOT_TOKEN | Required | Secret BotFather token |
| OWNER_ID | Required | Positive numeric owner Telegram ID |
| SUDO_IDS | Empty | Comma-separated trusted admin IDs |
| API_MODE | http in code; sandbox in sample/Heroku | sandbox, mock or http |
| API_BASE_URL | Required for http | Trusted HTTPS origin/base path, no query credentials |
| API_KEY | Empty | Optional Authorization Bearer secret |
| DB_PATH | data/swagger.db | Writable persistent SQLite path |
| BOT_MODE | polling | polling or webhook |
| WEBHOOK_URL | Required for webhook | HTTPS origin; app appends /telegram |
| WEBHOOK_SECRET | Required for webhook | 32–256 URL-safe characters |
| PORT | 8080 | Health/webhook HTTP listener |
| FORCE_SUB_CHAT_ID | Required in this Heroku template | Exact -100… channel ID or public @username |
| FORCE_SUB_URL | Supplied invite link | Join button destination; never used as the channel ID |

Generate a webhook secret with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
Do not send tokens in public chats or commit .env. Rotate any exposed secret.

## Commands

| Command | Who | Effect |
| --- | --- | --- |
| /start, /help | Everyone | Help, privacy notice and subscription menu |
| /num +15551234567 | Standard/admin | Number-shaped query, 7–15 digits |
| /info demo | Standard/admin | Printable term, max 120 characters |
| /subscribe | Private-chat user | Opt into announcements |
| /unsubscribe | Private-chat user | Stop announcements |
| /admin, /stats | Owner/sudo, private | Admin menu and aggregate counts |
| /ban ID, /unban ID | Owner/sudo, private | Block/unblock searches |
| /reset ID | Owner/sudo, private | Clear one user's daily quota |
| /broadcast text | Owner/sudo, private | Preview; confirm before sending |

The admin menu offers maintenance ON/OFF and paginated user IDs.
Do not add untrusted users to SUDO_IDS: sudo users have administrative powers.

## Configure the HTTP metadata API

The HTTP adapter is deliberately explicit and **not provider-specific**.
Connect only an authorized, consent-based data source. Do not integrate leaked
subscriber directories, stolen data or arbitrary private-identity lookup services.

Expected contract:

```http
POST {API_BASE_URL}/num
POST {API_BASE_URL}/info
Authorization: Bearer <API_KEY>
Content-Type: application/json

{"query": "demo"}
```

```json
{
  "data": {
    "entity": "Authorized example entity",
    "provider": "Example provider",
    "region": "Example region",
    "risk_score": "Not assessed"
  }
}
```

At least one recognized non-null scalar field is required. Absent fields show
"Not supplied"; structured fields are rejected. Values are capped at 250 characters
and HTML-escaped for rendering. API response size is capped at 256 KiB.
No generic raw-JSON dump or arbitrary URL fetching is exposed to Telegram users.

When your documentation is available, adapt APIClient._request and parse_record
to the real method, authentication, paths, field mapping and consent checks,
then add provider fixtures to tests. Verify the contract before starting in HTTP mode.
Unknown provider responses cannot be integrated just by setting an API key.

The full operation deadline is 10 seconds, including semaphore wait and retries.
HTTP 429/5xx receive up to three attempts with bounded backoff. Other HTTP statuses,
bad/empty JSON, invalid fields, oversized bodies and network timeouts produce
safe errors without upstream details. Transport exceptions are mapped to errors
rather than retried. Redirects are disabled so credentials are not forwarded.

## Deployment

### Persistent storage is mandatory for dependable quotas

Losing the SQLite file resets user quotas and pending deletions. Keep the database,
WAL and SHM files together on a writable persistent volume. Do not share SQLite
across separate replicas/network filesystems. Paid platform storage may be required.
The examples are templates, not deployed services or guarantees of free hosting.

### Docker / VPS (recommended)

```bash
docker build -t swagger .
docker volume create swagger-data
docker run -d --name swagger --restart unless-stopped \
  --env-file .env -p 8080:8080 \
  -v swagger-data:/app/data swagger
```

The container runs as an unprivileged bot user. For bind mounts/platform volumes,
ensure /app/data is writable by that user; do not solve this with world-writable
permissions. Polling needs outbound HTTPS to Telegram and no public inbound endpoint.
A systemd template is also included. Install under /opt/swagger with a dedicated
swagger OS user, .venv, .env (mode 600) and writable data directory before enabling it.

### Render

Upload/push this repository and use render.yaml as a Blueprint. Supply BOT_TOKEN and
OWNER_ID. The template requests a paid persistent disk at /app/data, a single instance
and polling. /healthz is the health endpoint. Check mounted-directory ownership.

### Railway

Deploy the Dockerfile, set environment variables and attach a persistent volume at
/app/data. railway.toml configures a single replica and /healthz. Confirm volume
ownership and that DB_PATH points inside it. Do not scale replicas above one.

### Koyeb

Deploy the Dockerfile as one continuously running instance, expose port 8080,
set /healthz health checks, and mount persistent storage at /app/data if your
service/plan supports it. Without persistent storage this setup is demonstration-only;
choose a VPS or another storage-capable host for dependable quotas.

### Heroku

Procfile uses `worker: python bot.py`; app.json defines the environment schema.
After pushing the repository, deploy via Heroku's repository template flow or CLI
and scale worker=1. Use the root of this repository as the build directory.

**Heroku's ephemeral filesystem makes this SQLite build demo-only there.**
Dyno restarts/redeploys lose quota and deletion state. Production on Heroku needs
a persistent database implementation (not included) or a storage-capable host.
Do not claim daily-limit enforcement across dyno resets with ephemeral SQLite.

### Webhook mode

Choose BOT_MODE=webhook, set WEBHOOK_URL to your public HTTPS origin and a strong
WEBHOOK_SECRET. Route /telegram to the app. Requests without the correct Telegram
secret header are rejected by aiogram. Never put the bot token into the webhook URL.
Reverse-proxy request-body/access logging should be disabled or redacted.
For platforms with web/worker process types, run `python bot.py` as a web process.
Polling startup removes the webhook without dropping queued updates. Webhook
shutdown leaves registration in place so Telegram can retry during restarts.

## Architecture

- bot.py: lifecycle, authenticated webhook/polling, health checks and cleanup.
- config.py: validated environment configuration.
- database.py: schema version 1 migration, atomic quotas, user CRUD and deletion queue.
- api.py: bounded asynchronous HTTP adapter and fictional mock implementation.
- keyboards.py: user/admin buttons and user pagination.
- helpers.py: safe formatting, UTC time calculation and background deletion/cleanup.
- handlers/user.py: user commands and ephemeral result delivery.
- handlers/admin.py: access-guarded administration and opt-in broadcast.
- middlewares/throttling.py: input validation, maintenance and quota reservations.
- middlewares/auth.py: private-chat owner/sudo checks on every admin event.
- tests/: isolated SQLite, mock Telegram methods and local HTTP server tests.

Quota correctness does not depend on the midnight job: the current UTC date is
compared on every reservation. The midnight job prunes old quota/log rows.
SQLite migrations run on boot; future schema versions must add explicit migrations
rather than deleting the database. Do not manually set user_version backwards.

## Tests and release checklist

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
python -m compileall -q bot.py config.py database.py api.py handlers middlewares
```

Before a live release:
1. Verify correct bot token, admin IDs and a persistent writable disk.
2. Test /start, /num and /info with an owner and a separate standard account.
3. Confirm one request survives restart and is blocked until UTC reset.
4. Confirm both messages are deleted; test deletion failures/permissions.
5. Test unauthorized admin commands and crafted admin callbacks.
6. Test maintenance, opt-in broadcasts, cancellation by restart and blocked users.
7. Test webhook secret rejection, TLS proxy and graceful restart if using webhooks.
8. Validate the real provider's consent/data policy, schema and HTTP error responses.
9. Back up SQLite using its online backup API or while the process is stopped;
   never blindly copy only a live .db file while WAL writes are occurring.
10. Review dependency security updates, CI and log redaction before production.

References:
- [aiogram webhook lifecycle](https://docs.aiogram.dev/en/latest/dispatcher/webhook.html)
- [Telegram deleteMessage limitations](https://core.telegram.org/bots/api#deletemessage)

No live deployment, paid service purchase, bot creation or real-data search is
performed by this repository.
