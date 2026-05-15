import { useState } from 'react'
import { api, GenerateResponse, TimetableRequest } from '../lib/api'

interface Props {
  prior: TimetableRequest | null
  onApplied: (resp: GenerateResponse, req: TimetableRequest) => void
  onExplain: () => Promise<string>
}

export default function ChatPanel({ prior, onApplied, onExplain }: Props) {
  const [msgs, setMsgs] = useState<{ role: 'user' | 'assistant'; text: string }[]>([
    {
      role: 'assistant',
      text:
        "Tell me what to change. Examples:\n• 'Dr Sampath is on leave Wednesdays'\n• 'Lock Dept Activity to FRI 5-7'\n• 'Move the elective to MON-2, TUE-3, WED-3, THU-3'\n• 'Cap Prof Nagi Teja Reddy at 4 classes per day'\n• 'Explain Friday' (for a summary)",
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)

  async function send() {
    const t = input.trim()
    if (!t) return
    setInput('')
    setMsgs((m) => [...m, { role: 'user', text: t }])
    setBusy(true)
    try {
      if (/^(explain|why|what)/i.test(t)) {
        const explanation = await onExplain()
        setMsgs((m) => [...m, { role: 'assistant', text: explanation }])
      } else {
        const out = await api.llmParse(t, prior ?? undefined)
        // Build the assistant reply with applied + errors detail.
        const parts: string[] = []
        if (out.message) parts.push(out.message)
        if (out.applied && out.applied.length) {
          parts.push('Applied:\n' + out.applied.map((a) => '  · ' + a).join('\n'))
        }
        if (out.errors && out.errors.length) {
          parts.push('Errors:\n' + out.errors.map((e) => '  ! ' + e).join('\n'))
        }
        if (out.timetable) {
          parts.push(
            `Re-solved: ${out.timetable.status} · ${out.timetable.classes.length} placements · ${out.timetable.solve_time_sec.toFixed(2)}s`,
          )
        }
        if (out.active_model) parts.push(`(model: ${out.active_model})`)
        setMsgs((m) => [...m, { role: 'assistant', text: parts.join('\n\n') }])

        // If the backend applied the patch and re-solved, propagate up so the
        // grid switches to the new timetable.
        if (out.action === 'patch' && out.request && out.timetable && out.job_id) {
          onApplied(
            {
              job_id: out.job_id,
              preflight: out.preflight!,
              timetable: out.timetable,
              verification: out.verification ?? null,
            },
            out.request,
          )
        }
      }
    } catch (e: any) {
      setMsgs((m) => [
        ...m,
        { role: 'assistant', text: `Error: ${e.message}` },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b bg-slate-100">
        <div className="font-semibold text-sm">Assistant</div>
        <div className="text-[11px] text-slate-500">Natural language → timetable</div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 text-sm">
        {msgs.map((m, i) => (
          <div
            key={i}
            className={m.role === 'user' ? 'text-slate-800' : 'text-slate-700 bg-white border rounded-md p-2'}
          >
            {m.role === 'user' ? (
              <div className="bg-indigo-600 text-white inline-block rounded-md px-3 py-1.5 whitespace-pre-wrap">
                {m.text}
              </div>
            ) : (
              <pre className="whitespace-pre-wrap font-sans">{m.text}</pre>
            )}
          </div>
        ))}
        {busy && <div className="text-slate-400 italic">Thinking…</div>}
      </div>
      <div className="p-2 border-t flex gap-2">
        <input
          className="flex-1 border rounded-md px-2 py-1 text-sm"
          placeholder="Type a request…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
        <button
          onClick={send}
          disabled={busy}
          className="bg-indigo-600 text-white text-sm rounded-md px-3 py-1 disabled:bg-indigo-300"
        >
          Send
        </button>
      </div>
    </div>
  )
}
