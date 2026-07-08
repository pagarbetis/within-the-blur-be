import dotenv from 'dotenv'
import dotenvExpand from 'dotenv-expand'

const myEnv = dotenv.config()
dotenvExpand.expand(myEnv)

import Fastify from 'fastify'
import fastifyCookie from '@fastify/cookie'
import fastifyCors from '@fastify/cors'

import prisma from './db.js'
import authRoutes from './routes/auth.js'
import profileRoutes from './routes/profile.js'
import journalRoutes from './routes/journal.js'
import kuisRoutes from './routes/kuis.js'
import cekdiriRoutes from './routes/cekdiri.js'
import statsRoutes from './routes/stats.js'

const PORT = parseInt(process.env.PORT ?? '8000', 10)
const HOST = '0.0.0.0' // required for Railway

const fastify = Fastify({
  logger: {
    level: process.env.NODE_ENV === 'production' ? 'warn' : 'info',
    transport:
      process.env.NODE_ENV !== 'production'
        ? { target: 'pino-pretty', options: { colorize: true } }
        : undefined,
  },
})

// ---- Plugins ----
await fastify.register(fastifyCors, {
  origin: process.env.FRONTEND_URL ?? 'http://localhost:3000',
  credentials: true,
  methods: ['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
})

await fastify.register(fastifyCookie)

// ---- Routes ----
// Health check
fastify.get('/api/', async () => ({ message: 'Within the Blur API' }))

// Feature routes — each plugin gets its own prefix
await fastify.register(authRoutes, { prefix: '/api/auth' })
await fastify.register(profileRoutes, { prefix: '/api/profile' })
await fastify.register(journalRoutes, { prefix: '/api/journal' })
await fastify.register(kuisRoutes, { prefix: '/api/kuis' })
await fastify.register(cekdiriRoutes, { prefix: '/api/cekdiri' })
await fastify.register(statsRoutes, { prefix: '/api/stats' })

// ---- Lifecycle ----
const start = async () => {
  try {
    // Verify DB connection on startup
    await prisma.$connect()
    fastify.log.info('Database connected.')

    await fastify.listen({ port: PORT, host: HOST })
    fastify.log.info(`Server running on http://${HOST}:${PORT}`)
  } catch (err) {
    fastify.log.error(err)
    process.exit(1)
  }
}

const gracefulShutdown = async (signal) => {
  fastify.log.info(`${signal} received. Shutting down...`)
  await fastify.close()
  await prisma.$disconnect()
  process.exit(0)
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'))
process.on('SIGINT', () => gracefulShutdown('SIGINT'))

start()
