import { useEffect, useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Loader2, X } from 'lucide-react'
import { Button } from './components/Button'
import { api, type Session } from './api'

type Catalog = {
  default: { model: string };
  current: { provider: string; model: string; validated_at: number | null; retain_for_new_sessions: boolean };
  providers: { id: string; label: string; models: string[]; key_url: string; validation: string; model_details: Record<string,{ label: string; description: string; validation: string }> }[];
}

export function ModelSettings({ session, onApplied, onBusy, onClose, restoreFocus }: {
  session: Session; onApplied: (session: Session) => void; onBusy: (busy: boolean) => void; onClose: () => void; restoreFocus: () => void;
}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [retain, setRetain] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [resetConfirmed, setResetConfirmed] = useState(false)
  const keyInput = useRef<HTMLInputElement>(null)
  function loadCatalog() {
    let active = true
    setError('')
    api<Catalog>('/settings').then(data => {
      if (!active) return
      setCatalog(data); setProvider(data.current.provider); setModel(data.current.model); setRetain(data.current.retain_for_new_sessions)
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }
  useEffect(loadCatalog, [])
  const selected = catalog?.providers.find(p => p.id === provider)
  const modelDetail = selected?.model_details[model]
  async function apply() {
    if (busy || !catalog || (session.messages.length > 0 && !resetConfirmed)) return
    setBusy(true); onBusy(true); setError(''); setSuccess(false)
    // The password exists only in the input and this HTTPS/same-origin request.
    const key = keyInput.current?.value || undefined
    if (keyInput.current) keyInput.current.value = ''
    try {
      const result = await api<{ session: Session; settings: Catalog }>('/settings', {
        request_id: crypto.randomUUID(), version: session.version, provider, model,
        credential_source: provider === 'scripted' ? 'demo' : 'byok', retain_for_new_sessions: provider !== 'scripted' && retain, ...(provider !== 'scripted' ? { api_key: key } : {}),
      }, session.csrf)
      setCatalog(result.settings); onApplied(result.session); setSuccess(true)
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false); onBusy(false) }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose() }}><Dialog.Portal>
    <Dialog.Overlay className="dialog-overlay"/>
    <Dialog.Content onCloseAutoFocus={event => { event.preventDefault(); restoreFocus() }} className="demo-dialog model-settings" onEscapeKeyDown={e => { if (busy) e.preventDefault() }} onPointerDownOutside={e => { if (busy) e.preventDefault() }}>
      <span className="eyebrow">MODEL CONNECTION</span><Dialog.Title>Model settings</Dialog.Title>
      <Dialog.Description>Choose your AI model and bring your own API key, or explore the Offline Demo without a key.</Dialog.Description>
      {catalog ? <form onSubmit={e => { e.preventDefault(); void apply() }}>
        <p className="settings-current">Current: <strong>{catalog.current.model}</strong><br/><span>{catalog.current.provider==='scripted'?'Offline · no connection needed':catalog.current.validated_at ? 'Connection validated for this key and model' : 'Configured · connection not checked this session'}<br/>Default: {catalog.default.model}</span></p>
        <label htmlFor="model-provider">Provider</label><select id="model-provider" value={provider} disabled={busy} onChange={e => {
          const p = catalog.providers.find(p => p.id === e.target.value)!
          setRetain(false); setProvider(p.id); setModel(p.models[0]); setSuccess(false); setError('')
          if (keyInput.current) keyInput.current.value = ''
        }}>{catalog.providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select>
        <label htmlFor="model-name">Model</label><select id="model-name" value={model} disabled={busy} onChange={e => { setModel(e.target.value); setSuccess(false) }}>{selected?.models.map(m => <option key={m} value={m}>{selected.model_details[m]?.label || m} · {selected.model_details[m]?.description}</option>)}</select>
        <p className="micro muted">{modelDetail?.validation}. Account access is checked when you validate this selection.</p>
        {provider !== 'scripted' && <>
          <label htmlFor="provider-key">API key</label><input id="provider-key" type="password" autoComplete="off" spellCheck={false} maxLength={512} ref={keyInput} disabled={busy} required/><p className="micro muted">Re-enter to validate. Stored encrypted on the backend for this session, never in browser storage. Use a local connection or HTTPS. Without retention, New session removes the key and makes no API call until you provide one again.</p><label className="settings-confirm"><input type="checkbox" checked={retain} disabled={busy} onChange={e => { setRetain(e.target.checked); setSuccess(false) }}/>Keep this key for new sessions in this browser</label><p className="micro muted">Optional. The key stays encrypted on the backend, linked to this browser’s session cookie, for up to 24 hours of inactivity. New sessions still clear identity and conversation. Uncheck and apply to stop retaining it; no key is stored in browser storage.</p>
          <a href={selected?.key_url} target="_blank" rel="noreferrer">Get an API key from {selected?.label} ↗</a>
        </>}
        <p className="settings-reset">Applying clears the conversation and summary, and requires fresh identity verification. Connection validation uses one small model call; provider charges may apply.</p>
        {session.messages.length > 0 && <label className="settings-confirm"><input type="checkbox" checked={resetConfirmed} disabled={busy} onChange={e=>setResetConfirmed(e.target.checked)}/>Clear this conversation and summary when applying</label>}
        {error && <p role="alert" className="lab-error">{error}</p>}{success && <p role="status" className="status-good">Connection validated. Ready for a new conversation.</p>}
        <Button type="submit" disabled={busy || (session.messages.length > 0 && !resetConfirmed)}>{busy && <Loader2 size={15} className="spin"/>}{busy ? 'Validating…' : provider === 'scripted' ? 'Apply offline mode' : 'Validate & apply'}</Button>
      </form> : error ? <div><p role="alert">{error}</p><Button onClick={loadCatalog}>Retry loading settings</Button></div> : <p role="status">Loading model settings…</p>}
      <Dialog.Close className="dialog-close" aria-label="Close model settings" disabled={busy}><X size={20}/></Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>
}
