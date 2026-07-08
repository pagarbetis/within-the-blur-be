import { authenticate } from '../middleware/authenticate.js'
import {
  createJournal,
  listJournal,
  deleteJournal,
} from '../controllers/journal.js'

export default async function journalRoutes(fastify) {
  // POST /api/journal
  fastify.post('/', {
    preHandler: authenticate,
    schema: {
      body: {
        type: 'object',
        required: ['body'],
        properties: {
          body: { type: 'string', minLength: 1, maxLength: 5000 },
          title: { type: 'string', maxLength: 120, nullable: true },
          mood: { type: 'string', maxLength: 40, nullable: true },
          unlockAt: { type: 'string', nullable: true },
        },
      },
    },
  }, createJournal)

  // GET /api/journal
  fastify.get('/', { preHandler: authenticate }, listJournal)

  // DELETE /api/journal/:entryId
  fastify.delete('/:entryId', { preHandler: authenticate }, deleteJournal)
}
