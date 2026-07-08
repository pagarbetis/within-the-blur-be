import prisma from '../db.js'

export async function saveCekdiri(request, reply) {
  const { feeling, note } = request.body

  const entry = await prisma.cekDiriEntry.create({
    data: {
      user_id: request.user.id,
      feeling,
      note: note ?? '',
    },
  })

  return reply.code(201).send({
    entry: {
      id: entry.id,
      user_id: entry.user_id,
      feeling: entry.feeling,
      note: entry.note,
      createdAt: entry.created_at.toISOString(),
    },
  })
}

export async function listCekdiri(request, reply) {
  const days = Math.max(1, Math.min(Number(request.query.days ?? 7), 90))
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000)

  const rows = await prisma.cekDiriEntry.findMany({
    where: {
      user_id: request.user.id,
      created_at: { gte: since },
    },
    orderBy: { created_at: 'desc' },
    take: 500,
  })

  const entries = rows.map(e => ({
    id: e.id,
    user_id: e.user_id,
    feeling: e.feeling,
    note: e.note,
    createdAt: e.created_at.toISOString(),
  }))

  return reply.send({ entries, count: entries.length })
}
