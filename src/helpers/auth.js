import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'

// TTL constants (in seconds)
export const ACCESS_TTL_SEC = 60 * 60 * 24      // 24 hours
export const REFRESH_TTL_SEC = 60 * 60 * 24 * 30 // 30 days

const JWT_ALGORITHM = 'HS256'

function getSecret() {
  const secret = process.env.JWT_SECRET
  if (!secret) throw new Error('JWT_SECRET is not set')
  return secret
}

export function hashPassword(password) {
  return bcrypt.hashSync(password, 12)
}

export function verifyPassword(plain, hashed) {
  try {
    return bcrypt.compareSync(plain, hashed)
  } catch {
    return false
  }
}

export function createAccessToken(userId, email) {
  return jwt.sign(
    { sub: userId, email, type: 'access' },
    getSecret(),
    { algorithm: JWT_ALGORITHM, expiresIn: ACCESS_TTL_SEC }
  )
}

export function createRefreshToken(userId) {
  return jwt.sign(
    { sub: userId, type: 'refresh' },
    getSecret(),
    { algorithm: JWT_ALGORITHM, expiresIn: REFRESH_TTL_SEC }
  )
}

export function verifyToken(token) {
  return jwt.verify(token, getSecret(), { algorithms: [JWT_ALGORITHM] })
}

export function userPublic(u) {
  return {
    id: u.id,
    email: u.email,
    name: u.name ?? '',
    profileColor: u.profile_color ?? 'terracotta',
    createdAt: u.created_at instanceof Date ? u.created_at.toISOString() : u.created_at,
  }
}
