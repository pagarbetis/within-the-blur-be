import prisma from '../db.js'
import {
  hashPassword,
  verifyPassword,
  createAccessToken,
  createRefreshToken,
  verifyToken,
  userPublic,
  ACCESS_TTL_SEC,
} from '../helpers/auth.js'
import { setAuthCookies, clearAuthCookies } from '../helpers/cookies.js'

export async function register(request, reply) {
  const { email: rawEmail, password, name } = request.body
  const email = rawEmail.toLowerCase().trim()

  const existing = await prisma.user.findUnique({ where: { email } })
  if (existing) {
    return reply.code(400).send({ error: 'Email sudah terdaftar. Coba login.' })
  }

  const user = await prisma.user.create({
    data: {
      email,
      name: name.trim(),
      password_hash: hashPassword(password),
      profile_color: 'terracotta',
    },
  })

  const access = createAccessToken(user.id, email)
  const refresh = createRefreshToken(user.id)
  setAuthCookies(reply, access, refresh)

  return reply.code(201).send({ user: userPublic(user), access_token: access })
}

export async function login(request, reply) {
  const { email: rawEmail, password } = request.body
  const email = rawEmail.toLowerCase().trim()
  const ip = request.ip ?? '0.0.0.0'
  const identifier = `${ip}:${email}`
  const now = new Date()

  const lock = await prisma.loginAttempt.findUnique({ where: { identifier } })
  if (lock?.locked_until && lock.locked_until > now) {
    return reply.code(429).send({ error: 'Terlalu banyak percobaan. Coba lagi dalam 15 menit.' })
  }

  const user = await prisma.user.findUnique({ where: { email } })
  const valid = user && verifyPassword(password, user.password_hash)

  if (!valid) {
    const attempts = (lock?.attempts ?? 0) + 1
    const lockedUntil = attempts >= 5 ? new Date(now.getTime() + 15 * 60 * 1000) : null

    await prisma.loginAttempt.upsert({
      where: { identifier },
      create: {
        identifier,
        attempts: lockedUntil ? 0 : attempts,
        last_attempt: now,
        locked_until: lockedUntil,
      },
      update: {
        attempts: lockedUntil ? 0 : attempts,
        last_attempt: now,
        locked_until: lockedUntil,
      },
    })

    return reply.code(401).send({ error: 'Email atau password salah.' })
  }

  if (lock) {
    await prisma.loginAttempt.delete({ where: { identifier } })
  }

  const access = createAccessToken(user.id, email)
  const refresh = createRefreshToken(user.id)
  setAuthCookies(reply, access, refresh)

  return reply.send({ user: userPublic(user), access_token: access })
}

export async function logout(request, reply) {
  clearAuthCookies(reply)
  return reply.send({ ok: true })
}

export async function me(request, reply) {
  return reply.send({ user: userPublic(request.user) })
}

export async function refresh(request, reply) {
  const token = request.cookies?.refresh_token
  if (!token) {
    return reply.code(401).send({ error: 'No refresh token' })
  }

  let payload
  try {
    payload = verifyToken(token)
  } catch (err) {
    const msg = err.name === 'TokenExpiredError' ? 'Refresh token expired' : 'Invalid refresh token'
    return reply.code(401).send({ error: msg })
  }

  if (payload.type !== 'refresh') {
    return reply.code(401).send({ error: 'Invalid token type' })
  }

  const user = await prisma.user.findUnique({ where: { id: payload.sub } })
  if (!user) {
    return reply.code(401).send({ error: 'User not found' })
  }

  const access = createAccessToken(user.id, user.email)
  const SECURE = process.env.NODE_ENV === 'production'
  reply.setCookie('access_token', access, {
    httpOnly: true,
    secure: SECURE,
    sameSite: 'lax',
    maxAge: ACCESS_TTL_SEC,
    path: '/',
  })

  return reply.send({ user: userPublic(user), access_token: access })
}
