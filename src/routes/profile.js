import { authenticate } from '../middleware/authenticate.js'
import { updateProfileColor } from '../controllers/profile.js'

const PALETTE = ['terracotta', 'mustard', 'sage', 'kabut', 'senja', 'ink']

export default async function profileRoutes(fastify) {
  // PATCH /api/profile/color
  fastify.patch('/color', {
    preHandler: authenticate,
    schema: {
      body: {
        type: 'object',
        required: ['color'],
        properties: {
          color: { type: 'string', enum: PALETTE },
        },
      },
    },
  }, updateProfileColor)
}
