import { useState, type RefObject } from 'react'
import { ChevronDown, ClipboardList } from 'lucide-react'
import { api } from './api'
import { Button } from './components/Button'

const FIELDS = {
  name: ['Full name', 'Example: Alex Morgan'],
  dob: ['Date of birth', 'e.g. 03/15/1985'],
  phone: ['Phone', 'Example: (202) 555-0100'],
  email: ['Email', 'Example: alex@example.com'],
  id_last4: ['SSN / approved ID last four', 'Exactly four digits'],
} as const
type Field = keyof typeof FIELDS
export type VerificationValue = { field: Field; value: string; identifier_type?: string }

export function IdentityVerification({ disabled, onSubmit, panelRef }: {
  disabled: boolean; onSubmit: (fields: VerificationValue[], displayText: string) => Promise<boolean>; panelRef: RefObject<HTMLDetailsElement | null>
}) {
  const [fields, setFields] = useState<Field[]>(['name', 'dob', 'phone'])
  const [values, setValues] = useState(['', '', ''])
  const [idType, setIdType] = useState('ssn_last4')
  const [loadingDemo, setLoadingDemo] = useState(false)
  const [demoError, setDemoError] = useState('')
  return <details className="verification-form" ref={panelRef}>
    <summary><ClipboardList size={17}/><span>Prefer a form?<small>Verify with three details · optional</small></span><ChevronDown size={14}/></summary>
    <div className="verification-body">
    <div className="verification-topline"><p className="small">Choose three different fields for one policyholder. SSN is optional.</p>
    <Button className="verification-demo" variant="outline" size="sm" title="Demo only · fills editable fields without submitting" disabled={disabled || loadingDemo} onClick={async () => {
      setLoadingDemo(true); setDemoError('')
      try {
        const demo = await api<{ verification_details: Record<'name' | 'dob' | 'phone', string> }>('/demo-starter')
        setFields(['name', 'dob', 'phone'])
        setValues([demo.verification_details.name, demo.verification_details.dob, demo.verification_details.phone])
      } catch (error) { setDemoError((error as Error).message) }
      finally { setLoadingDemo(false) }
    }}>{loadingDemo ? 'Loading synthetic details…' : 'Use synthetic verification details'}</Button></div>
    {demoError && <p role="alert">{demoError}</p>}
    <form autoComplete="off" aria-describedby="verification-privacy" onSubmit={async event => {
      event.preventDefault()
      const submitted = fields.map((field, n) => ({ field, value: values[n].trim(), ...(field === 'id_last4' ? { identifier_type: idType } : {}) }))
      if (await onSubmit(submitted, submitted.map(({field,value}) => `${FIELDS[field][0]}: ${value}`).join('\n'))) {
        setValues(['', '', ''])
        if (panelRef.current) panelRef.current.open = false
      }
    }}>
      <div className="verification-fields">{fields.map((field, n) => <div className="verification-row" key={n}>
        <label><span className="sr-only">Identity field {n + 1}</span><select aria-label={`Identity field ${n + 1}`} disabled={disabled || loadingDemo} value={field} onChange={event => {
          setFields(fields.map((old, index) => index === n ? event.target.value as Field : old))
          setValues(values.map((old, index) => index === n ? '' : old))
        }}>{(Object.keys(FIELDS) as Field[]).filter(key => key === field || !fields.includes(key)).map(key => <option key={key} value={key}>{FIELDS[key][0]}</option>)}</select></label>
        <label><span className="sr-only">{FIELDS[field][0]}</span><input aria-label={FIELDS[field][0]} aria-describedby={`identity-example-${n}`} placeholder={FIELDS[field][1]} value={values[n]} disabled={disabled || loadingDemo} required maxLength={field === 'id_last4' ? 4 : 160}
          type={field === 'email' ? 'email' : field === 'phone' ? 'tel' : field === 'id_last4' ? 'password' : 'text'}
          inputMode={field === 'id_last4' ? 'numeric' : undefined} pattern={field === 'id_last4' ? '\\d{4}' : undefined}
          onChange={event => setValues(values.map((old, index) => index === n ? event.target.value : old))}/><small className="sr-only" id={`identity-example-${n}`}>{field === 'dob' ? 'Use MM/DD/YYYY, YYYY-MM-DD, or a spelled-out date such as March 15, 1985.' : FIELDS[field][1]}</small></label>
        {field === 'id_last4' && <label>Identifier type<select value={idType} disabled={disabled || loadingDemo} onChange={event => setIdType(event.target.value)}><option value="ssn_last4">SSN last four</option><option value="national_id_last4">Approved national ID last four</option></select></label>}
      </div>)}</div>
      <p id="verification-privacy" className="sr-only">Use synthetic details only. Values are visible while editing and redacted in saved history. Individual match results stay private. Submitting replaces previously entered values for these fields.</p>
      <div className="verification-footer"><p className="micro muted">Synthetic details only. Select Verify to continue.</p><div className="verification-actions"><Button variant="outline" size="sm" disabled={disabled || loadingDemo} onClick={()=>{setValues(['', '', '']);setDemoError('');panelRef.current?.querySelector('input')?.focus()}}>Clear</Button><Button type="submit" size="sm" disabled={disabled || loadingDemo || values.some(value => !value.trim())}>Verify details</Button></div></div>
    </form>
    </div>
  </details>
}
