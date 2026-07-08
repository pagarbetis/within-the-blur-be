import { authenticate } from '../middleware/authenticate.js'
import { getUserStats } from '../controllers/stats.js'

export default async function statsRoutes(fastify) {
  // GET /api/stats
  fastify.get('/', { preHandler: authenticate }, getUserStats)
}
