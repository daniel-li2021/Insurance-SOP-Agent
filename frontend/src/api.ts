export type Event = { sequence: number; code: string; phase: string; at: number; detail: string; references: string[] }
export type Message = { id: string; role: 'user' | 'assistant'; text: string; protected: boolean; references: string[] }
export type SummaryCase = { case_id: string; case_type: string; status: string; denial_reason: string | null; payment: string; allowed_maximum: string; appeal_deadline: string | null; deadline_passed: boolean; next_steps: string; unresolved: string }
export type Summary = { id: string; text: string; cases?: SummaryCase[]; recipient: string; expires_at: number; status: string; receipt: string | null }
export type Session = {
  model_connection: { ready: boolean; retain_for_new_sessions: boolean };
  version: number; phase: string; verified: boolean; csrf: string; model: string;
  verification: { count: number; required: number; fields: string[]; representative: boolean };
  intent: string; case_id: string | null; case_status: string | null; choices: { case_id: string; case_type: string; created_at: string; status: string }[];
  emotion: string; human_offered: boolean; assistance_paused: boolean; unresolved: string[]; messages: Message[]; events: Event[];
  summary: Summary | null; fixture_version: string; auth_expires_at: number | null; server_time: number;
}
export type Scenario = { id: string; name: string; category: string; description: string; expectations: string[] }
export type Evaluation = { id: string; passed: boolean; mode: string; fixture_version: string; checks: { expected: string; observed: string; passed: boolean }[]; steps: { label: string; expected: string; phase: string; text: string; passed: boolean }[]; events: Event[]; duration_ms: number }
export class ApiError extends Error { constructor(message: string, public status: number) { super(message) } }
export async function api<T>(path: string, body?: unknown, csrf?: string): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 35000)
  try {
    const response = await fetch('/api' + path, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
      headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(csrf ? { 'X-CSRF-Token': csrf } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal })
    const data = await response.json()
    if (!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'The request was not accepted. Check your input and retry.', response.status)
    return data as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The request timed out. Retry safely; duplicate actions are prevented.', 504)
    throw error
  } finally { window.clearTimeout(timeout) }
}
