import type { FastifyReply, FastifyRequest } from 'fastify';
import { verifyToken } from '../services/authService.js';
import { getUserById } from '../services/userService.js';
import { AppError } from '../utils/errors.js';
import type { AuthUser } from '../types/index.js';

declare module 'fastify' {
  interface FastifyRequest {
    user?: AuthUser;
  }
}

export async function authenticate(
  request: FastifyRequest,
  _reply: FastifyReply
): Promise<void> {
  const header = request.headers.authorization;
  if (!header?.startsWith('Bearer ')) {
    throw new AppError(401, 'Missing or invalid authorization header');
  }

  const token = header.slice('Bearer '.length);
  const payload = verifyToken(token);
  const user = await getUserById(payload.sub);

  if (!user) {
    throw new AppError(401, 'User not found or inactive');
  }

  request.user = user;
}

export function getClientIp(request: FastifyRequest): string | undefined {
  const forwarded = request.headers['x-forwarded-for'];
  if (typeof forwarded === 'string') {
    return forwarded.split(',')[0]?.trim();
  }
  return request.ip;
}
