import prisma from '../db.js'

function validateUnlockAt(raw) {
  if (!raw) return null
  let dt
  try {
    dt = new Date(raw.replace('Z', '+00:00').endsWith(':00') ? raw : raw)
    if (isNaN(dt.getTime())) throw new Error('invalid date')
  } catch {
    throw { statusCode: 400, message: 'Format tanggal tidak valid.' }
  }
  const now = new Date()
  if (dt <= now) throw { statusCode: 400, message: 'Tanggal buka surat harus di masa depan.' }
  const maxDt = new Date(now.getTime() + 3 * 365 * 24 * 60 * 60 * 1000)
  if (dt > maxDt) throw { statusCode: 400, message: 'Maksimal 3 tahun dari sekarang.' }
  return dt
}

function entryToDict(e) {
  return {
    id: e.id,
    user_id: e.user_id,
    title: e.title,
    body: e.body,
    mood: e.mood,
    unlockAt: e.unlock_at ? e.unlock_at.toISOString() : null,
    createdAt: e.created_at ? e.created_at.toISOString() : null,
  }
}

function isLocked(entry) {
  const ua = entry.unlockAt
  if (!ua) return false
  try {
    return new Date(ua) > new Date()
  } catch {
    return false
  }
}

function maskLockedEntry(entry) {
  if (isLocked(entry)) {
    const { body, ...rest } = entry
    return { ...rest, body: null, locked: true }
  }
  return { ...entry, locked: false }
}

export async function createJournal(request, reply) {
  const { body: bodyText, title, mood, unlockAt } = request.body

  let unlock_at
  try {
    unlock_at = validateUnlockAt(unlockAt)
  } catch (e) {
    return reply.code(e.statusCode ?? 400).send({ error: e.message })
  }

  const entry = await prisma.journalEntry.create({
    data: {
      user_id: request.user.id,
      title: (title ?? '').trim() || 'Tanpa Judul',
      body: bodyText.trim(),
      mood: (mood ?? 'tenang').trim(),
      unlock_at,
    },
  })

  return reply.code(201).send({ entry: maskLockedEntry(entryToDict(entry)) })
}

export async function listJournal(request, reply) {
  const entries = await prisma.journalEntry.findMany({
    where: { user_id: request.user.id },
    orderBy: { created_at: 'desc' },
    take: 500,
  })

  const result = entries.map(e => maskLockedEntry(entryToDict(e)))
  return reply.send({ entries: result, count: result.length })
}

export async function deleteJournal(request, reply) {
  const { entryId } = request.params

  const deleted = await prisma.journalEntry.deleteMany({
    where: { id: entryId, user_id: request.user.id },
  })

  if (deleted.count === 0) {
    return reply.code(404).send({ error: 'Entry tidak ditemukan' })
  }

  return reply.send({ ok: true })
}
