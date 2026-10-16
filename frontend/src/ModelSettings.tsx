import { useEffect, useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Loader2, X } from 'lucide-react'
import { Button } from './components/Button'
import { api, type Session } from './api'

type Catalog = {
  current: { provider: string; model: string; credential_source: 'demo' | 'byok'; validated_at: number | null };
  providers: { id: string; label: string; models: string[]; demo_configured: boolean; key_url: string; validation: string }[];
}

export function ModelSettings({ session, onApplied, onBusy, onClose, restoreFocus }: {
  session: Session; onApplied: (session: Session) => void; onBusy: (busy: boolean) => void; onClose: () => void; restoreFocus: () => void;
}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [source, setSource] = useState<'demo' | 'byok'>('demo')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const keyInput = useRef<HTMLInputElement>(null)
  useEffect(() => {
    let active = true
    api<Catalog>('/settings').then(data => {
      if (!active) return
      setCatalog(data); setProvider(data.current.provider); setModel(data.current.model); setSource(data.current.credential_source)
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [])
  const selected = catalog?.providers.find(p => p.id === provider)
  async function apply() {
    if (busy || !catalog) return
    setBusy(true); onBusy(true); setError(''); setSuccess(false)
    // The password exists only in the input and this HTTPS/same-origin request.
    const key = keyInput.current?.value || undefined
    if (keyInput.current) keyInput.current.value = ''
    try {
      const result = await api<{ session: Session; settings: Catalog }>('/settings', {
        request_id: crypto.randomUUID(), version: session.version, provider, model,
        credential_source: source, ...(source === 'byok' ? { api_key: key } : {}),
      }, session.csrf)
      setCatalog(result.settings); onApplied(result.session); setSuccess(true)
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false); onBusy(false) }
  }
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose() }}><Dialog.Portal>
    <Dialog.Overlay className="dialog-overlay"/>
    <Dialog.Content onCloseAutoFocus={event => { event.preventDefault(); restoreFocus() }} className="demo-dialog model-settings" onEscapeKeyDown={e => { if (busy) e.preventDefault() }} onPointerDownOutside={e => { if (busy) e.preventDefault() }}>
      <span className="eyebrow">MODEL CONNECTION</span><Dialog.Title>Model settings</Dialog.Title>
      <Dialog.Description>Choose how ClaimFlow interprets messages. The SOP controls identity, claim access, and actions.</Dialog.Description>
      {catalog ? <form onSubmit={e => { e.preventDefault(); void apply() }}>
        <p className="settings-current">Current: <strong>{catalog.current.model}</strong><br/><span>{catalog.current.validated_at ? 'Connection validated' : 'Configured · connection not checked this session'} · {catalog.current.credential_source === 'byok' ? 'Your key' : 'Demo configuration'}</span></p>
        <label htmlFor="model-provider">Provider</label><select id="model-provider" value={provider} disabled={busy} onChange={e => {
          const p = catalog.providers.find(p => p.id === e.target.value)!
          setProvider(p.id); setModel(p.models[0]); setSource('demo'); setSuccess(false); setError('')
          if (keyInput.current) keyInput.current.value = ''
        }}>{catalog.providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select>
        <label htmlFor="model-name">Model</label><select id="model-name" value={model} disabled={busy} onChange={e => { setModel(e.target.value); setSuccess(false) }}>{selected?.models.map(m => <option key={m} value={m}>{m}</option>)}</select>
        <p className="micro muted">{selected?.validation}</p>
        {provider !== 'scripted' && <>
          <label htmlFor="model-credentials">Credentials</label><select id="model-credentials" value={source} disabled={busy} onChange={e => { setSource(e.target.value as typeof source); setSuccess(false); if (keyInput.current) keyInput.current.value = '' }}>
            <option value="demo">Demo-configured key{selected?.demo_configured ? ' · available' : ' · unavailable'}</option><option value="byok">Bring Your Own Key</option>
          </select>
          {source === 'byok' ? <><label htmlFor="provider-key">API key</label><input id="provider-key" type="password" autoComplete="off" spellCheck={false} maxLength={512} ref={keyInput} disabled={busy} required/><p className="micro muted">Re-enter to validate. Stored encrypted on the backend for this session, never in browser storage. New session removes it. Use a local connection or HTTPS.</p></> : <p className="micro muted">{selected?.demo_configured ? 'Uses a backend environment key. The browser never receives it.' : 'No demo key is configured. Choose Bring Your Own Key or another provider.'}</p>}
          <a href={selected?.key_url} target="_blank" rel="noreferrer">Get an API key from {selected?.label} ↗</a>
        </>}
        <p className="settings-reset">Applying clears the conversation and summary, and requires fresh identity verification. Connection validation uses one small model call; provider charges may apply.</p>
        {error && <p role="alert" className="lab-error">{error}</p>}{success && <p role="status" className="status-good">Connection validated. Ready for a new conversation.</p>}
        <Button type="submit" disabled={busy || (provider !== 'scripted' && source === 'demo' && !selected?.demo_configured)}>{busy && <Loader2 size={15} className="spin"/>}{busy ? 'Validating…' : provider === 'scripted' ? 'Apply offline mode' : 'Validate & apply'}</Button>
      </form> : <p role="status">{error || 'Loading model settings…'}</p>}
      <Dialog.Close className="dialog-close" aria-label="Close model settings" disabled={busy}><X size={20}/></Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>
}
