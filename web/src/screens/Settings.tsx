import { FormEvent, useState } from "react";
import { api2, ApiError, Me, ResponseStyle } from "../api";

const STYLES: [ResponseStyle, string][] = [
  ["concise", "Concise: short answers, the main point first"], ["detailed", "Detailed: thorough answers with reasons"],
  ["casual", "Casual: friendly and relaxed"], ["formal", "Formal: polished and professional"],
];
const ZONES: string[] = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.("timeZone") ?? [];

const message = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message.charAt(0).toUpperCase() + e.message.slice(1) : fallback);

/** The owner's settings: what the assistant is called and how it talks, and the account itself. */
export function Settings({ me, onMe, onSignedOut, announce }: { me: Me; onMe: (m: Me) => void; onSignedOut: () => void; announce: (m: string) => void }) {
  return (
    <section aria-labelledby="settings-h" className="settings">
      <h2 id="settings-h">Settings</h2>
      <AssistantCard me={me} onMe={onMe} announce={announce} />
      <PasswordCard announce={announce} />
      <DeleteAccountCard me={me} onSignedOut={onSignedOut} />
    </section>
  );
}

function AssistantCard({ me, onMe, announce }: { me: Me; onMe: (m: Me) => void; announce: (m: string) => void }) {
  const [name, setName] = useState(me.assistant_name);
  const [style, setStyle] = useState(me.response_style as ResponseStyle);
  const [zone, setZone] = useState(me.time_zone);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const changed = name.trim() !== me.assistant_name || style !== me.response_style || zone !== me.time_zone;

  const save = async (e: FormEvent) => {
    e.preventDefault(); setError(""); setBusy(true);
    try {
      onMe(await api2.updateMe({ assistant_name: name.trim(), response_style: style, time_zone: zone.trim() }));
      announce("Assistant settings saved.");
    } catch (err) { setError(message(err, "Could not save.")); }
    finally { setBusy(false); }
  };

  return (
    <form className="card" aria-labelledby="assistant-h" onSubmit={save}>
      <h3 id="assistant-h">Your assistant</h3>
      {error && <p role="alert" className="error">{error}</p>}
      <label className="block">Name
        <input value={name} required maxLength={64} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="block">How it answers
        <select value={style} onChange={(e) => setStyle(e.target.value as ResponseStyle)}>
          {STYLES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </label>
      <label className="block">Time zone
        <input value={zone} required list="zones" spellCheck={false} aria-describedby="zone-hint" onChange={(e) => setZone(e.target.value)} />
      </label>
      <datalist id="zones">{ZONES.map((z) => <option key={z} value={z} />)}</datalist>
      <p id="zone-hint" className="muted small">Used for schedules and for “today” and “tomorrow”, for example America/New_York.</p>
      <button type="submit" disabled={!changed || busy}>Save</button>
    </form>
  );
}

function PasswordCard({ announce }: { announce: (m: string) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  const save = async (e: FormEvent) => {
    e.preventDefault(); setError(""); setDone("");
    try {
      await api2.changePassword(current, next);
      setCurrent(""); setNext("");
      setDone("Password changed. You were signed out everywhere else."); announce("Password changed.");
    } catch (err) { setError(message(err, "Could not change the password.")); }
  };

  return (
    <form className="card" aria-labelledby="password-h" onSubmit={save}>
      <h3 id="password-h">Password</h3>
      {error && <p role="alert" className="error">{error}</p>}
      {done && <p role="status">{done}</p>}
      <label className="block">Current password
        <input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
      </label>
      <label className="block">New password
        <input type="password" autoComplete="new-password" required minLength={12} aria-describedby="new-pw-hint" value={next} onChange={(e) => setNext(e.target.value)} />
      </label>
      <p id="new-pw-hint" className="muted small">At least 12 characters.</p>
      <button type="submit">Change password</button>
    </form>
  );
}

function DeleteAccountCard({ me, onSignedOut }: { me: Me; onSignedOut: () => void }) {
  const [confirm, setConfirm] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const matches = confirm.trim().toLowerCase() === me.email.toLowerCase();

  const remove = async (e: FormEvent) => {
    e.preventDefault(); setError("");
    try { await api2.deleteAccount(confirm, password); onSignedOut(); }
    catch (err) { setError(message(err, "Could not delete the account.")); }
  };

  return (
    <form className="card danger" aria-labelledby="delete-account-h" onSubmit={remove}>
      <h3 id="delete-account-h">Delete account</h3>
      <p>Deletes everything in “Your data”, then your account and sign-in. Your saved model key and website sign-ins are erased,
        and connected accounts are disconnected. This cannot be undone.</p>
      {error && <p role="alert" className="error">{error}</p>}
      <label className="block">Type your email address ({me.email}) to confirm
        <input value={confirm} autoComplete="off" onChange={(e) => setConfirm(e.target.value)} />
      </label>
      <label className="block">Password
        <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      <button type="submit" disabled={!matches || !password}>Delete my account</button>
    </form>
  );
}
