import { Fragment, RefObject, useCallback, useEffect, useRef, useState } from "react";
import { api, api2, ApiError, Approval, Conversation, Me, Message, Notification, setCsrf, subscribe, Task, TaskState } from "./api";
import { files } from "./apiM4";
import { ApprovalCard, Approvals } from "./screens/Approvals";
import { Automations } from "./screens/Automations";
import { Browser } from "./screens/Browser";
import { Data } from "./screens/Data";
import { ArtifactLinks, Files } from "./screens/Files";
import { Memory } from "./screens/Memory";
import { KeyOnboarding } from "./screens/ModelKey";
import { ConnectionCard } from "./screens/ConnectionCard";
import { Profile } from "./screens/Profile";
import { Settings } from "./screens/Settings";
import { Skills } from "./screens/Skills";
import { ShareDialog, SharedLinks } from "./screens/Share";
import { Avatar, Icon, IconName, stamp } from "./ui";

type Screen = "chat" | "tasks" | "approvals" | "automations" | "browser" | "notifications" | "skills" | "shares" | "files" | "memory" | "data" | "settings";

const STATE_LABEL: Record<TaskState, string> = {
  queued: "Queued", running: "Running", waiting_approval: "Needs approval", waiting_user: "Needs your reply",
  blocked: "Blocked", succeeded: "Done", failed: "Failed", cancelled: "Cancelled",
};

const WIDE_PANEL = 1280;
const WIDE_LIST = 900;

function Empty({ children }: { children: string }) {
  return <p className="muted empty-note">{children}</p>;
}

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);

  const load = useCallback(async () => {
    try {
      const m = await api.me();
      setCsrf(m.csrf_token);
      setMe(m);
    } catch {
      setMe(null);
    } finally {
      setChecked(true);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (!checked) return <p role="status" className="center loading"><Avatar size={64} /><span className="sr-only">Loading…</span></p>;
  if (!me) return <Login onDone={load} />;
  const logout = async () => { await api.logout(); setMe(null); };
  if (me.needs_model_key) return <KeyOnboarding me={me} onDone={load} onLogout={logout} />;
  return <Shell me={me} setMe={setMe} onLogout={logout} onSignedOut={() => setMe(null)} />;
}

const POINTS: [IconName, string, string][] = [
  ["chat", "Just ask", "Mail, calendar, Drive, Notion, GitHub and the web, all from one conversation. Even connecting accounts happens in the chat."],
  ["shield", "Asks before it acts", "Every email, event or change shows up as a card that says exactly what will happen. Nothing runs until you allow it."],
  ["fingerprint", "Yours, on your machine", "Open source and self-hosted. Your data stays on your computer, and you can export or delete all of it anytime."],
];

function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [canSignup, setCanSignup] = useState(false);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  useEffect(() => { api.authOptions().then((o) => setCanSignup(o.signup)).catch(() => undefined); }, []);
  const signingUp = mode === "signup";
  const switchTo = (m: "signin" | "signup") => { setMode(m); setError(""); setPassword(""); };
  return (
    <div className="landing">
      <header className="landing-top">
        <span className="wordmark"><Avatar size={30} />esum</span>
        <a className="pill soft" href="https://github.com/lingcode-dev/esum" target="_blank" rel="noreferrer"><Icon name="download" size={18} />Get esum</a>
      </header>
      <main className="landing-hero">
        <Mark />
        <h1 className="headline">esum <span className="headline-avatar"><Avatar size={88} /></span>, AI that asks before it acts</h1>
        <form className="login" onSubmit={async (e) => {
          e.preventDefault(); setError(""); setBusy(true);
          try {
            if (signingUp) await api.signup(email, password);
            else await api.login(email, password);
            onDone();
          } catch (err) {
            setError(err instanceof ApiError ? err.message : signingUp ? "Could not create the account" : "Sign-in failed");
          } finally { setBusy(false); }
        }}>
          <h2 className="login-sub">{signingUp ? "Create your account" : "Sign in to your assistant"}</h2>
          <label className="field-pill"><span>Email</span>
            <input type="email" autoComplete={signingUp ? "email" : "username"} placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field-pill"><span>Password</span>
            <input type="password" autoComplete={signingUp ? "new-password" : "current-password"} minLength={signingUp ? 12 : undefined}
              aria-describedby={signingUp ? "pw-hint" : undefined} value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {signingUp && <p id="pw-hint" className="muted small form-hint">At least 12 characters. You'll add your own AI key next.</p>}
          {error && <p role="alert" className="error">{error}</p>}
          <button type="submit" className="primary big" disabled={busy}>
            {busy ? (signingUp ? "Creating your account…" : "Signing in…") : signingUp ? "Create account" : "Sign in"}
          </button>
          {canSignup && (
            <p className="switch-mode">
              {signingUp ? "Already have an account?" : "New to esum?"}{" "}
              <button type="button" className="link" onClick={() => switchTo(signingUp ? "signin" : "signup")}>
                {signingUp ? "Sign in" : "Create an account"}
              </button>
            </p>
          )}
        </form>
        <a className="pill learn" href="#learn">Learn more <Icon name="down" size={18} /></a>
      </main>
      <section id="learn" className="learn-more" aria-labelledby="learn-h">
        <h2 id="learn-h">Your personal agent, without the worry</h2>
        <ul>
          {POINTS.map(([icon, title, body]) => (
            <li key={title}><span className="tl-icon"><Icon name={icon} /></span><h3>{title}</h3><p>{body}</p></li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** The esum mark: a chat bubble with a check, because nothing happens until you say yes. */
function Mark() {
  return (
    <svg className="mark" viewBox="0 0 100 100" width="108" height="108" aria-hidden="true" focusable="false">
      <defs><linearGradient id="mark-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3b82ff" /><stop offset="1" stopColor="#0a4fe0" /></linearGradient></defs>
      <path d="M22 14h56a14 14 0 0 1 14 14v34a14 14 0 0 1-14 14H50L30 92V76h-8A14 14 0 0 1 8 62V28a14 14 0 0 1 14-14z" fill="url(#mark-g)" />
      <path d="M32 45l11 11 24-24" fill="none" stroke="#fff" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const RAIL: [Screen, string, IconName][] = [
  ["files", "Files", "notebook"], ["memory", "Memory", "bulb"], ["tasks", "Tasks", "tasks"], ["skills", "Skills and accounts", "shapes"],
];
const MENU: [Screen, string][] = [["tasks", "Tasks"], ["approvals", "Approvals"], ["automations", "Automations"], ["files", "Files"],
  ["memory", "Memory"], ["browser", "Browser"], ["notifications", "Notifications"], ["skills", "Skills and accounts"], ["shares", "Shared links"], ["data", "Your data"], ["settings", "Settings"]];

function Shell({ me, setMe, onLogout, onSignedOut }: { me: Me; setMe: (m: Me) => void; onLogout: () => void; onSignedOut: () => void }) {
  const [notice] = useState(() => {
    // Returning from a provider sign-in: /?oauth=connected|error&provider=Notion&note=...&reason=...
    const q = new URLSearchParams(window.location.search);
    const oauth = q.get("oauth");
    if (!oauth) return null;
    window.history.replaceState(null, "", window.location.pathname);
    const name = q.get("provider") ?? "The";
    return oauth === "connected"
      ? { ok: true, text: `${name} account connected.${q.get("note") ? " " + q.get("note") : ""}` }
      : { ok: false, text: q.get("reason") ?? `${name} sign-in failed.` };
  });
  const [screen, setScreen] = useState<Screen>("chat");
  const [menuOpen, setMenuOpen] = useState(false);
  const [listOpen, setListOpen] = useState(() => window.innerWidth >= WIDE_LIST);
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth >= WIDE_PANEL);
  const [pending, setPending] = useState(0);
  const [tick, setTick] = useState(0);
  const [live, setLive] = useState("");
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [active, setActive] = useState("");
  const [msgCount, setMsgCount] = useState(0);
  const [sharing, setSharing] = useState(false);
  const [fileFocus, setFileFocus] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => subscribe((type) => {
    setTick((t) => t + 1);
    if (type === "task.succeeded") setLive("A task finished.");
    if (type === "task.waiting_user") setLive("A task needs your reply.");
    if (type === "task.blocked") setLive("A task is blocked.");
    if (type === "approval.requested") setLive("An action needs your approval. It is shown in the chat.");
    if (type === "connection.reauth_required") setLive("A connected account needs reconnecting. Ask in the chat to reconnect it.");
    if (type === "connection_request.created") setLive("The assistant is asking about an account. Check the chat.");
  }), []);
  useEffect(() => { api2.approvals().then((a) => setPending(a.length)).catch(() => undefined); }, [tick]);
  useEffect(() => {
    api.conversations().then((c) => {
      setConvs(c);
      setActive((a) => a || (c.find((x) => x.is_default) ?? c[0])?.id || "");
    }).catch(() => undefined);
  }, [tick]);
  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [menuOpen]);

  const go = (s: Screen) => {
    setScreen(s); setMenuOpen(false);
    if (window.innerWidth < WIDE_PANEL) setPanelOpen(false);
  };
  const openSearch = useCallback(() => {
    setScreen("chat"); setListOpen(true);
    requestAnimationFrame(() => searchRef.current?.focus());
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openSearch(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [openSearch]);

  const pick = (id: string) => {
    setActive(id); setScreen("chat");
    if (window.innerWidth < WIDE_LIST) setListOpen(false);
  };
  const activeConv = convs.find((c) => c.id === active);
  const title = activeConv?.is_default ? "Main chat" : activeConv?.title ?? "";

  return (
    <div className="app">
      <nav aria-label="Main" className="rail">
        <span className="rail-logo"><Avatar size={36} /></span>
        <div className="rail-group">
          <button className="rail-btn" aria-label="Chat" data-tip="Chat" aria-current={screen === "chat" ? "page" : undefined} onClick={() => go("chat")}>
            <Icon name="chat" />
          </button>
          <button className="rail-btn" aria-label="Search" data-tip="Search  ⌘K" aria-keyshortcuts="Meta+K" onClick={openSearch}>
            <Icon name="search" />
          </button>
          {RAIL.map(([s, label, icon]) => (
            <button key={s} className="rail-btn" aria-label={label} data-tip={label} aria-current={screen === s ? "page" : undefined} onClick={() => go(s)}>
              <Icon name={icon} />
            </button>
          ))}
        </div>
        <div className="rail-group rail-bottom">
          <button className="rail-btn" aria-label="Your data" data-tip="Export your data" aria-current={screen === "data" ? "page" : undefined} onClick={() => go("data")}>
            <Icon name="download" />
          </button>
          <div className="menu" ref={menuRef}>
            <button className="rail-btn" aria-label="Menu" data-tip="More" aria-expanded={menuOpen} aria-controls="main-menu" onClick={() => setMenuOpen((o) => !o)}>
              <Icon name="menu" />
            </button>
            <ul id="main-menu" hidden={!menuOpen}>
              {MENU.map(([s, label]) => (
                <li key={s}><button aria-current={screen === s ? "page" : undefined} onClick={() => go(s)}>{label}</button></li>
              ))}
              <li className="menu-sep"><button onClick={onLogout}>Sign out</button></li>
            </ul>
          </div>
        </div>
      </nav>

      {screen === "chat" && listOpen && (
        <ChatList convs={convs} active={active} searchRef={searchRef} onPick={pick} onClose={() => setListOpen(false)}
          onCreated={(c) => { setConvs((all) => [...all, c]); pick(c.id); setLive(`Side chat “${c.title}” created.`); }} />
      )}

      <div className="main-col">
        <header className="topbar">
          <h1 className="sr-only">{me.assistant_name}</h1>
          {screen === "chat" && (
            <button className="icon-btn" aria-label={listOpen ? "Hide chat list" : "Show chat list"} aria-expanded={listOpen} onClick={() => setListOpen((o) => !o)}>
              <Icon name="sidebar" />
            </button>
          )}
          {screen === "chat" && <span className="topbar-title">{title}</span>}
          {me.mode === "demo" && <span className="badge" aria-label="Demo mode: no real provider calls">DEMO</span>}
          <span className="spacer" />
          {pending > 0 && (
            <button className="pill warn" onClick={() => go("approvals")} aria-label={`Approvals, ${pending} waiting`}>
              <Icon name="shield" size={18} />{pending} waiting
            </button>
          )}
          {screen === "chat" && msgCount > 0 && (
            <button className="pill" onClick={() => setSharing(true)}><Icon name="share" size={18} />Share</button>
          )}
          {!panelOpen && (
            <button className="avatar-btn" aria-label="Assistant profile" aria-expanded={false} onClick={() => setPanelOpen(true)}>
              <Avatar size={34} />
            </button>
          )}
        </header>
        {me.setup_required.length > 0 && <div role="alert" className="setup">Setup needed: {me.setup_required.join("; ")}</div>}
        <div role="status" aria-live="polite" className="sr-only">{live}</div>
        <main className={screen === "chat" ? "chat-main" : "page"}>
          {screen === "chat" && notice && <p role={notice.ok ? "status" : "alert"} className={notice.ok ? "notice" : "error"}>{notice.text}</p>}
          {screen === "chat" && (
            <Chat active={active} title={title} tick={tick} announce={setLive} sharing={sharing} onCloseShare={() => setSharing(false)}
              onCount={setMsgCount} onOpenFile={(id) => { setFileFocus(id); setScreen("files"); }} />
          )}
          {screen === "skills" && <Skills me={me} onMe={setMe} tick={tick} announce={setLive} />}
          {screen === "shares" && <SharedLinks tick={tick} announce={setLive} />}
          {screen === "tasks" && <Tasks tick={tick} />}
          {screen === "approvals" && <Approvals tick={tick} announce={setLive} />}
          {screen === "notifications" && <Notifications tick={tick} />}
          {screen === "automations" && <Automations me={me} tick={tick} announce={setLive} />}
          {screen === "browser" && <Browser tick={tick} announce={setLive} />}
          {screen === "data" && <Data me={me} tick={tick} announce={setLive} />}
          {screen === "files" && <Files tick={tick} announce={setLive} focusId={fileFocus || undefined} />}
          {screen === "memory" && <Memory tick={tick} announce={setLive} />}
          {screen === "settings" && <Settings me={me} onMe={setMe} onSignedOut={onSignedOut} announce={setLive} />}
        </main>
      </div>

      {panelOpen && <Profile me={me} tick={tick} onClose={() => setPanelOpen(false)} onGo={go} />}
    </div>
  );
}

function ChatList({ convs, active, searchRef, onPick, onClose, onCreated }: {
  convs: Conversation[]; active: string; searchRef: RefObject<HTMLInputElement>;
  onPick: (id: string) => void; onClose: () => void; onCreated: (c: Conversation) => void;
}) {
  const [query, setQuery] = useState("");
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const q = query.trim().toLowerCase();
  const main = convs.find((c) => c.is_default) ?? convs[0];
  const sides = convs.filter((c) => c !== main && c.title.toLowerCase().includes(q));
  const showMain = main && (!q || "main chat".includes(q) || main.title.toLowerCase().includes(q));

  return (
    <aside className="chats" aria-label="Conversations" onKeyDown={(e) => { if (e.key === "Escape" && window.innerWidth < WIDE_LIST) onClose(); }}>
      <label className="search">
        <Icon name="search" size={20} />
        <span className="sr-only">Search chats</span>
        <input ref={searchRef} type="search" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
      </label>
      {showMain && (
        <button className="conv" aria-current={main.id === active ? "true" : undefined} onClick={() => onPick(main.id)}>Main chat</button>
      )}
      <div className="side-head">
        <span>Side chats</span>
        <button className="icon-btn small" aria-label="New side chat" onClick={() => { setNaming(true); setError(""); }}><Icon name="plus" size={20} /></button>
      </div>
      {naming && (
        <form className="name-chat" onSubmit={async (e) => {
          e.preventDefault();
          if (!name.trim()) return;
          try { onCreated(await api.createConversation(name.trim())); setName(""); setNaming(false); }
          catch (err) { setError(err instanceof ApiError ? err.message : "Could not create the chat."); }
        }}>
          <input autoFocus aria-label="Side chat name" placeholder="Name this chat, then press Enter" value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); setNaming(false); setName(""); } }}
            onBlur={() => { if (!name.trim()) setNaming(false); }} />
          {error && <p role="alert" className="error small">{error}</p>}
        </form>
      )}
      <ul className="conv-list">
        {sides.map((c) => (
          <li key={c.id}><button className="conv" aria-current={c.id === active ? "true" : undefined} onClick={() => onPick(c.id)}>{c.title}</button></li>
        ))}
      </ul>
      {sides.length === 0 && !naming && (
        <p className="muted small hint">{q ? "No chats match." : "Side chats keep a separate topic out of your main chat."}</p>
      )}
    </aside>
  );
}

const SUGGESTIONS = [
  "Go through my inbox and draft replies",
  "What's on my calendar today?",
  "Connect my Google account",
  "Summarize my Notion meeting notes",
  "Remind me every weekday at 8:00 to review email",
  "Look up the latest news on a topic for me",
];

type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean; start(): void; stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onend: (() => void) | null;
};
const SpeechRecognition = ((window as unknown as Record<string, unknown>).SpeechRecognition
  ?? (window as unknown as Record<string, unknown>).webkitSpeechRecognition) as (new () => Recognition) | undefined;

const GAP_MS = 30 * 60_000;

function Chat({ active, title, tick, announce, sharing, onCloseShare, onCount, onOpenFile }: {
  active: string; title: string; tick: number; announce: (msg: string) => void; sharing: boolean; onCloseShare: () => void;
  onCount: (n: number) => void; onOpenFile: (id: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [tasks, setTasks] = useState<Record<string, Task>>({});
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<string>("");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [listening, setListening] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recRef = useRef<Recognition | null>(null);

  const reload = useCallback(async () => {
    if (!active) return;
    setMessages(await api.messages(active));
    setTasks(Object.fromEntries((await api.tasks()).items.map((t) => [t.id, t])));
    setApprovals(await api2.approvals());
  }, [active]);
  useEffect(() => { void reload(); }, [reload, tick]);
  useEffect(() => { onCount(messages.length); }, [messages.length, onCount]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [messages.length, approvals.length]);
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [draft]);
  useEffect(() => () => recRef.current?.stop(), []);

  const mine = Object.values(tasks).filter((t) => t.conversation_id === active);
  const waiting = mine.filter((t) => t.state === "waiting_user");
  const working = mine.some((t) => t.state === "running" || t.state === "queued");
  const lastOfTask: Record<string, number> = {};
  messages.forEach((m, i) => { if (m.task_id) lastOfTask[m.task_id] = i; });

  const dictate = () => {
    if (!SpeechRecognition) return;
    if (listening) { recRef.current?.stop(); return; }
    const rec = new SpeechRecognition();
    const base = draft;
    rec.lang = navigator.language; rec.interimResults = true; rec.continuous = true;
    rec.onresult = (e) => {
      const said = Array.from(e.results).map((r) => r[0].transcript).join("");
      setDraft(base ? `${base} ${said}` : said);
    };
    rec.onend = () => { setListening(false); recRef.current = null; };
    recRef.current = rec;
    rec.start();
    setListening(true);
    announce("Listening. Press the microphone again to stop.");
  };

  return (
    <section className="chat" aria-labelledby="chat-h">
      <h2 id="chat-h" className="sr-only">Chat</h2>
      {sharing && <ShareDialog conversationId={active} title={title || "Conversation"} messages={messages} announce={announce} onClose={onCloseShare} />}
      {messages.length === 0 && (
        <div className="welcome">
          <Avatar size={96} />
          <p className="hello">What can I help with?</p>
          <p className="muted">Ask for anything, including connecting your accounts. Changes always wait for your OK.</p>
          <ul className="options" aria-label="Suggestions">
            {SUGGESTIONS.map((x) => (
              <li key={x}><button className="option" onClick={() => { setDraft(x); inputRef.current?.focus(); }}>{x}</button></li>
            ))}
          </ul>
        </div>
      )}
      <ol className="messages" aria-label="Messages">
        {messages.map((m, i) => {
          const t = m.task_id ? tasks[m.task_id] : undefined;
          // A task's approval cards follow its latest message, so a summary it posted comes before its drafts.
          const asks = m.task_id && lastOfTask[m.task_id] === i ? approvals.filter((a) => a.task_id === m.task_id) : [];
          const prev = messages[i - 1];
          const showStamp = !prev || new Date(m.created_at).getTime() - new Date(prev.created_at).getTime() > GAP_MS;
          return (<Fragment key={m.id}>
            {showStamp && <li className="stamp"><time dateTime={m.created_at}>{stamp(m.created_at)}</time></li>}
            <li className={`msg ${m.role}${m.connection_request ? " has-card" : ""}`}>
              <h3 className="sr-only">{m.role === "user" ? "You" : m.role === "system" ? "System" : "Assistant"}</h3>
              <p className={m.connection_request ? "sr-only" : undefined}>{m.content}</p>
              {t && m.role === "user" && t.state !== "succeeded" && <TaskChip task={t} />}
              <ArtifactLinks ids={m.artifact_ids} onOpen={onOpenFile} />
              {m.connection_request && <ConnectionCard req={m.connection_request} onChanged={async (msg) => { announce(msg); await reload(); }} />}
            </li>
            {asks.map((a) => (
              <li key={a.id} className="msg has-card">
                <h3 className="sr-only">Approval needed</h3>
                <ApprovalCard a={a} announce={announce} onDone={reload} />
              </li>
            ))}
          </Fragment>);
        })}
        {working && (
          <li className="msg assistant typing" aria-hidden="true"><span /><span /><span /></li>
        )}
      </ol>
      <div ref={endRef} className="chat-end" />
      <form className="composer" onSubmit={async (e) => {
        e.preventDefault(); setError("");
        if (!draft.trim() || !active) return;
        recRef.current?.stop();
        try { await api.send(active, draft, replyTo || undefined); setDraft(""); setReplyTo(""); await reload(); }
        catch (err) { setError(err instanceof ApiError ? err.message : "Send failed"); }
      }}>
        {waiting.length > 0 && (
          // CHAT-01: never guess whether a message is a new task or a reply to existing work.
          <label className="send-as">Send as{" "}
            <select value={replyTo} onChange={(e) => setReplyTo(e.target.value)}>
              <option value="">New task</option>
              {waiting.map((t) => <option key={t.id} value={t.id}>Reply to: {t.intent.slice(0, 60)}</option>)}
            </select>
          </label>
        )}
        <div className="composer-box">
          <button type="button" className="icon-btn" aria-label="Attach a file" disabled={uploading} onClick={() => fileRef.current?.click()}>
            <Icon name="plus" />
          </button>
          <input ref={fileRef} type="file" hidden tabIndex={-1} onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            setUploading(true); setError("");
            try {
              const a = await files.upload(f);
              setDraft((d) => (d ? `${d}\n` : "") + `I attached “${a.name}” in Files.`);
              announce(`Uploaded ${a.name}.`);
              inputRef.current?.focus();
            } catch (err) { setError(err instanceof ApiError ? err.message : "Upload failed"); }
            finally { setUploading(false); }
          }} />
          <label className="grow"><span className="sr-only">Message</span>
            <textarea ref={inputRef} value={draft} onChange={(e) => setDraft(e.target.value)} rows={1}
              placeholder={uploading ? "Uploading…" : "Message"}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); (e.currentTarget.form as HTMLFormElement).requestSubmit(); } }} />
          </label>
          {SpeechRecognition && (
            <button type="button" className={`icon-btn${listening ? " listening" : ""}`} aria-label="Dictate" aria-pressed={listening} onClick={dictate}>
              <Icon name="mic" />
            </button>
          )}
          <button type="submit" className={`send${draft.trim() ? "" : " idle"}`} aria-label="Send" disabled={!active}>
            <Icon name="up" size={20} />
          </button>
        </div>
        {error && <p role="alert" className="error">{error}</p>}
      </form>
    </section>
  );
}

function TaskChip({ task }: { task: Task }) {
  return <span className={`chip s-${task.state}`}>Task: {STATE_LABEL[task.state]}{task.blocker_detail ? ` — ${task.blocker_detail}` : ""}</span>;
}

function Tasks({ tick }: { tick: number }) {
  const [filter, setFilter] = useState("");
  const [items, setItems] = useState<Task[]>([]);
  const [error, setError] = useState("");
  const refresh = useCallback(() => api.tasks(filter || undefined).then((r) => setItems(r.items)), [filter]);
  useEffect(() => { void refresh(); }, [refresh, tick]);
  const act = async (fn: () => Promise<unknown>) => { setError(""); try { await fn(); await refresh(); } catch (e) { setError(e instanceof ApiError ? e.message : "Action failed"); } };

  return (
    <section aria-labelledby="tasks-h">
      <h2 id="tasks-h">Tasks</h2>
      <label>Filter by state{" "}
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All</option>
          {Object.entries(STATE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      {error && <p role="alert" className="error">{error}</p>}
      {items.length > 0 && (
        <table>
          <thead><tr><th scope="col">Task</th><th scope="col">State</th><th scope="col">Current step</th><th scope="col">Active time</th><th scope="col">Last activity</th><th scope="col">Actions</th></tr></thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id}>
                <td>{t.intent.slice(0, 80)}{t.retry_of && <small> (retry)</small>}</td>
                <td><TaskChip task={t} /></td>
                <td>{t.current_step ?? "—"}</td>
                <td>{(t.active_ms / 1000).toFixed(1)} s</td>
                <td>{t.last_activity_at ? stamp(t.last_activity_at) : "—"}</td>
                <td className="actions">
                  {!["succeeded", "failed", "cancelled"].includes(t.state) && <button onClick={() => act(() => api.cancel(t.id))}>Stop</button>}
                  {["blocked", "waiting_user"].includes(t.state) && <button onClick={() => act(() => api.resume(t.id))}>Resume</button>}
                  {["succeeded", "failed", "cancelled"].includes(t.state) && <button onClick={() => act(() => api.retry(t.id))}>Retry</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {items.length === 0 && <Empty>No tasks yet. Ask for something in Chat and it will show up here.</Empty>}
    </section>
  );
}

function Notifications({ tick }: { tick: number }) {
  const [items, setItems] = useState<Notification[]>([]);
  useEffect(() => { api.notifications().then(setItems); }, [tick]);
  return (
    <section aria-labelledby="notif-h">
      <h2 id="notif-h">Notifications</h2>
      <ul className="notifs">
        {items.map((n) => (
          <li key={n.id} className={n.read_at ? "read" : "unread"}>
            <div className="grow">
              <strong>{n.title}</strong> <span>{n.body}</span>
              <div><time dateTime={n.created_at}>{stamp(n.created_at)}</time></div>
            </div>
            {!n.read_at && <button onClick={async () => { await api.markRead(n.id); setItems(await api.notifications()); }}>Mark read</button>}
          </li>
        ))}
      </ul>
      {items.length === 0 && <Empty>You're all caught up.</Empty>}
    </section>
  );
}
