import { useState } from "react";
import { api, api2, ApiError, Me, ModelKey, ModelProvider } from "../api";
import { Avatar, stamp } from "../ui";

const PROVIDERS: { id: ModelProvider; label: string; model: (me: Me) => string; help: string; link?: string }[] = [
  { id: "anthropic", label: "Anthropic", model: (me) => me.default_model, help: "A Claude API key from the Claude Console.", link: "https://platform.claude.com/settings/keys" },
  { id: "zenmux", label: "ZenMux", model: () => "anthropic/claude-sonnet-4.5", help: "A ZenMux API key. Use a model that ZenMux offers through its Anthropic-compatible API.", link: "https://zenmux.ai" },
  { id: "custom", label: "Custom", model: () => "", help: "Any provider that speaks the Anthropic Messages API, at a public https:// address." },
];

/** Provider, key and model. Saving checks the key with the provider before storing it encrypted. */
export function KeyForm({ me, current, submitLabel, onSaved, onCancel }: {
  me: Me; current?: ModelKey | null; submitLabel: string; onSaved: (k: ModelKey) => void | Promise<void>; onCancel?: () => void;
}) {
  const [provider, setProvider] = useState<ModelProvider>(current?.provider ?? "anthropic");
  const [model, setModel] = useState(current?.model ?? me.default_model);
  const [baseUrl, setBaseUrl] = useState(current?.provider === "custom" ? current.base_url ?? "" : "");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const p = PROVIDERS.find((x) => x.id === provider)!;

  const pick = (id: ModelProvider) => {
    setProvider(id); setError("");
    setModel(current?.provider === id ? current.model : PROVIDERS.find((x) => x.id === id)!.model(me));
  };

  return (
    <form className="key-form" onSubmit={async (e) => {
      e.preventDefault(); setError(""); setBusy(true);
      try {
        const saved = await api2.saveModelKey({ provider, model: model.trim(), api_key: apiKey.trim(), base_url: provider === "custom" ? baseUrl.trim() : null });
        setApiKey("");
        await onSaved(saved);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not save the key.");
      } finally {
        setBusy(false);
      }
    }}>
      <fieldset className="provider-pick">
        <legend>Provider</legend>
        {PROVIDERS.map((x) => (
          <label key={x.id} className={provider === x.id ? "on" : undefined}>
            <input type="radio" name="provider" value={x.id} checked={provider === x.id} onChange={() => pick(x.id)} />
            {x.label}
          </label>
        ))}
      </fieldset>
      <p className="muted small key-help">
        {p.help}{p.link && <> <a href={p.link} target="_blank" rel="noreferrer">Get a key</a>.</>}
      </p>
      {provider === "custom" && (
        <label className="field-pill"><span>Address</span>
          <input type="url" required placeholder="https://gateway.example.com/api/anthropic" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </label>
      )}
      <label className="field-pill"><span>API key</span>
        <input type="password" required autoComplete="off" spellCheck={false} placeholder={current ? `Saved key ${current.key_hint}. Paste a new one to replace it.` : "Paste your key"}
          value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
      </label>
      <label className="field-pill"><span>Model</span>
        <input type="text" required spellCheck={false} placeholder="claude-opus-5-5" value={model} onChange={(e) => setModel(e.target.value)} />
      </label>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="row">
        <button type="submit" className="primary big grow" disabled={busy || !apiKey.trim() || !model.trim()}>{busy ? "Checking the key…" : submitLabel}</button>
        {onCancel && <button type="button" className="big" onClick={onCancel} disabled={busy}>Cancel</button>}
      </div>
      <p className="muted small key-note">Your key is checked with one tiny request, then stored encrypted. Only its last four characters are ever shown again.</p>
    </form>
  );
}

/** The first thing a new owner sees in live mode when there is no key yet. */
export function KeyOnboarding({ me, onDone, onLogout }: { me: Me; onDone: () => void; onLogout: () => void }) {
  return (
    <div className="landing">
      <header className="landing-top">
        <span className="wordmark"><Avatar size={30} />esum</span>
        <button className="pill soft" onClick={onLogout}>Sign out</button>
      </header>
      <main className="landing-hero key-onboarding">
        <Avatar size={96} />
        <h1 className="headline small-headline">Bring your own key</h1>
        <p className="lede">esum runs on your own AI account, so you stay in control of cost and data. Paste a key from Anthropic, ZenMux or another compatible provider.</p>
        <KeyForm me={me} submitLabel="Save and start" onSaved={onDone} />
      </main>
    </div>
  );
}

/** The model section of Skills and accounts. */
export function ModelSection({ me, onMe, announce }: { me: Me; onMe: (m: Me) => void; announce: (s: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const key = me.model_key;
  const refresh = async () => onMe(await api.me());

  return (
    <section className="card model-card" aria-labelledby="model-h">
      <h3 id="model-h">AI model</h3>
      {editing ? (
        <KeyForm me={me} current={key} submitLabel={key ? "Save new key" : "Save key"} onCancel={() => setEditing(false)}
          onSaved={async (k) => { setEditing(false); announce(`Saved your ${k.provider_label} key.`); await refresh(); }} />
      ) : key ? (
        <>
          <p className="model-line"><strong>{key.provider_label}</strong> · {key.model} · key {key.key_hint}</p>
          <p className="muted small">Saved {stamp(key.updated_at)}{key.last_used_at ? `. Last used ${stamp(key.last_used_at)}.` : "."}</p>
          <div className="row">
            <button onClick={() => setEditing(true)}>Change key</button>
            <button onClick={async () => {
              if (!confirm("Remove your API key? The assistant stops until you add one again.")) return;
              setError("");
              try { await api2.removeModelKey(); announce("Removed your API key."); await refresh(); }
              catch (e) { setError(e instanceof ApiError ? e.message : "Could not remove the key."); }
            }}>Remove key</button>
          </div>
        </>
      ) : (
        <>
          <p className="muted">{me.needs_model_key ? "No key yet. The assistant needs one to work." : "Using the key this server was set up with. Add your own to use your account instead."}</p>
          <button className="primary" onClick={() => setEditing(true)}>Add your key</button>
        </>
      )}
      {error && <p role="alert" className="error">{error}</p>}
    </section>
  );
}
