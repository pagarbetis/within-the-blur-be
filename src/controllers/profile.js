import prisma from '../db.js'
import { userPublic } from '../helpers/auth.js'

export async function updateProfileColor(request, reply) {
  const { color } = request.body

  const user = await prisma.user.update({
    where: { id: request.user.id },
    data: { profile_color: color },
  })

  return reply.send({ user: userPublic(user) })
}
