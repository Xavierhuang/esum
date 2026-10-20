import { useCallback, useEffect, useState } from "react";
import { Action, api2, ApiError, Approval, Decision, PreviewField } from "../api";

function relative(iso: string): string {
  const mins = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  if (mins <= 0) return "expired";
  return mins < 90 ? `in ${mins} min` : `in ${Math.round(mins / 60)} h`;
}

function Fields({ fields }: { fields: PreviewField[] }) {
  return (
    <dl className="fields">
      {fields.map((f, i) => (
        <div key={i} className="field">
          <dt>{f.label}</dt>
          <dd>
            {f.before !== undefined && <><del aria-label={`was ${f.before}`}>{f.before}</del>{" → "}</>}
            {f.multiline ? <pre>{f.value}</pre> : <span>{f.value}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

const ANNOUNCE: Record<Decision, Record<string, (title: string) => string>> = {
  allow_once: { approved: (t) => `Approved: ${t}. The assistant will continue.` },
  edit_and_allow: { approved: (t) => `Approved your edited version: ${t}. The assistant will continue.` },
  skip: { skipped: (t) => `Skipped: ${t}. Nothing was done, and the assistant will continue.` },
  deny: { denied: (t) => `Denied: ${t}. The task is stopped.` },
};

/** One pending change, shown exactly as it will be sent. Used on the Approvals screen and inline in the chat.
 *  Emails can be edited before approving: the server records the edited email as a new action you approve. */
export function ApprovalCard({ a, announce, onDone }: { a: Approval; announce: (s: string) => void; onDone: () => void | Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const editable = a.preview.tool === "gmail.send_message";
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(String(a.preview.payload.subject ?? ""));
  const [body, setBody] = useState(String(a.preview.payload.body ?? ""));
  const titleId = `ap-${a.id}`;
  const descId = `ap-d-${a.id}`;
  const decide = async (decision: Decision) => {
    setError(""); setBusy(true);
    try {
      const r = await api2.decide(a, decision, decision === "edit_and_allow" ? { subject, body } : undefined);
      const say = ANNOUNCE[decision][r.outcome];
      announce(say ? say(a.preview.title) : `Not done: this request is ${r.outcome}.`);
      await onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <article className="card approval" aria-labelledby={titleId} aria-describedby={descId}>
      <h3 id={titleId}>{a.preview.title}</h3>
      <p id={descId} className="muted">
        For task “{a.task_intent.slice(0, 80)}”. {a.preview.side_effects} Expires {relative(a.expires_at)}
        {" "}(<time dateTime={a.expires_at}>{new Date(a.expires_at).toLocaleString()}</time>).
      </p>
      {editing ? (
        <form className="edit" onSubmit={(e) => { e.preventDefault(); void decide("edit_and_allow"); }}>
          <Fields fields={a.preview.fields.filter((f) => !["Subject", "Body"].includes(f.label))} />
          <label>Subject<input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
          <label>Body<textarea rows={8} value={body} onChange={(e) => setBody(e.target.value)} /></label>
          <p className="muted">To change who receives it, ask the assistant for a new draft.</p>
          <div className="row">
            <button className="primary" type="submit" disabled={busy || !body.trim()}>Approve edited version</button>
            <button type="button" disabled={busy} onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <>
          <Fields fields={a.preview.fields} />
          <div className="row">
            <button className="primary" disabled={busy} onClick={() => decide("allow_once")}>Allow once</button>
            {editable && <button disabled={busy} onClick={() => setEditing(true)}>Edit</button>}
            <button disabled={busy} onClick={() => decide("skip")} aria-describedby={`ap-h-${a.id}`}>Skip</button>
            <button disabled={busy} onClick={() => decide("deny")} aria-describedby={`ap-h-${a.id}`}>Deny</button>
          </div>
          <p id={`ap-h-${a.id}`} className="muted small">Skip: not this one, the assistant carries on. Deny: stop the task.</p>
        </>
      )}
      {error && <p role="alert" className="error">{error}</p>}
    </article>
  );
}

export function Approvals({ tick, announce }: { tick: number; announce: (s: string) => void }) {
  const [items, setItems] = useState<Approval[]>([]);
  const [unknown, setUnknown] = useState<Action[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const refresh = useCallback(async () => {
    setItems(await api2.approvals());
    setUnknown(await api2.unknownActions());
  }, []);
  useEffect(() => { void refresh(); }, [refresh, tick]);

  const run = async (key: string, fn: () => Promise<string>) => {
    setError(""); setBusy(key);
    try { announce(await fn()); await refresh(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Action failed"); }
    finally { setBusy(""); }
  };

  return (
    <section aria-labelledby="approvals-h">
      <h2 id="approvals-h">Approvals</h2>
      {error && <p role="alert" className="error">{error}</p>}
      {items.length === 0 && <p>Nothing is waiting for your approval.</p>}
      {items.map((a) => <ApprovalCard key={a.id} a={a} announce={announce} onDone={refresh} />)}

      <h2 id="unknown-h">Needs checking</h2>
      {unknown.length === 0 && <p>No changes with an unknown outcome.</p>}
      {unknown.map((x) => (
        <article key={x.id} className="card unknown" aria-labelledby={`u-${x.id}`}>
          <h3 id={`u-${x.id}`}>{x.preview.title}: outcome unknown</h3>
          <p>The connection dropped after this was sent to the provider, so it may or may not have happened. It will not be retried automatically.</p>
          <Fields fields={x.preview.fields} />
          <div className="row">
            <button disabled={!!busy} onClick={() => run(x.id, async () => {
              const r = await api2.reconcile(x.id);
              return r.state === "unknown" ? "Could not confirm automatically. Please check the account and answer below." : `Checked: the change ${r.state === "succeeded" ? "did happen" : "did not happen"}.`;
            })}>Check with provider</button>
            <button disabled={!!busy} onClick={() => run(x.id, async () => { await api2.resolve(x.id, "happened"); return "Marked as happened."; })}>It happened</button>
            <button disabled={!!busy} onClick={() => run(x.id, async () => { await api2.resolve(x.id, "did_not_happen"); return "Marked as did not happen. A new attempt will need a new approval."; })}>It did not happen</button>
          </div>
        </article>
      ))}
    </section>
  );
}
