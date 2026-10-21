import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { api, api2, Approval, Automation, automationsApi, Connection, Me, Task, TaskState } from "../api";
import { Avatar, dayLabel, Icon, IconName, stamp, timeLabel } from "../ui";

type Tab = "activity" | "approvals" | "automations" | "accounts";
const TABS: [Tab, string, IconName][] = [
  ["activity", "Activity", "list"], ["approvals", "Waiting for you", "shield"],
  ["automations", "Scheduled", "clock"], ["accounts", "Accounts", "fingerprint"],
];

const STATE: Record<TaskState, [string, IconName]> = {
  queued: ["Queued", "dot"], running: ["Working on it", "dot"], waiting_approval: ["Needs your OK", "alert"],
  waiting_user: ["Needs your reply", "alert"], blocked: ["Blocked", "alert"], succeeded: ["Done", "check"],
  failed: ["Failed", "xcircle"], cancelled: ["Cancelled", "xcircle"],
};
const ACCOUNT_STATUS: Record<string, string> = { connected: "Connected", reauth_required: "Needs reconnecting", error: "Error" };

type Go = (screen: "approvals" | "automations" | "skills" | "tasks") => void;

/** The assistant's profile: who it is, whether it is connected, and what it has been doing. */
export function Profile({ me, tick, onClose, onGo }: { me: Me; tick: number; onClose: () => void; onGo: Go }) {
  const [tab, setTab] = useState<Tab>("activity");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [autos, setAutos] = useState<Automation[]>([]);
  const [conns, setConns] = useState<Connection[]>([]);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    api.tasks().then((r) => setTasks(r.items)).catch(() => undefined);
    api2.approvals().then(setApprovals).catch(() => undefined);
    automationsApi.list().then(setAutos).catch(() => undefined);
    api2.connections().then(setConns).catch(() => undefined);
  }, [tick]);

  const connected = conns.some((c) => c.status === "connected");
  const onTabKey = (e: KeyboardEvent, i: number) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    const next = (i + step + TABS.length) % TABS.length;
    setTab(TABS[next][0]);
    tabRefs.current[next]?.focus();
  };

  return (
    <aside className="profile" aria-labelledby="profile-h">
      <button className="icon-btn profile-close" aria-label="Close profile" onClick={onClose}><Icon name="x" /></button>
      <div className="profile-head">
        <Avatar size={128} />
        <h2 id="profile-h">{me.assistant_name}</h2>
        <p className={`presence${connected ? " on" : ""}`}><span className="presence-dot" />{connected ? "Connected" : "No accounts yet"}</p>
      </div>

      <div role="tablist" aria-label="Assistant details" className="seg">
        {TABS.map(([key, label, icon], i) => (
          <button key={key} ref={(el) => { tabRefs.current[i] = el; }} role="tab" id={`pt-${key}`} aria-controls="pt-panel"
            aria-selected={tab === key} tabIndex={tab === key ? 0 : -1} aria-label={label} data-tip={label}
            onClick={() => setTab(key)} onKeyDown={(e) => onTabKey(e, i)}>
            <Icon name={icon} size={20} />
          </button>
        ))}
      </div>

      <div role="tabpanel" id="pt-panel" aria-labelledby={`pt-${tab}`} className="profile-body">
        {tab === "activity" && <Activity tasks={tasks} onGo={onGo} />}
        {tab === "approvals" && (
          <Rows empty="Nothing is waiting for your OK." more={["Open approvals", () => onGo("approvals")]}
            items={approvals.map((a) => ({ id: a.id, icon: "shield", title: a.preview.title, sub: a.task_intent, meta: `Expires ${stamp(a.expires_at).replace(/^(Today|Yesterday|Tomorrow)/, (w) => w.toLowerCase())}` }))} />
        )}
        {tab === "automations" && (
          <Rows empty="Nothing scheduled. Ask in chat, for example “every weekday at 8:00, review my email”."
            more={["Manage automations", () => onGo("automations")]}
            items={autos.map((a) => ({
              id: a.id, icon: "clock", title: a.name, sub: a.description,
              meta: !a.enabled ? "Off" : a.paused_reason ? "Paused" : a.next_run_local ? `Next: ${a.next_run_local}` : "",
            }))} />
        )}
        {tab === "accounts" && (
          <Rows empty="No accounts yet. Ask in chat to connect one." more={["Manage accounts", () => onGo("skills")]}
            items={conns.map((c) => ({
              id: c.id, icon: "fingerprint", title: c.account_label, sub: c.capabilities.map((k) => k.label).join(" · "),
              meta: ACCOUNT_STATUS[c.status] ?? c.status,
            }))} />
        )}
      </div>
    </aside>
  );
}

function Activity({ tasks, onGo }: { tasks: Task[]; onGo: Go }) {
  const when = (t: Task) => t.last_activity_at ?? t.created_at;
  const sorted = [...tasks].sort((a, b) => when(b).localeCompare(when(a))).slice(0, 40);
  const groups: [string, Task[]][] = [];
  for (const t of sorted) {
    const day = dayLabel(when(t));
    const g = groups[groups.length - 1];
    if (g && g[0] === day) g[1].push(t); else groups.push([day, [t]]);
  }
  if (groups.length === 0) return <p className="muted profile-empty">Nothing yet. What the assistant does will show up here.</p>;
  return (
    <>
      {groups.map(([day, items]) => (
        <section key={day} className="tl-day">
          <h3>{day}</h3>
          <ul className="timeline">
            {items.map((t) => {
              const [label, icon] = STATE[t.state];
              return (
                <li key={t.id} className={`tl st-${t.state}`}>
                  <span className="tl-icon"><Icon name={icon} size={20} /></span>
                  <div>
                    <p className="tl-title">{t.intent}</p>
                    <p className="tl-sub">{label}</p>
                    <p className="tl-time">{timeLabel(when(t))}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <button className="link more" onClick={() => onGo("tasks")}>All tasks</button>
    </>
  );
}

type Row = { id: string; icon: IconName; title: string; sub: string; meta: string };

function Rows({ items, empty, more }: { items: Row[]; empty: string; more: [string, () => void] }) {
  return (
    <>
      {items.length === 0 ? <p className="muted profile-empty">{empty}</p> : (
        <ul className="timeline">
          {items.map((r) => (
            <li key={r.id} className="tl">
              <span className="tl-icon"><Icon name={r.icon} size={20} /></span>
              <div>
                <p className="tl-title">{r.title}</p>
                {r.sub && <p className="tl-sub">{r.sub}</p>}
                {r.meta && <p className="tl-time">{r.meta}</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <button className="link more" onClick={more[1]}>{more[0]}</button>
    </>
  );
}
