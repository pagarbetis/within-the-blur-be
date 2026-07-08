import { verifyToken } from '../helpers/auth.js'
import prisma from '../db.js'

/**
 * Fastify preHandler hook — attaches `request.user` from JWT.
 * Reads token from cookie `access_token` OR `Authorization: Bearer <token>` header.
 */
export async function authenticate(request, reply) {
  let token = request.cookies?.access_token

  if (!token) {
    const auth = request.headers.authorization ?? ''
    if (auth.startsWith('Bearer ')) token = auth.slice(7)
  }

  if (!token) {
    return reply.code(401).send({ error: 'Not authenticated' })
  }

  let payload
  try {
    payload = verifyToken(token)
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return reply.code(401).send({ error: 'Token expired' })
    }
    return reply.code(401).send({ error: 'Invalid token' })
  }

  if (payload.type !== 'access') {
    return reply.code(401).send({ error: 'Invalid token type' })
  }

  const user = await prisma.user.findUnique({ where: { id: payload.sub } })
  if (!user) {
    return reply.code(401).send({ error: 'User not found' })
  }

  request.user = user
}
