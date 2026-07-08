import prisma from '../db.js'

const DAY_LABELS_ID = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']

function dayKey(dt) {
  try {
    return dt.toISOString().slice(0, 10) // "YYYY-MM-DD"
  } catch {
    return null
  }
}

function indexByDay(rows, field) {
  const days = new Set()
  const byDay = {}
  for (const r of rows) {
    const k = dayKey(r.created_at)
    if (!k) continue
    days.add(k)
    if (!(k in byDay)) byDay[k] = r[field]
  }
  return { days, byDay }
}

function computeStreak(cekDays, today) {
  let current = 0
  let d = new Date(today)
  const todayKey = today.toISOString().slice(0, 10)

  if (!cekDays.has(todayKey)) {
    d.setDate(d.getDate() - 1)
  }

  while (true) {
    const k = d.toISOString().slice(0, 10)
    if (!cekDays.has(k)) break
    current++
    d.setDate(d.getDate() - 1)
  }

  let longest = 0
  let run = 0
  let prev = null
  const sorted = [...cekDays].sort()

  for (const k of sorted) {
    const cur = new Date(k)
    if (prev !== null) {
      const diff = (cur - prev) / (1000 * 60 * 60 * 24)
      if (diff === 1) {
        run++
      } else {
        run = 1
      }
    } else {
      run = 1
    }
    longest = Math.max(longest, run)
    prev = cur
  }

  return { current, longest }
}

function buildChart(today, cekByDay, jurByDay) {
  const chart = []
  for (let i = 6; i >= 0; i--) {
    const d0 = new Date(today)
    d0.setDate(d0.getDate() - i)
    const k = d0.toISOString().slice(0, 10)
    const mood = cekByDay[k] ?? jurByDay[k] ?? null
    const source = k in cekByDay ? 'cekdiri' : k in jurByDay ? 'journal' : null
    const jsDay = d0.getDay()
    const labelIndex = jsDay === 0 ? 6 : jsDay - 1
    chart.push({ date: k, label: DAY_LABELS_ID[labelIndex], mood, source })
  }
  return chart
}

export async function getUserStats(request, reply) {
  const since60 = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000)

  const [cekRows, jurRows] = await Promise.all([
    prisma.cekDiriEntry.findMany({
      where: { user_id: request.user.id, created_at: { gte: since60 } },
      orderBy: { created_at: 'desc' },
      take: 1000,
    }),
    prisma.journalEntry.findMany({
      where: { user_id: request.user.id, created_at: { gte: since60 } },
      orderBy: { created_at: 'desc' },
      take: 1000,
    }),
  ])

  const { days: cekDays, byDay: cekByDay } = indexByDay(cekRows, 'feeling')
  const { byDay: jurByDay } = indexByDay(jurRows, 'mood')

  const todayUTC = new Date(new Date().toISOString().slice(0, 10) + 'T00:00:00Z')
  const todayKey = todayUTC.toISOString().slice(0, 10)

  const { current, longest } = computeStreak(cekDays, todayUTC)
  const chart = buildChart(todayUTC, cekByDay, jurByDay)

  return reply.send({
    streak: {
      current,
      longest,
      today: cekDays.has(todayKey),
    },
    chart,
  })
}
