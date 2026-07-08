import { ACCESS_TTL_SEC, REFRESH_TTL_SEC } from './auth.js'

const SECURE = process.env.NODE_ENV === 'production'

export function setAuthCookies(reply, access, refresh) {
  reply
    .setCookie('access_token', access, {
      httpOnly: true,
      secure: SECURE,
      sameSite: 'lax',
      maxAge: ACCESS_TTL_SEC,
      path: '/',
    })
    .setCookie('refresh_token', refresh, {
      httpOnly: true,
      secure: SECURE,
      sameSite: 'lax',
      maxAge: REFRESH_TTL_SEC,
      path: '/',
    })
}

export function clearAuthCookies(reply) {
  reply
    .clearCookie('access_token', { path: '/' })
    .clearCookie('refresh_token', { path: '/' })
}
