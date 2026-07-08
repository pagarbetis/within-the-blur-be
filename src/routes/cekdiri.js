import { authenticate } from '../middleware/authenticate.js'
import {
  saveCekdiri,
  listCekdiri,
} from '../controllers/cekdiri.js'

export default async function cekdiriRoutes(fastify) {
  // POST /api/cekdiri
  fastify.post('/', {
    preHandler: authenticate,
    schema: {
      body: {
        type: 'object',
        required: ['feeling'],
        properties: {
          feeling: { type: 'string', minLength: 1, maxLength: 40 },
          note: { type: 'string', maxLength: 2000, nullable: true },
        },
      },
    },
  }, saveCekdiri)

  // GET /api/cekdiri?days=7
  fastify.get('/', {
    preHandler: authenticate,
    schema: {
      querystring: {
        type: 'object',
        properties: {
          days: { type: 'integer', minimum: 1, maximum: 90, default: 7 },
        },
      },
    },
  }, listCekdiri)
}
