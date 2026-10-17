import { useRef, useState } from 'react'
import { api } from './api'
import { Button } from './components/Button'

const FIELDS = {
  name: ['Full name', 'Example: Alex Morgan'],
  dob: ['Date of birth', 'ISO, March 15, 1985, or 03/15/1985'],
  phone: ['Phone', 'Example: (202) 555-0100'],
  email: ['Email', 'Example: alex@example.com'],
  id_last4: ['SSN / approved ID last four', 'Exactly four digits'],
} as const
type Field = keyof typeof FIELDS
export type VerificationValue = { field: Field; value: string; identifier_type?: string }

export function IdentityVerification({ disabled, onSubmit }: {
  disabled: boolean; onSubmit: (fields: VerificationValue[], displayText: string) => Promise<boolean>
}) {
  const [fields, setFields] = useState<Field[]>(['name', 'dob', 'phone'])
  const [values, setValues] = useState(['', '', ''])
  const [idType, setIdType] = useState('ssn_last4')
  const [loadingDemo, setLoadingDemo] = useState(false)
  const [demoError, setDemoError] = useState('')
  const panel = useRef<HTMLDetailsElement>(null)
  return <details className="verification-form" ref={panel}>
    <summary>Prefer a form? Verify with three details (optional)</summary>
    <p className="small">Chat works too. Choose three different fields; SSN is optional. All three must match one policyholder. Submitting replaces previously entered values for these fields.</p>
    <div className="verification-demo"><Button variant="outline" size="sm" disabled={disabled || loadingDemo} onClick={async () => {
      setLoadingDemo(true); setDemoError('')
      try {
        const demo = await api<{ verification_details: Record<'name' | 'dob' | 'phone', string> }>('/demo-starter')
        setFields(['name', 'dob', 'phone'])
        setValues([demo.verification_details.name, demo.verification_details.dob, demo.verification_details.phone])
      } catch (error) { setDemoError((error as Error).message) }
      finally { setLoadingDemo(false) }
    }}>{loadingDemo ? 'Loading synthetic details…' : 'Use synthetic verification details'}</Button><span className="micro muted">Demo only · editable · select Verify afterward</span></div>
    {demoError && <p role="alert">{demoError}</p>}
    <form autoComplete="off" onSubmit={async event => {
      event.preventDefault()
      const submitted = fields.map((field, n) => ({ field, value: values[n].trim(), ...(field === 'id_last4' ? { identifier_type: idType } : {}) }))
      if (await onSubmit(submitted, submitted.map(({field,value}) => `${FIELDS[field][0]}: ${value}`).join('\n'))) {
        setValues(['', '', ''])
        if (panel.current) panel.current.open = false
      }
    }}>
      <div className="verification-fields">{fields.map((field, n) => <div className="verification-row" key={n}>
        <label><span className="sr-only">Identity field {n + 1}</span><select aria-label={`Identity field ${n + 1}`} disabled={disabled || loadingDemo} value={field} onChange={event => {
          setFields(fields.map((old, index) => index === n ? event.target.value as Field : old))
          setValues(values.map((old, index) => index === n ? '' : old))
        }}>{(Object.keys(FIELDS) as Field[]).filter(key => key === field || !fields.includes(key)).map(key => <option key={key} value={key}>{FIELDS[key][0]}</option>)}</select></label>
        <label><span>{FIELDS[field][0]}</span><input aria-label={FIELDS[field][0]} aria-describedby={`identity-example-${n}`} value={values[n]} disabled={disabled || loadingDemo} required maxLength={field === 'id_last4' ? 4 : 160}
          type={field === 'email' ? 'email' : field === 'phone' ? 'tel' : field === 'id_last4' ? 'password' : 'text'}
          inputMode={field === 'id_last4' ? 'numeric' : undefined} pattern={field === 'id_last4' ? '\\d{4}' : undefined}
          onChange={event => setValues(values.map((old, index) => index === n ? event.target.value : old))}/><small id={`identity-example-${n}`}>{FIELDS[field][1]}</small></label>
        {field === 'id_last4' && <label>Identifier type<select value={idType} disabled={disabled || loadingDemo} onChange={event => setIdType(event.target.value)}><option value="ssn_last4">SSN last four</option><option value="national_id_last4">Approved national ID last four</option></select></label>}
      </div>)}</div>
      <p className="micro muted">Synthetic demo only. Don’t enter real personal information. Values are visible while editing and redacted in saved conversation views. Individual match results stay private.</p>
      <Button type="submit" size="sm" disabled={disabled || loadingDemo || values.some(value => !value.trim())}>Verify details</Button>
    </form>
  </details>
}
