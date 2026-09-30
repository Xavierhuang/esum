<div align="center">

# ✨ esum

### Your personal AI agent — open source, self-hosted, and it asks before it acts.

**⚡ Built from scratch in one weekend with [LingCode](https://lingcode.dev) ⚡**

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![React 18](https://img.shields.io/badge/react-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL 16](https://img.shields.io/badge/postgres-16-4169E1?logo=postgresql&logoColor=white)
![Tests: 269 passing](https://img.shields.io/badge/tests-269%20passing-2ea44f)
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
| 🧪 **269 automated tests** | Plus mutation checks: each safety rule was deliberately broken to prove a test catches it |
| ✅ **10/10 release gates** | Locked dependencies, linting, migrations, secret scanning, browser smoke tests, fresh install verification, and more |
| 🧩 **10 skills** | Gmail · Calendar · Drive · Notion · GitHub · Files · Memory · Automations · Browser · Daily brief |

### 📸 Screenshots

| Connect accounts in chat | Wider access needs your OK | Approve the exact email |
|:---:|:---:|:---:|
| <img src="docs/screenshots/demo/demo-2-connect-in-chat.png" width="260"> | <img src="docs/screenshots/demo/demo-4-access-in-chat.png" width="260"> | <img src="docs/screenshots/demo/demo-5-approve-in-chat.png" width="260"> |
| **Share a conversation snapshot** | **What the recipient sees** | **Skills and accounts** |
| <img src="docs/screenshots/demo/demo-9-share-dialog.png" width="260"> | <img src="docs/screenshots/demo/demo-11-shared-page.png" width="260"> | <img src="docs/screenshots/demo/demo-8-skills-and-accounts.png" width="260"> |

### 🧩 Features

- **💬 Chat is the interface** — Connect, modify access, reconnect, or disconnect accounts simply by asking; confirmation cards appear directly inside the chat.
- **📧 Gmail / 📅 Google Calendar** — Search, read, and summarize; draft emails and event updates that are sent only after you explicitly approve them.
- **📂 Google Drive · 📝 Notion · 🐙 GitHub** — Read-only access to documents, pages, databases, repositories, issues, and pull requests.
- **🧠 Skill System** — Every capability is a `SKILL.md` loaded on demand. You can write your own in plain text (e.g., a "weekly review") without writing a single line of code.
- **⏰ Automations** — "Remind me every weekday at 8:00 AM to review emails" or "notify me when my calendar changes"; nothing activates until you confirm it.
- **📄 Files & Memory** — Generates Markdown, CSV, and PDF files; remembers only what you explicitly ask it to keep.
- **🌐 Isolated Browser** — Navigates public web pages only (no sign-ins, no form submissions); watch it live and take control at any time.
- **🔗 Sharing** — Convert selected messages into a read-only snapshot link that lasts 1, 7, or 30 days, and revoke access whenever you want.
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
git clone [https://github.com/SubjectAlphaChisato/esum.git](https://github.com/SubjectAlphaChisato/esum.git) esum && cd esum
