import { authenticate } from '../middleware/authenticate.js'
import {
  saveKuis,
  getKuisLatest,
} from '../controllers/kuis.js'

export default async function kuisRoutes(fastify) {
  // POST /api/kuis/result
  fastify.post('/result', {
    preHandler: authenticate,
    schema: {
      body: {
        type: 'object',
        required: ['dominant'],
        properties: {
          dominant: { type: 'string', enum: ['chimp', 'human', 'computer'] },
          counts: { type: 'object' },
        },
      },
    },
  }, saveKuis)

  // GET /api/kuis/latest
  fastify.get('/latest', { preHandler: authenticate }, getKuisLatest)
}
