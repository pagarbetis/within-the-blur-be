import { authenticate } from '../middleware/authenticate.js'
import {
  register,
  login,
  logout,
  me,
  refresh,
} from '../controllers/auth.js'

export default async function authRoutes(fastify) {
  // POST /api/auth/register
  fastify.post('/register', {
    schema: {
      body: {
        type: 'object',
        required: ['email', 'password', 'name'],
        properties: {
          email: { type: 'string', format: 'email' },
          password: { type: 'string', minLength: 6, maxLength: 128 },
          name: { type: 'string', minLength: 1, maxLength: 60 },
        },
      },
    },
  }, register)

  // POST /api/auth/login
  fastify.post('/login', {
    schema: {
      body: {
        type: 'object',
        required: ['email', 'password'],
        properties: {
          email: { type: 'string', format: 'email' },
          password: { type: 'string' },
        },
      },
    },
  }, login)

  // POST /api/auth/logout  (auth required)
  fastify.post('/logout', { preHandler: authenticate }, logout)

  // GET /api/auth/me  (auth required)
  fastify.get('/me', { preHandler: authenticate }, me)

  // POST /api/auth/refresh
  fastify.post('/refresh', refresh)
}
