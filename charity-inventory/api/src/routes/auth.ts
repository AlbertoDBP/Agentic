import type { FastifyInstance } from 'fastify';
import { authenticate, getClientIp } from '../middleware/auth.js';
import { login, logout, getMe } from '../services/authService.js';
import { loginSchema } from '../utils/validation.js';

export async function authRoutes(app: FastifyInstance): Promise<void> {
  app.post('/auth/login', async (request, reply) => {
    const body = loginSchema.parse(request.body);
    const result = await login(body.email, body.password, getClientIp(request));
    return reply.send(result);
  });

  app.post('/auth/logout', { preHandler: authenticate }, async (request, reply) => {
    await logout(request.user!.id, getClientIp(request));
    return reply.send({ success: true });
  });

  app.get('/me', { preHandler: authenticate }, async (request, reply) => {
    const user = await getMe(request.user!.id);
    return reply.send({ user });
  });
}
