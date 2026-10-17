import { useCallback, useEffect, useRef, useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import * as Dialog from '@radix-ui/react-dialog'
import { ArrowDown, ArrowRight, ArrowUp, Check, CheckCheck, CheckCircle2, ChevronDown, ChevronRight, Circle, CircleAlert, Clock3, ClipboardList, FlaskConical, Info, Loader2, LockKeyhole, Mail, MessageSquare, PanelRightClose, PanelRightOpen, Plus, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { ModelSettings } from './ModelSettings'
import { IdentityVerification } from './IdentityVerification'
import { Button } from './components/Button'
import { api, ApiError, type Session, type Event, type Scenario, type Evaluation } from './api'

const PHASES = ['VERIFY_ID', 'RESOLVE_INTENT', 'PROCESS_CASE', 'POST_PROCESS']
const PHASE_NAMES = ['Verify identity', 'Resolve intent', 'Process case', 'Follow-up']
const INTENTS: Record<string,string> = { none: 'Listening for your question', denial_question: 'Understand a denial', status_inquiry: 'Check claim status', document_submission: 'Documents & submission', payment_question: 'Understand payment', next_steps: 'Find next steps', general_claim_question: 'Claim assistance' }
const title = (s: string) => s.toLowerCase().replaceAll('_', ' ').replace(/^./, x => x.toUpperCase())
let bootstrap: Promise<Session> | undefined
function initialize() {
  if (!bootstrap) bootstrap = api<Session>('/session').catch(error => {
    if (error instanceof ApiError && error.status === 401) return api<Session>('/session', {})
    throw error
  }).finally(() => { bootstrap = undefined })
  return bootstrap
}

function Brand({ small = false }: { small?: boolean }) {
  return <span className={'brand ' + (small ? 'brand-small' : '')}><span className="brand-mark"><ShieldCheck size={small ? 16 : 22} strokeWidth={1.7} /></span>{!small && <span>Claim<span className="brand-light">Flow</span></span>}</span>
}

function evidenceLabel(reference: string) {
  if (reference.startsWith('claims.json#')) return `Claim ${reference.split('#')[1]} record`
  if (reference==='claims.json') return 'Authorized claim records'
  if (reference.startsWith('claim_schema.json')) return 'Payment field definitions'
  if (reference.startsWith('required_document_guideline.json')) {
    const document = reference.split('/').at(-1)
    if (document && !document.includes('#') && document!=='default') return title(document.replace(/^original /, '')) + ' guidance'
    return reference.includes('followup') ? 'Claim follow-up guidance' : 'Document guidance'
  }
  return 'Provided guidance'
}

function Trace({ events, compact = false }: { events: Event[]; compact?: boolean }) {
  const visible = compact ? events.slice(-7).reverse() : events
  return <div className="trace-list">{visible.map(e => <details key={e.sequence} className="trace-entry">
    <summary><span className={'trace-dot ' + (e.code.includes('DENIED') || e.code.includes('BLOCKED') || e.code.includes('EXPIRED') ? 'attention' : '')} /><span>{title(e.code)}</span><ChevronDown size={13}/></summary>
    <div className="trace-detail"><p>{e.detail}</p><span className="mono trace-meta">{e.phase} · #{String(e.sequence).padStart(2,'0')} · <time dateTime={new Date(e.at*1000).toISOString()}>{new Date(e.at*1000).toLocaleString()}</time></span>{e.references.length > 0 && <ul>{e.references.map(r => <li key={r} className="mono">{r}</li>)}</ul>}</div>
  </details>)}</div>
}

function Inspector({ session }: { session: Session }) {
  const evidence = session.messages.filter(m=>m.role==='assistant').at(-1)?.references || []
  const labels: Record<string,string> = { CASE_RESOLVED:'Authorized claim selected', CLAIMS_READ:'Authorized claim accessed', GROUNDED_RESPONSE:'Response generated from claim records', SUMMARY_OFFERED:'Summary preview prepared', EMAIL_SIMULATED:'Email simulation recorded', EMAIL_SKIPPED:'Email simulation skipped', CONSENT_EXPIRED:'Summary consent expired', MODEL_CHANGED:'Model changed; verification reset' }
  const latest = session.events.filter(e=>labels[e.code]).filter((e,n,events)=>!events.slice(n+1).some(next=>next.code===e.code)).slice(-4)

  return <div className="inspector-content">
    <div className="inspector-intro"><span className="eyebrow">WORKFLOW INSPECTOR</span><h2>Every decision, explained.</h2><p>The model interprets. The SOP controller decides.</p></div>
    <section className="inspector-section">
      <div className="section-label"><ShieldCheck size={16}/><h3>Identity & access</h3><span className={session.verified ? 'status-good' : 'muted'}>{session.verified ? 'Verified' : 'Required'}</span></div>
      <div className="verification-meter">{[0,1,2].map(n => <span key={n} className={n < session.verification.count ? 'filled' : ''}/>)}</div>
      <p className="small">{session.verified ? <><strong>3 of 3</strong> distinct identity fields matched</> : <>Three matching fields required. Partial results stay private.</>}</p>
      <p className="micro muted">{session.verification.representative ? 'Representative identity and a scoped grant are also required.' : 'Policy numbers help locate records. They do not count toward verification.'}</p>
      {session.verified && <div className="access-note"><CheckCheck size={14}/> Read access scoped to this policyholder</div>}
    </section>
    <section className="inspector-section context-section">
      <div className="section-label"><ClipboardList size={16}/><h3>Conversation context</h3></div>
      <dl><div><dt>Intent</dt><dd>{INTENTS[session.intent] || 'Claim assistance'}</dd></div><div><dt>Claim</dt><dd>{session.case_id ? <span><span className="mono">{session.case_id}</span>{session.case_status && <> · {title(session.case_status)}</>}</span> : <span className="context-lock"><LockKeyhole size={12}/>{session.verified ? 'Awaiting selection' : 'Locked until verified'}</span>}</dd></div><div><dt>Support</dt><dd>{session.human_offered ? 'Human review recommended' : 'Guided assistance'}</dd></div></dl>
      {session.unresolved.length > 0 && <p className="next-step"><span className="eyebrow">NEXT STEP</span>{session.unresolved[0]}</p>}
    </section>
    <section className="inspector-section decisions">
      <div className="section-label"><Circle size={14}/><h3>Latest decisions</h3></div>
      <ul className="decision-summary">{session.verified&&<li><Check size={14}/>Identity verified</li>}{evidence.some(r=>r.startsWith('required_document_guideline.json'))&&<li><Check size={14}/>Document guidance applied</li>}{latest.map(e=><li key={e.sequence}><Check size={14}/>{labels[e.code]}</li>)}</ul>
      {!latest.length&&!session.verified&&<p className="micro muted">Decisions will appear as the conversation progresses.</p>}
      {evidence.length>0&&<details className="inspector-evidence"><summary>Evidence used for this response · {evidence.length}</summary><p className="micro muted">Synthetic claim data and supplied guidance.</p><table><thead><tr><th>Source</th><th>Internal reference</th></tr></thead><tbody>{evidence.map(r=><tr key={r}><td>{evidenceLabel(r)}</td><td className="mono">{r}</td></tr>)}</tbody></table></details>}
      <details className="full-trace"><summary>Full decision history ({session.events.length} events)</summary><p className="micro muted">Complete policy events, timestamps and original references. No private model reasoning.</p><Trace events={session.events}/></details>
    </section>
    <div className="inspector-foot"><LockKeyhole size={13}/><span>Credentials are hidden from the inspector.<br/>Fixture version <span className="mono">{session.fixture_version}</span></span></div>
  </div>
}

type Pending = { path: string; body: Record<string,unknown>; text?: string; displayText?: string }
type DemoScenario = { id: string; name: string; opening: string; description: string }

function transcriptScope(session: Session) {
  const reset = session.events.filter(e => ['AUTH_EXPIRED', 'IDENTITY_RECHECK', 'REPRESENTATIVE_BLOCKED', 'MODEL_CHANGED'].includes(e.code)).at(-1)?.sequence
  return JSON.stringify([session.csrf, session.model, reset])
}

function pendingLabel(text: string) {
  // Only fixed, non-identity questions are safe before server-side redaction.
  const safe = /^(?:can i still appeal after the deadline|why was my claim denied|how much (?:money will i get|will i receive)|what (?:is the (?:payment|status)|documents (?:are needed|do i need))|how (?:do i submit documents|long will it take))\??$/i
  return safe.test(text) ? text : 'Message pending · personal details hidden'
}

function lockedSession(s: Session): Session {
  return { ...s, verified:false, phase:'VERIFY_ID', case_id:null, case_status:null, choices:[], summary:null, auth_expires_at:null,
    verification:{ ...s.verification, count:0, fields:[] }, intent:'none', unresolved:['Complete identity verification'],
    messages:s.messages.filter(m=>!m.protected), events:s.events.filter(e=>!e.references.length) }
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [initializing, setInitializing] = useState(true)
  const [tab, setTab] = useState('playground')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  // Page memory only; never merge originals into the server session or Inspector.
  const [submitted, setSubmitted] = useState<{ scope: string; messages: Record<string,string> } | null>(null)
  const [inspector, setInspector] = useState(true)
  const [mobileInspector, setMobileInspector] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [demoOpen, setDemoOpen] = useState(false)
  const [demo, setDemo] = useState<{ opening: string; scenarios: DemoScenario[] } | null>(null)
  const [demoChoice, setDemoChoice] = useState('standard')
  const [demoError, setDemoError] = useState('')
  const [resetOpen, setResetOpen] = useState(false)
  const [nearBottom, setNearBottom] = useState(true)
  const [newMessage, setNewMessage] = useState(false)
  const [remaining, setRemaining] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const sendingRef = useRef(false)
  const sessionEpoch = useRef(0)
  const expiredSummary = useRef<string | null>(null)
  const mobileInspectorButton = useRef<HTMLButtonElement>(null)
  const settingsButton = useRef<HTMLButtonElement>(null)
  const resetButton = useRef<HTMLButtonElement>(null)
  const demoButton = useRef<HTMLButtonElement>(null)
  const demoInserted = useRef(false)
  const scope = session ? transcriptScope(session) : ''
  const submittedMessages = submitted?.scope === scope ? submitted.messages : {}

  useEffect(() => {
    setSubmitted(current => current?.scope === scope ? current : null)
  }, [scope])

  useEffect(() => {
    let active = true
    const epoch = sessionEpoch.current
    initialize().then(s => { if (active && epoch === sessionEpoch.current) setSession(s) }).catch(e => { if (active && epoch === sessionEpoch.current) setError(e.message) }).finally(() => { if (active) setInitializing(false) })
    return () => { active = false }
  }, [])

  const refresh = useCallback(async () => {
    const epoch = sessionEpoch.current
    const latest = await api<Session>('/session')
    if (epoch === sessionEpoch.current) setSession(latest)
    return latest
  }, [])

  useEffect(() => {
    if (!session) return
    const skew = session.server_time - Date.now()/1000
    const tick = () => {
      const now = Date.now()/1000 + skew
      setRemaining(Math.max(0, Math.ceil((session.summary?.expires_at || 0)-now)))
      if (session.auth_expires_at && now >= session.auth_expires_at) {
        // Hide protected content at the deadline even when the server cannot be reached.
        setSubmitted(null)
        setSession(current => current === session ? lockedSession(current) : current)
        void refresh().catch(() => {})
      } else if (session.summary && ['offered','failed','timeout'].includes(session.summary.status) && now >= session.summary.expires_at && expiredSummary.current !== session.summary.id) {
        expiredSummary.current = session.summary.id
        void refresh().catch(() => {})
      }
    }
    tick()
    const interval = window.setInterval(tick, 1000)
    return () => window.clearInterval(interval)
  }, [session, refresh])

  useEffect(() => {
    if (!session?.messages.length && !busy) return
    if (nearBottom) { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'instant' }); setNewMessage(false) }
    else setNewMessage(true)
  // Keep the scroll position when the reader has moved up.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.messages.length, busy, session?.summary?.id, remaining > 0])

  async function execute(operation: Pending) {
    if (!session || sendingRef.current) return false
    ++sessionEpoch.current
    sendingRef.current = true; setBusy(true); setError(''); setPending(operation)
    if (operation.text) setText('')
    try {
      const next = await api<Session>(operation.path, operation.body, session.csrf)
      const original = operation.text ?? operation.displayText
      const id = operation.body.request_id
      if (transcriptScope(next) !== scope) setSubmitted(null)
      else if (original && typeof id === 'string' && next.messages.some(m => m.role === 'user' && m.id === id)) {
        setSubmitted(current => ({ scope, messages: { ...(current?.scope === scope ? current.messages : {}), [id]: original } }))
      }
      setSession(next); setPending(null)
      if (operation.text) setText('')
      inputRef.current?.focus()
      return true
    } catch (e) {
      if (operation.text) setText(operation.text)
      setError(e instanceof Error ? e.message : 'Something went wrong. Please retry.')
      if (e instanceof ApiError && e.status === 401) {
        setSubmitted(null)
        setSession(current => current && lockedSession(current)); setPending(null)
      }
      if (e instanceof ApiError && [403, 409].includes(e.status)) {
        setSubmitted(null)
        setSession(current => current && lockedSession(current))
        try {
          const latest = await refresh()
          if (latest.csrf !== session.csrf) {
            setPending(null)
            setError('The session was replaced in another tab. The current session is now loaded. Review your draft before sending again.')
          } else {
            setPending({ ...operation, body: { ...operation.body, version: latest.version } })
            setError('The current session has been synchronized. Review the conversation, then retry your action.')
          }
        } catch { setPending(null) /* Keep explicit recovery available. */ }
      }
      return false
    } finally { setBusy(false); sendingRef.current = false }
  }

  function send() {
    if (!session || session.assistance_paused || !text.trim()) return
    if (pending || sendingRef.current) return
    void execute({ path:'/turn',body:{ text:text.trim(),version:session.version,request_id:crypto.randomUUID() },text:text.trim() })
  }
  function action(action: string) {
    if (!session) return
    if (pending || sendingRef.current) return
    void execute({ path:'/action',body:{ action,version:session.version,summary_id:action==='preview'?null:session.summary?.id,request_id:crypto.randomUUID() } })
  }
  async function reset() {
    if (sendingRef.current) return
    sendingRef.current = true
    ++sessionEpoch.current
    setSubmitted(null)
    setBusy(true); setError('')
    try { setSession(await api<Session>('/session',{})); setText(''); setPending(null); setNearBottom(true); setResetOpen(false) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false); sendingRef.current = false }
  }
  async function showDemo() {
    demoInserted.current = false
    setDemoError('')
    setDemoOpen(true)
    if (!demo) try { setDemo(await api('/demo-starter')) } catch(e) { setDemoError((e as Error).message) }
  }
  async function recover() {
    if (sendingRef.current) return
    sendingRef.current = true; setBusy(true)
    ++sessionEpoch.current
    try { setSession(await (session ? refresh() : initialize())); setPending(null); setError('') }
    catch (e) {
      setError((e as Error).message)
      if (e instanceof ApiError && e.status === 401) { setSubmitted(null); setSession(current => current && lockedSession(current)) }
    } finally { sendingRef.current = false; setBusy(false) }
  }
  const summary = pending?.text || session?.assistance_paused ? null : session?.summary
  const activePhase = PHASES.indexOf(session?.phase || 'VERIFY_ID')
  const selectedDemo = demo?.scenarios.find(s => s.id === demoChoice)

  return <Tabs.Root value={tab} onValueChange={setTab} className="app-shell">
    <header className="app-header"><a href="/" aria-label="ClaimFlow home"><Brand/></a><span className="header-divider"/><span className="workspace-label">Claims support workspace</span>
      <Tabs.List className="main-tabs" aria-label="Workspace"><Tabs.Trigger value="playground"><MessageSquare size={16}/><span>Agent Playground</span></Tabs.Trigger><Tabs.Trigger value="lab"><FlaskConical size={16}/><span>Evaluation Lab</span></Tabs.Trigger></Tabs.List>
      <Button ref={settingsButton} variant="ghost" size="sm" disabled={!session||busy||!!pending} onClick={()=>setSettingsOpen(true)}>Model settings</Button><span className="demo-label"><span/>Synthetic data</span>
    </header>
    <Tabs.Content value="playground" className="workspace" forceMount hidden={tab!=='playground'}>
      <div className="page-heading"><div><div className="eyebrow">AGENT PLAYGROUND</div><h1>Claims support</h1><p>A clear answer. A considered next step.</p></div><div className="heading-actions"><span className="model-label"><span className={'connection-dot '+(session?.model==='scripted'?'offline':'')}/>{session?.model === 'scripted' ? 'Offline · Scripted' : session?.model ? 'Live · ' + session.model : 'Connecting'}</span><Button ref={resetButton} variant="outline" size="sm" disabled={busy||initializing} onClick={()=>session?.messages.length||text.trim()?setResetOpen(true):void reset()}><Plus size={15}/>New session</Button></div></div>
      <ol className="phase-strip" aria-label="Workflow progress">{PHASE_NAMES.map((name,n) => <li key={name} aria-current={n===activePhase?'step':undefined} className={n===activePhase?'current':n<activePhase?'complete':''}><span className="phase-number">{n<activePhase?<Check size={14}/>:String(n+1).padStart(2,'0')}</span><span>{name}</span>{n<3&&<ChevronRight className="phase-chevron" size={16}/>}</li>)}</ol>
      <main className={'playground-layout '+(!inspector?'inspector-hidden':'')}>
        <section className="chat-panel" aria-label="Claim support conversation">
          <div className="panel-header"><span className="chat-agent-icon"><ShieldCheck size={18}/></span><div><h2>ClaimFlow assistant</h2><p>Guided by your insurer’s demo SOP</p></div><span className="private-note"><LockKeyhole size={12}/>Private session</span><Button variant="ghost" size="icon" className="desktop-inspector-button" aria-label={inspector?'Hide workflow inspector':'Show workflow inspector'} aria-pressed={inspector} onClick={()=>setInspector(!inspector)}>{inspector?<PanelRightClose size={18}/>:<PanelRightOpen size={18}/>}</Button><Button variant="ghost" size="icon" className="mobile-inspector-button" ref={mobileInspectorButton} aria-label="Open workflow inspector" onClick={()=>setMobileInspector(true)}><PanelRightOpen size={18}/></Button></div>
          <div className="conversation" ref={scrollRef} onScroll={()=>{ const el=scrollRef.current!; const near=el.scrollHeight-el.scrollTop-el.clientHeight<90; setNearBottom(near); if(near)setNewMessage(false) }}>
            <div className="conversation-date">YOUR SUPPORT SESSION</div>
            {session?.messages.length===0&&<div className="starter-area"><div className="starter-label">EXPLORING THE DEMO?</div><button ref={demoButton} className="scenario-starter" onClick={showDemo}><span className="starter-icon"><ClipboardList size={18}/></span><span><strong>Try a guided scenario</strong><small>Standard claim, frustrated caller, or ambiguous claim</small></span><ArrowRight size={17}/></button><p className="micro muted"><Info size={12}/> Synthetic records only. Please don’t enter real personal information.</p></div>}
            <div className="assistant-message welcome"><Brand small/><div className="message-body"><span className="message-author">ClaimFlow</span><p>Hello, I’m here to help with your insurance claim.</p><p>We’ll first verify your identity, then look at your claim together and work through the next steps. You can ask questions along the way.</p><p className="muted">To begin, tell me what brings you here and share any three approved identity details: full name, date of birth, phone, email, or SSN / approved national-ID last four.</p></div></div>

            {session?.messages.map(m => <div className={m.role==='user'?'user-message':'assistant-message'} key={m.id}>{m.role==='assistant'&&<Brand small/>}<div className="message-body"><span className="message-author">{m.role==='assistant'?'ClaimFlow':'You'}</span><div className="message-text">{m.role==='user' ? submittedMessages[m.id] ?? m.text : m.text}</div>{m.references.length>0&&<details className="message-grounding"><summary><ShieldCheck size={12}/>Sources · {m.references.length} {m.references.length===1?'source':'sources'}<ChevronDown size={12}/></summary><p className="micro muted">Supporting evidence · synthetic records and supplied guidance</p><ul>{m.references.map(r=><li key={r}>{evidenceLabel(r)}</li>)}</ul></details>}</div></div>)}
            {pending?.text&&!session?.messages.some(m=>m.id===pending.body.request_id)&&<div className="user-message pending-message"><div className="message-body"><div className="message-text">{pendingLabel(pending.text)}</div><span className={'delivery-status '+(error?'status-bad':'')} role="status">{error?<CircleAlert size={14}/>:<Clock3 size={14}/>} {error?'Not sent · Retry below':'Sending…'}</span></div></div>}
            {!session?.assistance_paused && session?.choices.length ? <div className="case-choices">{session.choices.map(c=><Button variant="outline" size="sm" key={c.case_id} disabled={busy} onClick={()=>void execute({path:'/turn',body:{text:`Please discuss ${c.case_id}. I want its status.`,version:session.version,request_id:crypto.randomUUID()},text:`Please discuss ${c.case_id}. I want its status.`})}><span className="mono">{c.case_id}</span> · {c.created_at.slice(0,4)}<ArrowRight size={13}/></Button>)}</div>:null}
            {session?.assistance_paused && <section className="human-assistance" aria-label="Human assistance recommended">
              <h3>Human assistance recommended</h3><p>Chat is paused. Select “Return to chatbot” to resume this conversation. For human help, contact your insurer’s official member support directly. This demo cannot transfer you, open a ticket, or place you in a queue.</p>
              <Button variant="outline" size="sm" disabled={busy || !!pending} onClick={()=>session && void execute({path:'/turn',body:{text:'Return to chatbot',version:session.version,request_id:crypto.randomUUID()},text:'Return to chatbot'})}>Return to chatbot</Button>
            </section>}
            {session?.verification.representative && <section className="representative-state" aria-label="Representative Mode">
              <h3>Representative Mode</h3><p>Representative identity and policyholder authorization remain required. Providing self-service details here does not change your role.</p>
              <Button variant="outline" size="sm" disabled={busy || !!pending} onClick={()=>setResetOpen(true)}>Start fresh self-service session</Button>
            </section>}
            {session?.phase === 'VERIFY_ID' && !session.assistance_paused && <IdentityVerification key={session.csrf} disabled={busy || !!pending} onSubmit={(fields,displayText)=>execute({path:'/verify',body:{fields,version:session.version,request_id:crypto.randomUUID()},displayText})}/>}
            {summary&&<div className="summary-preview"><div className="summary-header"><Mail size={17}/><h3>Claim discussion summary</h3><span>Simulation</span></div><div className="summary-content">{summary.cases?.length ? <>{summary.cases.map(c=><section className="summary-case" key={c.case_id} aria-label={'Summary for '+c.case_id}><div className="summary-claim"><span className="summary-label">Claim</span><h4>{c.case_id} · {c.case_type}</h4><p className="summary-status">{c.status==='Denied'?<CircleAlert size={17} className="status-bad"/>:<CheckCircle2 size={17}/>} {c.status}</p></div><dl>{c.denial_reason&&<div><dt>Reason for denial</dt><dd>{c.denial_reason}</dd></div>}<div><dt>Payment</dt><dd className="summary-payment">{c.payment}</dd><dd className="summary-note">Recorded finalized insurer payment. Allowed maximum: {c.allowed_maximum}, not a promised payout.</dd></div>{c.appeal_deadline&&<div><dt>Appeal deadline</dt><dd className={c.deadline_passed?'deadline-passed':''}>{c.appeal_deadline}{c.deadline_passed?' — Passed':''}</dd></div>}<div><dt>Next steps</dt><dd>{c.next_steps}</dd></div></dl>{c.unresolved&&<details className="summary-unresolved"><summary>Still unresolved</summary><p>{c.unresolved}</p></details>}</section>)}<p className="summary-boundary">This is a synthetic summary. No appeal, payment, document submission, or email delivery has occurred.</p></> : summary.text}</div><div className="summary-recipient"><span>To your on-file email</span><strong>{summary.recipient}</strong></div>
              {['offered','failed','timeout'].includes(summary.status)&&remaining>0?<><p className="micro muted consent-note">Choose explicitly. This offer expires in {Math.floor(remaining/60)}:{String(remaining%60).padStart(2,'0')}.</p><div className="summary-actions"><Button disabled={busy} onClick={()=>action('send')}><Mail size={15}/>{summary.status==='offered'?'Send simulated email':'Retry simulation'}</Button><Button variant="outline" disabled={busy} onClick={()=>action('skip')}>Skip</Button></div></>:<div className="summary-result"><CheckCircle2 size={16}/>{summary.status==='simulated_sent'?'Simulation recorded. No email was delivered.':summary.status==='skipped'?'Skipped. No email was sent.':'Offer expired. No email action was taken.'}{summary.status==='simulated_sent'&&<span className="micro mono">Receipt {summary.receipt}</span>}{summary.status==='expired'&&<Button variant="outline" size="sm" disabled={busy} onClick={()=>action('preview')}>Review a fresh summary</Button>}</div>}
            </div>}
            {busy&&<div className="assistant-message thinking" role="status"><Brand small/><div className="message-body"><span className="message-author">ClaimFlow</span><span className="processing-label"><Loader2 size={18} className="spin"/>Checking your claim…</span></div></div>}
          </div>
          {newMessage&&!nearBottom&&<button className="jump-bottom" onClick={()=>{ scrollRef.current?.scrollTo({top:scrollRef.current.scrollHeight,behavior:'smooth'});setNearBottom(true);setNewMessage(false) }}><ArrowDown size={13}/>New message</button>}
          <div className="composer-area">
            {Object.keys(submittedMessages).length>0&&<div className="transcript-privacy"><span>Your submitted text is visible only in this page.</span><Button variant="ghost" size="sm" disabled={busy} onClick={()=>setSubmitted(null)}>Hide submitted details</Button></div>}
            {error&&<div className="error-banner" role="alert"><Info size={15}/><span>{error}</span>{pending?<Button variant="ghost" size="sm" disabled={busy} onClick={()=>void execute(pending)}>Retry</Button>:<Button variant="ghost" size="sm" disabled={busy} onClick={()=>void recover()}>Recover</Button>}<button aria-label="Dismiss error" onClick={()=>{setError('');setPending(null)}}><X size={15}/></button></div>}
            {session?.verified&&!session.assistance_paused&&session.case_id&&session.phase!=='POST_PROCESS'&&<div className="wrap-up"><span>Have what you need?</span><button disabled={busy} onClick={()=>action('preview')}>Review summary <ArrowRight size={13}/></button></div>}
            {session && session.model_connection?.ready === false && <p className="connection-notice" role="status">Missing key — no API call. Open <button onClick={()=>setSettingsOpen(true)}>Model settings</button> to enter a key or choose Offline Demo.</p>}
            <form className="composer" onSubmit={e=>{e.preventDefault();send()}}><label className="sr-only" htmlFor="message">Message ClaimFlow</label><textarea id="message" ref={inputRef} value={text} maxLength={4000} rows={2} disabled={!session||busy||session.assistance_paused} placeholder={session?.assistance_paused?'Chat is paused · choose Return to chatbot to continue':session?.messages.length?'Ask a follow-up question…':'Tell me about your claim…'} onChange={e=>{setText(e.target.value);if(pending){setPending(null);setError('')}}} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send()}}}/><Button type="submit" size="icon" disabled={!session||busy||session.assistance_paused||!!pending||!text.trim()} aria-label="Send message"><ArrowUp size={19}/></Button></form>
            <div className="composer-footer"><span><LockKeyhole size={11}/>Saved history hides identity details. Privacy labels are not verification results.</span><span>Enter to send · Shift + Enter for a new line</span></div>
          </div>
        </section>
        {inspector&&session&&<aside className="inspector-panel" aria-label="Workflow inspector"><Inspector session={session}/></aside>}
      </main>
    </Tabs.Content>
    <Tabs.Content value="lab" className="workspace lab-workspace" forceMount hidden={tab!=='lab'}><EvaluationLab session={session}/></Tabs.Content>
    {settingsOpen&&session&&<ModelSettings session={session} onApplied={s=>{setSubmitted(null);setSession(s);setText('');setPending(null);setError('');setNearBottom(true);setNewMessage(false)}} onBusy={value=>{if(value)++sessionEpoch.current;sendingRef.current=value;setBusy(value)}} onClose={()=>setSettingsOpen(false)} restoreFocus={()=>settingsButton.current?.focus()}/>}
    <footer className="app-footer"><span><ShieldCheck size={12}/>A support demo with deterministic SOP controls</span><span>Synthetic identity matching · Simulated actions</span></footer>
    <Dialog.Root open={mobileInspector} onOpenChange={setMobileInspector}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="inspector-drawer" onCloseAutoFocus={event=>{event.preventDefault();mobileInspectorButton.current?.focus()}}><Dialog.Title className="sr-only">Workflow inspector</Dialog.Title><Dialog.Description className="sr-only">Verification, context, and sanitized policy decisions</Dialog.Description><Dialog.Close className="dialog-close" aria-label="Close workflow inspector"><X size={20}/></Dialog.Close>{session&&<Inspector session={session}/>}</Dialog.Content></Dialog.Portal></Dialog.Root>
    <Dialog.Root open={demoOpen} onOpenChange={setDemoOpen}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="demo-dialog" onCloseAutoFocus={e=>{e.preventDefault();(demoInserted.current?inputRef:demoButton).current?.focus()}}><span className="eyebrow">SYNTHETIC DEMO SCENARIO</span><Dialog.Title>Choose a demo scenario</Dialog.Title><Dialog.Description>Explore the complete workflow with a fictional policyholder. These details are supplied test data, not real credentials.</Dialog.Description>{demo&&selectedDemo?<><div className="demo-scenarios" role="group" aria-label="Demo scenarios">{demo.scenarios.map(s=><Button key={s.id} variant="outline" aria-pressed={demoChoice===s.id} onClick={()=>setDemoChoice(s.id)}>{s.name}</Button>)}</div><p className="demo-context">{selectedDemo.description}</p><div className="demo-opening">{selectedDemo.opening}</div>{demoChoice==='frustrated'&&<details className="demo-identity"><summary>Synthetic identity for the next message</summary><p>{demo.opening}</p></details>}<Button onClick={()=>{demoInserted.current=true;setText(selectedDemo.opening);setDemoOpen(false)}}>Use this opening message<ArrowRight size={16}/></Button></>:demoError?<div><p role="alert">{demoError}</p><Button onClick={showDemo}>Retry loading scenarios</Button></div>:<p role="status">Loading synthetic scenario…</p>}<Dialog.Close className="dialog-close" aria-label="Close demo scenario"><X size={20}/></Dialog.Close></Dialog.Content></Dialog.Portal></Dialog.Root>
    <Dialog.Root open={resetOpen} onOpenChange={setResetOpen}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="demo-dialog" onCloseAutoFocus={e=>{e.preventDefault();resetButton.current?.focus()}} onEscapeKeyDown={e=>{if(busy)e.preventDefault()}} onPointerDownOutside={e=>{if(busy)e.preventDefault()}}><Dialog.Title>Start a new session?</Dialog.Title><Dialog.Description>This clears your conversation, summary, draft, and representative role. Fresh identity verification is required. {session?.model_connection?.retain_for_new_sessions ? 'Your API key and model selection will be retained because you opted in.' : 'Your session API key is removed. A BYOK model will show “Missing key — no API call” until you enter a key again; other connections return to the default model.'}</Dialog.Description><div className="summary-actions"><Dialog.Close asChild><Button variant="outline" disabled={busy}>Keep conversation</Button></Dialog.Close><Button disabled={busy} onClick={()=>void reset()}>Start new session</Button></div>{error&&<p role="alert">{error}</p>}</Dialog.Content></Dialog.Portal></Dialog.Root>
    <div className="sr-only" role="status" aria-live="polite">{!busy&&session?.messages.at(-1)?.role==='assistant'?session.messages.at(-1)?.text:''}</div>
  </Tabs.Root>
}

function EvaluationLab({ session }: { session: Session | null }) {
  const [scenarios,setScenarios]=useState<Scenario[]>([])
  const [selected,setSelected]=useState('margaret')
  const [results,setResults]=useState<Record<string,Evaluation>>({})
  const [running,setRunning]=useState(false)
  const [error,setError]=useState('')
  const [view,setView]=useState<'replay'|'checks'|'trace'>('replay')
  useEffect(()=>{api<Scenario[]>('/evaluations').then(setScenarios).catch(e=>setError(e.message))},[])
  const scenario=scenarios.find(s=>s.id===selected)
  const result=results[selected]
  async function run() {
    if(!session||running)return
    setRunning(true);setError('')
    try{const result=await api<Evaluation>('/evaluations/'+selected,{},session.csrf);setResults(old=>({...old,[selected]:result}))}catch(e){setError((e as Error).message)}finally{setRunning(false)}
  }
  return <><div className="page-heading"><div><div className="eyebrow">EVALUATION LAB</div><h1>Trust, made testable.</h1><p>Replay the scenarios. Inspect the decisions.</p></div><span className="lab-mode"><FlaskConical size={14}/>Scripted policy tests · No model calls</span></div>
    <main className="lab-layout"><aside className="scenario-list"><div className="scenario-list-header"><h2>Test scenarios</h2><span>{scenarios.length}</span></div>{[...new Set(scenarios.map(s=>s.category))].map(category=><div key={category}><h3>{category}</h3>{scenarios.filter(s=>s.category===category).map(s=><button key={s.id} onClick={()=>{setSelected(s.id);setError('')}} className={selected===s.id?'selected':''}><span>{s.name}</span>{results[s.id]?(results[s.id].passed?<CheckCircle2 size={15} className="status-good"/>:<X size={15} className="status-bad"/>):<ChevronRight size={14}/>}</button>)}</div>)}</aside>
      <section className="evaluation-detail" aria-label="Scenario result"><div className="evaluation-heading"><span className="eyebrow">{scenario?.category}</span><h2>{scenario?.name || 'Loading scenarios…'}</h2><p>{scenario?.description}</p><div className="evaluation-actions"><Button disabled={running||!session} onClick={run}>{running?<Loader2 size={15} className="spin"/>:result?<RotateCcw size={15}/>:<FlaskConical size={15}/>} {running?'Running…':result?'Replay scenario':'Run scenario'}</Button>{result&&<><span className={result.passed?'evaluation-pass':'status-bad'}>{result.passed?<CheckCircle2 size={16}/>:<X size={16}/>} {result.passed?'All assertions passed':'Needs attention'}</span><span className="micro muted">{result.duration_ms} ms</span><Button variant="ghost" size="sm" onClick={()=>setResults(old=>{const next={...old};delete next[selected];return next})}>Reset result</Button></>}</div></div>
      {error&&<p role="alert" className="lab-error">{error}</p>}
      {result?<><Tabs.Root value={view} onValueChange={value=>setView(value as typeof view)} style={{display:"contents"}}><Tabs.List className="result-tabs" aria-label="Evaluation evidence">{(['replay','checks','trace'] as const).map(v=><Tabs.Trigger key={v} value={v}>{v==='replay'?'Conversation replay':v==='checks'?'Expected vs. observed':'Decision trace'}</Tabs.Trigger>)}</Tabs.List><Tabs.Content className="result-body" value={view}>{view==='replay'?result.steps.map((step,n)=><article className="replay-step" key={n}><div className="replay-step-title"><span className="step-count">{String(n+1).padStart(2,'0')}</span><h3>{step.label}</h3>{step.passed?<Check size={16} className="status-good"/>:<X size={16} className="status-bad"/>}</div><div className="replay-response">{step.text}</div><div className="expected-line"><span>EXPECTED</span>{step.expected}</div><div className="expected-line"><span>OBSERVED</span>{step.phase}</div></article>):view==='checks'?<div className="assertion-list">{result.checks.map((check,n)=><div className="assertion" key={n}>{check.passed?<CheckCircle2 size={16} className="status-good"/>:<X size={16} className="status-bad"/>}<div><strong>{check.expected}</strong><p>{check.observed}</p></div><span>{check.passed?'Pass':'Fail'}</span></div>)}</div>:<Trace events={result.events}/>}</Tabs.Content></Tabs.Root><div className="evaluation-foot">{result.mode} · fixtures <span className="mono">{result.fixture_version}</span> · Live-model conversational quality is evaluated separately.</div></>:<div className="evaluation-empty"><span className="evaluation-empty-icon"><ClipboardList size={25}/></span><h3>A clear contract for this conversation.</h3><p>Each replay runs the actual SOP controller with scripted interpretations, a fixed clock, and the supplied fixtures.</p><div className="expectations"><span className="eyebrow">WHAT THIS SCENARIO CHECKS</span>{scenario?.expectations.map((item,n)=><div key={n}><span>{String(n+1).padStart(2,'0')}</span>{item}</div>)}</div><p className="micro muted">Runs are isolated from your Playground session. Passing a scripted test is not evidence of live-model quality.</p></div>}
      </section></main></>
}
