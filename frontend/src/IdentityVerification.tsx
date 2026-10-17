import { useRef, useState } from 'react'
import { Button } from './components/Button'

const FIELDS = {
  name: ['Full name', 'Example: Alex Morgan'],
  dob: ['Date of birth', 'YYYY-MM-DD, for example 1985-03-15'],
  phone: ['Phone', 'Example: (202) 555-0100'],
  email: ['Email', 'Example: alex@example.com'],
  id_last4: ['SSN / approved ID last four', 'Exactly four digits'],
} as const
type Field = keyof typeof FIELDS
export type VerificationValue = { field: Field; value: string; identifier_type?: string }

export function IdentityVerification({ disabled, onSubmit }: {
  disabled: boolean; onSubmit: (fields: VerificationValue[]) => Promise<boolean>
}) {
  const [fields, setFields] = useState<Field[]>(['name', 'dob', 'phone'])
  const [values, setValues] = useState(['', '', ''])
  const [idType, setIdType] = useState('ssn_last4')
  const panel = useRef<HTMLDetailsElement>(null)
  return <details className="verification-form" ref={panel}>
    <summary>Prefer a form? Verify with three details (optional)</summary>
    <p className="small">Chat works too. Choose three different fields; SSN is optional. All three must match one policyholder. Submitting replaces previously entered values for these fields.</p>
    <form autoComplete="off" onSubmit={async event => {
      event.preventDefault()
      if (await onSubmit(fields.map((field, n) => ({ field, value: values[n].trim(), ...(field === 'id_last4' ? { identifier_type: idType } : {}) })))) {
        setValues(['', '', ''])
        if (panel.current) panel.current.open = false
      }
    }}>
      {fields.map((field, n) => <div className="verification-row" key={n}>
        <label><span className="sr-only">Identity field {n + 1}</span><select aria-label={`Identity field ${n + 1}`} disabled={disabled} value={field} onChange={event => {
          setFields(fields.map((old, index) => index === n ? event.target.value as Field : old))
          setValues(values.map((old, index) => index === n ? '' : old))
        }}>{(Object.keys(FIELDS) as Field[]).filter(key => key === field || !fields.includes(key)).map(key => <option key={key} value={key}>{FIELDS[key][0]}</option>)}</select></label>
        <label><span>{FIELDS[field][0]}</span><input aria-label={FIELDS[field][0]} aria-describedby={`identity-example-${n}`} value={values[n]} disabled={disabled} required maxLength={field === 'id_last4' ? 4 : 160}
          type={field === 'email' ? 'email' : field === 'phone' ? 'tel' : field === 'id_last4' ? 'password' : 'text'}
          inputMode={field === 'id_last4' ? 'numeric' : undefined} pattern={field === 'dob' ? '\\d{4}-\\d{2}-\\d{2}' : field === 'id_last4' ? '\\d{4}' : undefined}
          onChange={event => setValues(values.map((old, index) => index === n ? event.target.value : old))}/><small id={`identity-example-${n}`}>{FIELDS[field][1]}</small></label>
        {field === 'id_last4' && <label>Identifier type<select value={idType} disabled={disabled} onChange={event => setIdType(event.target.value)}><option value="ssn_last4">SSN last four</option><option value="national_id_last4">Approved national ID last four</option></select></label>}
      </div>)}
      <p className="micro muted">Synthetic demo only. Don’t enter real personal information. Values are visible while editing and redacted in saved conversation views. Individual match results stay private.</p>
      <Button type="submit" size="sm" disabled={disabled || values.some(value => !value.trim())}>Submit verification details</Button>
    </form>
  </details>
}
