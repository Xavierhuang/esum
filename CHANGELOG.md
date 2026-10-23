# Changelog

All notable changes are recorded here. Versions follow [Semantic Versioning](https://semver.org/).

## Unreleased (v0.4 accounts, your own key, LingCode Cloud)

### Added
- **Create an account:** with `OPA_SIGNUP_ENABLED=true` (on by default for the LingCode Cloud deployment), the sign-in page offers "Create an account". Each account is private: every record was already scoped to its owner, and each person brings their own model key. `OPA_SIGNUP_MAX_OWNERS` (default 100) caps accounts and `OPA_SIGNUP_PER_IP_PER_HOUR` (default 5) limits attempts per network. Off by default for self-hosted installs.
- **Bring your own key:** in live mode, the first screen after sign-in asks for an API key from Anthropic, ZenMux or any provider that speaks the Anthropic Messages API (Custom, public https only). The key is checked with one tiny request, sealed in the broker's vault, and shown again only as `…1234`; the worker fetches it per task. Change or remove it under Skills and accounts. `OPA_ANTHROPIC_API_KEY` still works as the server-wide fallback.
- **Settings screen** (Menu > Settings, or "Edit name and style" on the assistant's profile): rename the assistant, choose how it answers (concise, detailed, casual or formal), and set the time zone used for schedules. Closes the last open part of UX-01.
- **Change password:** needs the current password; every other session is signed out. Wrong guesses count toward the login throttle.
- **Delete account:** after typing the account email and the password, deletes everything "Delete all data" does, then the account, its sessions and its audit trail, which frees its place under the sign-up cap.
- **LingCode Cloud deployment** (`deploy/cloud`): the whole stack runs in one hosted-app container behind a status page that names the failing start-up step. It works with a managed database role that cannot create schemas (broker tables are mapped into the app's schema) and checks the schema version when the platform applies migrations. Files and exports live in `/tmp` there, so they last until the next restart.

### Changed
- Compose's egress allow-list includes `zenmux.ai:443` for ZenMux keys.

### Fixed
- Demo mode outside `npm run dev` (Docker Compose, LingCode Cloud) answered everything with "OK. (scripted model)"; it now uses the built-in demo script wherever it runs.
- `opa bootstrap-owner EMAIL --reset-password` changed the password of the first owner in the table whatever email was given; it now changes only that account and refuses an unknown email.

## Unreleased (v0.3 inbox triage)

### Added
- **Inbox triage:** "Go through my inbox" sorts unread mail from the last day into needs your reply, FYI, and can ignore, posts that summary in the chat, then drafts up to five replies, one approval card at a time. Replies go only to the sender of the email they answer and follow the owner's tone from earlier messages in the thread. Anything that needs the owner's decision is listed, not drafted. See the `inbox-triage` skill.
- **Edit before sending:** email approval cards have an Edit button for the subject and body. The edited email becomes a new action with its own hash, approved in the same click. The assistant's original draft stays in the ledger as proposed, and the assistant is told the owner changed it.
- **Skip:** every approval card can skip one item. The task carries on with the rest, where Deny still stops it.
- **`post_update` core tool:** the assistant can post a message to the chat and keep working. Approval cards now appear under a task's latest message, so a summary comes before its drafts.
- **Gmail attachments for real Google accounts:** approved files are sent through Gmail's multipart upload endpoint, re-checked against their approved SHA-256 at dispatch.
- **Live mode from `npm run dev`:** set `OPA_MODE=live` in `server/.env` (see `server/.env.example`). Live data is kept apart from the demo's, and a broker key is created on first run.
- **Scripted demo replies:** demo mode now walks through connecting the demo account, inbox triage, and reading Notion notes, and explains how to switch to live mode for anything else.
- The demo mailbox has a realistic unread inbox, and its search understands `is:`, `category:`, `label:`, `newer_than:`, `older_than:`, `after:`, `before:`, and `-` negation.

- **Saved website sign-ins:** sign in to a website once in your own browser (Browser > Open my browser) and save it. The assistant can then open that site signed in, only after you approve it, for that one task. The cookies are encrypted in the broker's store like a provider credential; the assistant sees only the name of the sign-in, never the cookies, and the browser container still has no route to the broker. Handing the browser back, stopping, or finishing the task ends the sign-in, and it can be removed at any time. Passwords are never stored.

### Changed
- The default model is `claude-opus-5-5`.
- The browser still cannot fill in forms or run scripts, so a saved sign-in lets the assistant read what you can see; it cannot act as you on a site.

## Unreleased (v0.2 connectors)

### Added
- **Skills harness:** every capability is a skill with a `SKILL.md` (instructions, tools, the account it needs). The model sees a short catalog and loads skills on demand with `skill__load`; loaded skills survive restarts. A daily-brief workflow skill shows how skills combine. Owners can add instruction-only skills with `OPA_SKILLS_DIR` and turn skills off on the new Skills screen. See `docs/skills.md`.
- **Sharing:** share chosen messages of a conversation as a read-only snapshot link that anyone can open without signing in. Only a hash of the link is stored; links expire (1, 7, or 30 days) and can be turned off; the page has no scripts or cookies and is kept out of search engines. Delete-all removes shared links and a restore turns them off.
- **Chat-first app:** the header shows only the assistant, a count of waiting approvals, and a Menu. Account cards and approvals appear inside the conversation. The Connections screen is gone; Skills and accounts shows access read-only. The chat opens with suggestions.
- **Accounts from the chat:** `connections__list` and `connections__request` let the assistant ask to connect, change, reconnect, or disconnect an account. The request is a card in the chat; connecting, adding access, and disconnecting happen only when the owner confirms it, and reductions apply at once. Provider sign-ins started from a card return to the chat.
- **Read-only connectors:** Google Drive (search, and Docs/Sheets/Slides exported as Markdown, CSV, and text), Notion (search, pages with nested blocks, data-source queries), and GitHub through a GitHub App (repositories, issue and pull-request search, issues with comments, text files). All provider content is marked untrusted, and the browser's data-sharing approval covers it.
- A provider registry that declares each connector's capabilities and allowed modes; the API refuses a mode a capability does not support (`mode_not_supported`).
- Generic OAuth routes (`/api/connectors/{provider}/authorize`, `/api/oauth/{provider}/callback`) and a shared single-flight token manager used by every provider.
- The Connections screen lists every configured provider and shows only the modes each capability supports.

### Fixed
- After a provider sign-in, the notice names the right provider (it always said Google), and the add-account list no longer repeats each provider's name.

## 0.1.0 — unreleased

First release candidate of OpenMuse, implementing `docs/open-muse-implementation-requirements.md` v0.1.1.

### Added
- **Foundation (M1):** single-owner sign-in with CSRF and throttling; persistent chat with side conversations; durable background tasks with leases, fencing, budgets, cancel, resume, and retry; live updates over server-sent events with replay; Claude and scripted model adapters.
- **Approvals (M2):** connector broker; action ledger with exact-payload approvals, 24-hour expiry, duplicate-safe dispatch, and unknown-outcome reconciliation; separate database roles; encrypted credential vault; egress proxy for the model host.
- **Google (M3):** Gmail and Google Calendar through OAuth with PKCE, incremental scopes, single-flight refresh, revocation, and health checks.
- **Files and memory (M4):** uploads and versioned Markdown, CSV, and PDF files; attachment-bound approvals; explicit, editable memory with a confirmation gate.
- **Automations (M5):** one-time, daily, and weekday schedules with DST-safe timing, catch-up, and no overlap; calendar-change triggers with deduplication and self-edit suppression.
- **Browser and data (M6):** isolated public-web browser with live view, takeover, and a data-sharing approval; export with JSON Schemas; delete-all; backup and restore with post-restore safety rules.
- **Packaging:** `uv.lock` and hash-pinned image requirements; Dockerfiles that install only from the locks; `opa version`; generated frontend API types with a compile-time contract check; automated accessibility scan (axe-core); `scripts/release_check.py` running every release gate.

### Known limitations
See `IMPLEMENTATION_STATUS.md`. In short: Docker images and Compose have not been built on the development machine; Google and the Claude API have not been called live; the manual VoiceOver pass (A17b) is outstanding; Gmail attachments work only with the demo account.
