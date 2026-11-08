<div align="center">

# ✨ esum

### Your personal AI agent — open source, self-hosted, and it asks before it acts.

**⚡ Built from scratch in one weekend with [LingCode](https://lingcode.dev) ⚡**

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![React 18](https://img.shields.io/badge/react-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL 16](https://img.shields.io/badge/postgres-16-4169E1?logo=postgresql&logoColor=white)
![Tests: 318 passing](https://img.shields.io/badge/tests-318%20passing-2ea44f)
![Release gates: 10/10](https://img.shields.io/badge/release%20gates-10%2F10-2ea44f)
[![Built with LingCode](https://img.shields.io/badge/built%20with-LingCode-8A2BE2)](https://lingcode.dev)

<img src="docs/screenshots/demo/demo-3-brief.png" alt="esum reads tomorrow's calendar and email and suggests what to prepare" width="760">

</div>

---

### 💡 What is esum?

esum is a **personal AI agent that runs on your own machine**. You just **chat**: it reads your calendar and email, digs through Google Drive, Notion, and GitHub, writes briefs, sets reminders, and looks things up on the web. Even *connecting your accounts* happens right inside the conversation.

And the part that matters most: **it never acts behind your back.** Sending an email, changing an event, or asking for more access always shows up as a card in the chat that says **exactly** what will happen, and nothing runs until you click Allow.

### ⚡ Built from scratch in one weekend with LingCode

The whole project (requirements, technical design, backend, frontend, tests, and release tooling) was **built with [LingCode](https://lingcode.dev) in one weekend**. Not a toy demo, but a system built with real engineering discipline:

| | |
|---|---|
| 🐍 **~12,000 lines** of Python backend | FastAPI · PostgreSQL · six isolated services |
| ⚛️ **~1,900 lines** of React frontend | Chat-first, passes automated accessibility checks (axe-core) |
| 🧪 **318 automated tests** | Plus mutation checks: each safety rule was deliberately broken to prove a test catches it |
| ✅ **10/10 release gates** | Locked dependencies, linting, migrations, secret scanning, browser smoke tests, fresh install verification, and more |
| 🧩 **11 skills** | Gmail · Calendar · Drive · Notion · GitHub · Files · Memory · Automations · Browser · Daily brief · Inbox triage |

### 📸 Screenshots

| Connect accounts in chat | Wider access needs your OK | Approve the exact email |
|:---:|:---:|:---:|
| <img src="docs/screenshots/demo/demo-2-connect-in-chat.png" width="260"> | <img src="docs/screenshots/demo/demo-4-access-in-chat.png" width="260"> | <img src="docs/screenshots/demo/demo-5-approve-in-chat.png" width="260"> |
| **Share a conversation snapshot** | **What the recipient sees** | **Skills and accounts** |
| <img src="docs/screenshots/demo/demo-9-share-dialog.png" width="260"> | <img src="docs/screenshots/demo/demo-11-shared-page.png" width="260"> | <img src="docs/screenshots/demo/demo-8-skills-and-accounts.png" width="260"> |

### 🧩 Features

- **📥 Inbox triage** — "Go through my inbox" sorts new mail into *needs your reply*, *FYI*, and *can ignore*, then drafts replies in your tone. Each draft is a card: **Allow once**, **Edit** it first, or **Skip** it and move on.
- **💬 Chat is the interface** — Connect, modify access, reconnect, or disconnect accounts simply by asking; confirmation cards appear directly inside the chat.
- **📧 Gmail / 📅 Google Calendar** — Search, read, and summarize; draft emails and event updates that are sent only after you explicitly approve them.
- **📂 Google Drive · 📝 Notion · 🐙 GitHub** — Read-only access to documents, pages, databases, repositories, issues, and pull requests.
- **🧠 Skill System** — Every capability is a `SKILL.md` loaded on demand. You can write your own in plain text (e.g., a "weekly review") without writing a single line of code.
- **⏰ Automations** — "Remind me every weekday at 8:00 AM to review emails" or "notify me when my calendar changes"; nothing activates until you confirm it.
- **📄 Files & Memory** — Generates Markdown, CSV, and PDF files; remembers only what you explicitly ask it to keep.
- **🌐 Isolated Browser** — Reads web pages in a sandbox that starts signed out (no form submissions). Sign in to a site yourself and save it, and the assistant can read it with your approval, never seeing your password or session. Watch it live and take control at any time.
- **🔗 Sharing** — Convert selected messages into a read-only snapshot link that lasts 1, 7, or 30 days, and revoke access whenever you want.
- **🔑 Bring your own key** — Paste a key from Anthropic, ZenMux, or any Anthropic-compatible provider. It is checked once, stored encrypted, and shown only as `…1234`.
- **👥 Accounts** — Optional open sign-up (`OPA_SIGNUP_ENABLED=true`): everyone gets a private assistant. Rename yours, pick its style, change your password, or delete your account under Settings.
- **🗂️ Ownership of Your Data** — One-click full data export, one-click complete purge, plus full backup and restore capabilities.

### 🔒 Security by Design

- **Every external write requires explicit approval** of the **exact content** (recipients, body, and attachments are cryptographically bound by hash). Approvals expire in 24 hours and cannot be replayed.
- **The AI cannot elevate its own permissions.** It can only *request* access; elevation requires your signed-in click. Revoking permissions takes effect immediately.
- **Content from emails, web pages, and files is treated as untrusted data**, never as executable instructions.
- **Credentials live exclusively in the broker process** and are encrypted at rest. The worker process running the AI has no outbound internet route except to the model API.
- **Share links are stored as hashes only.** Shared pages contain no scripts or cookies, are excluded from search engines, and all content is permanently deleted once expired or disabled.

### 🚀 Quick Start (Demo mode: no accounts or API keys required)

**Prerequisites:** [uv](https://docs.astral.sh/uv/) and Node 20+ (with npm). The database is embedded and starts automatically.

```sh
git clone https://github.com/lingcode-dev/esum.git esum && cd esum
```

**1. Install** (every version is locked; the release check runs this block verbatim in an empty copy of the repository):

<!-- fresh-install:begin -->
```sh
cd server
uv sync --frozen --extra dev --extra browser
.venv/bin/playwright install chromium
cd ../web
npm ci
npm run build
cd ..
```
<!-- fresh-install:end -->

**2. Run** (one command starts the database and every service):

```sh
npm run dev          # or: node scripts/dev.mjs
```

Open **http://127.0.0.1:8080**, sign in with `demo@example.com` / `demo-password-123`, and say "**Connect my accounts**", then "**Go through my inbox**". Press `Ctrl-C` to stop; your data is kept in `server/data/`.

> Demo mode uses a sample mailbox, calendar, and documents, and the assistant's replies are scripted; **no real service is contacted**. In LingCode, just press **Run**.

### 🛠️ How to run locally

After the one-time install above:

| Command | What it does |
|---|---|
| `npm run dev` (or `npm start`) | From the repo root: rebuilds the web app if `web/src` changed, then starts the database and every service. Demo mode by default; live mode if `server/.env` exists. Serves on http://127.0.0.1:8080. |
| `cd web && npm run dev` | Optional: Vite dev server for working on the frontend alone. |
| `cd web && npm run build` | Type-checks and builds the frontend into `web/dist/`. |
| `cd server && .venv/bin/python -m pytest` | Backend tests. |
| `cd server && .venv/bin/ruff check opa tests scripts` | Backend lint. |

If `npm run dev` says `server/.venv` or `web/node_modules` is missing, run the install block above first.

### 🔌 Use your real Gmail and Claude

1. Copy the local settings: `cp server/.env.example server/.env`
2. Fill in `OPA_ANTHROPIC_API_KEY`, and a Google OAuth client in `OPA_GOOGLE_CLIENT_ID` / `OPA_GOOGLE_CLIENT_SECRET` (step by step in the [operations guide](docs/OPERATIONS.md#use-your-real-accounts)).
3. Run `npm run dev` again. It starts in live mode with its own database, so demo data never mixes with yours.
4. Say "**Connect my Google account**", then "**Go through my inbox and draft replies**". To get this every morning, say "**Every weekday at 8:00, go through my inbox and draft replies**" and confirm the automation.

### ☁️ Deploy (Docker Compose)

On any machine with Docker:

```sh
cp .env.example .env                 # set the three database passwords and OPA_INTERNAL_TOKEN
server/.venv/bin/opa generate-kek    # paste the output into OPA_BROKER_KEK in .env
docker compose --env-file .env -f deploy/compose.yaml up --build -d
docker compose --env-file .env -f deploy/compose.yaml run --rm api opa bootstrap-owner you@example.com
```

The app listens on `127.0.0.1:8080` only. To reach it from elsewhere (for example, so people can open your share links), put it behind an **HTTPS reverse proxy** and set `OPA_SECURE_COOKIES=true` and `OPA_PUBLIC_BASE_URL=https://your-domain`. Backups, restore, running the services yourself, and upgrades are in the [operations guide](docs/OPERATIONS.md).

### ☁️ Deploy (LingCode Cloud)

`deploy/cloud` runs the whole stack in one [LingCode Cloud](https://lingcode.dev) hosted app: `python3 deploy/cloud/build.py`, then deploy `deploy/cloud/dist` as a hosted Python app. Add `OPA_BROKER_KEK` (from `opa generate-kek`) to the backend's secrets before anyone saves a key, and keep a copy: keys saved under one KEK cannot be read with another. Sign-up is on by default there; set `OPA_SIGNUP_ENABLED=false` to turn it off. Files and exports are kept until the next restart. Details are in the [operations guide](docs/OPERATIONS.md).

### 📊 Status: v0.4 preview

To be straight about it: every feature passes the automated tests, but **the real Google, Notion, GitHub, and Claude APIs have not been exercised live yet** (tests use fakes built to the providers' published contracts). The Docker Compose deployment has been built, run, backed up, and restored on a real Docker host. Details in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). Try it, open issues, and send pull requests!

### 📚 Docs

[Operations guide](docs/OPERATIONS.md) · [Writing skills](docs/skills.md) · [Technical design](docs/tech-design.md) · [Requirements](docs/open-muse-implementation-requirements.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)

---

<div align="center">

**esum** is an independent open-source project. It is not affiliated with or endorsed by Meta, and it is not an implementation of any Meta product.

Apache-2.0 · Made with ❤️ and [LingCode](https://lingcode.dev)

</div>
