import { ScheduledClass, TimetableRequest } from '../lib/api'

interface Props {
  req: TimetableRequest
  classes: ScheduledClass[]
  sectionId: string
  highlightCourse?: string | null
}

// Visual category for a class — drives color coding.
function categoryOf(c: ScheduledClass): 'theory' | 'lab' | 'elective' | 'activity' | 'locked' {
  const code = c.course_code || ''
  const label = c.label || ''
  if (c.is_lab) return 'lab'
  if (code.startsWith('ELEC_') || label.includes('/')) return 'elective'
  if (
    code === 'IIC-Activity' ||
    code === 'BENGDIP2' ||
    label === 'IIC-Activity' ||
    label === 'BENGDIP2' ||
    code === 'DEPT_ACT' ||
    label === 'Dept Activity'
  )
    return 'locked'
  if (
    code === 'CRC' ||
    code === 'PROCTORING' ||
    code === 'TUTORIAL' ||
    code === 'REMEDIAL' ||
    code === 'NCMC'
  )
    return 'activity'
  return 'theory'
}

const STYLE_BY_CAT: Record<string, string> = {
  theory: 'bg-sky-50 border-sky-200 text-sky-900',
  lab: 'bg-violet-50 border-violet-200 text-violet-900',
  elective: 'bg-amber-50 border-amber-200 text-amber-900',
  activity: 'bg-slate-50 border-slate-300 text-slate-700',
  locked: 'bg-rose-50 border-rose-200 text-rose-900',
}

export default function TimetableGrid({ req, classes, sectionId, highlightCourse }: Props) {
  const days = req.time_config.days
  const slots = Array.from({ length: req.time_config.slots_per_day }, (_, i) => i + 1)
  const teaAfter = req.time_config.tea_break.after_slot
  const lunchAfter = req.time_config.lunch_break.after_slot
  const teaDuration = req.time_config.tea_break.duration_min
  const lunchDuration = req.time_config.lunch_break.duration_min

  // Build a list of columns interleaving slot columns + break columns.
  type Col =
    | { kind: 'slot'; t: number }
    | { kind: 'break'; label: string; durationMin: number }
  const cols: Col[] = []
  for (const t of slots) {
    cols.push({ kind: 'slot', t })
    if (t === teaAfter) cols.push({ kind: 'break', label: 'TEA BREAK', durationMin: teaDuration })
    if (t === lunchAfter)
      cols.push({ kind: 'break', label: 'LUNCH BREAK', durationMin: lunchDuration })
  }

  const grid = new Map<string, ScheduledClass[]>()
  for (const c of classes) {
    if (c.section_id !== sectionId) continue
    const k = `${c.day}-${c.slot}`
    const arr = grid.get(k) ?? []
    arr.push(c)
    grid.set(k, arr)
  }

  const timing = (t: number) => req.time_config.slot_timings?.[t - 1]

  return (
    <div className="overflow-x-auto">
      <table className="border-collapse text-xs w-full table-fixed">
        <colgroup>
          <col style={{ width: 64 }} />
          {cols.map((c, i) => (
            <col
              key={i}
              style={c.kind === 'break' ? { width: 44 } : { width: 'auto' }}
            />
          ))}
        </colgroup>
        <thead>
          <tr className="bg-slate-900 text-white">
            <th className="border border-slate-800 px-2 py-2 text-left">Day</th>
            {cols.map((c, i) =>
              c.kind === 'slot' ? (
                <th key={i} className="border border-slate-800 px-1 py-1 text-center">
                  <div className="text-[11px] font-semibold">Slot {c.t}</div>
                  <div className="text-[10px] font-normal opacity-70">
                    {timing(c.t) ? `${timing(c.t)!.start}–${timing(c.t)!.end}` : ''}
                  </div>
                </th>
              ) : (
                <th
                  key={i}
                  className="border border-slate-800 bg-amber-300/90 text-slate-900 px-0.5 align-middle"
                >
                  <div
                    className="text-[10px] font-bold tracking-wider whitespace-nowrap leading-tight"
                    style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                  >
                    {c.label}
                  </div>
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {days.map((d, ri) => (
            <tr key={d} className={ri % 2 ? 'bg-slate-50/60' : 'bg-white'}>
              <td className="border border-slate-300 px-2 py-2 font-semibold bg-slate-100 text-center text-slate-800">
                {d}
              </td>
              {cols.map((c, i) => {
                if (c.kind === 'break') {
                  return (
                    <td
                      key={i}
                      className="border border-slate-300 bg-amber-100/70 align-middle text-center"
                    >
                      <div
                        className="text-[10px] text-amber-900 font-semibold opacity-80 whitespace-nowrap"
                        style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                      >
                        {c.durationMin}m
                      </div>
                    </td>
                  )
                }
                const t = c.t
                const items = grid.get(`${d}-${t}`) ?? []
                const hl =
                  highlightCourse &&
                  items.some(
                    (i) => i.course_code === highlightCourse || i.label === highlightCourse,
                  )
                if (items.length === 0) {
                  return (
                    <td
                      key={i}
                      className="border border-slate-200 align-middle text-center text-slate-300 italic h-16"
                    >
                      {d === 'SAT' ? '—' : ''}
                    </td>
                  )
                }
                // Group items so paired labs render as one stacked cell
                return (
                  <td
                    key={i}
                    className={[
                      'border align-top p-1 h-16',
                      hl ? 'ring-2 ring-indigo-500 ring-inset' : '',
                    ].join(' ')}
                  >
                    <div className="flex flex-col gap-0.5 h-full">
                      {items.map((it, idx) => {
                        const cat = categoryOf(it)
                        return (
                          <div
                            key={idx}
                            className={[
                              'rounded-md border px-1.5 py-0.5 leading-tight flex-1 flex flex-col justify-center',
                              STYLE_BY_CAT[cat] || STYLE_BY_CAT.theory,
                            ].join(' ')}
                            title={`${it.label || it.course_code}\n${it.faculty_id ?? ''}`}
                          >
                            <div className="font-semibold truncate text-[11px]">
                              {it.label || it.course_code}
                            </div>
                            <div className="text-[9px] opacity-70 truncate">
                              {it.faculty_id ?? ''}
                              {it.batch_id ? ` · ${it.batch_id}` : ''}
                              {it.room ? ` · ${it.room}` : ''}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <Legend />
    </div>
  )
}

function Legend() {
  const items: { cat: keyof typeof STYLE_BY_CAT; label: string }[] = [
    { cat: 'theory', label: 'Theory' },
    { cat: 'lab', label: 'Lab' },
    { cat: 'elective', label: 'Elective block' },
    { cat: 'activity', label: 'Activity (CRC / Proctoring / NCMC / …)' },
    { cat: 'locked', label: 'Fixed (Sat lock / Dept Activity)' },
  ]
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-600">
      {items.map((i) => (
        <span
          key={i.cat}
          className={[
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border',
            STYLE_BY_CAT[i.cat],
          ].join(' ')}
        >
          <span className="inline-block h-2 w-2 rounded-sm bg-current opacity-80" />
          {i.label}
        </span>
      ))}
      <span className="ml-auto inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border border-amber-300 bg-amber-100/70 text-amber-900">
        TEA / LUNCH BREAK
      </span>
    </div>
  )
}
