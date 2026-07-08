import prisma from '../db.js'

function kuisToDict(r) {
  return {
    id: r.id,
    user_id: r.user_id,
    dominant: r.dominant,
    counts: r.counts,
    createdAt: r.created_at.toISOString(),
  }
}

export async function saveKuis(request, reply) {
  const { dominant, counts = {} } = request.body

  const result = await prisma.kuisResult.create({
    data: {
      user_id: request.user.id,
      dominant,
      counts,
    },
  })

  return reply.code(201).send({ result: kuisToDict(result) })
}

export async function getKuisLatest(request, reply) {
  const row = await prisma.kuisResult.findFirst({
    where: { user_id: request.user.id },
    orderBy: { created_at: 'desc' },
  })

  if (!row) return reply.send({ result: null })
  return reply.send({ result: kuisToDict(row) })
}
