import type { FastifyInstance } from 'fastify';
import { authenticate } from '../middleware/auth.js';
import { getCenterForUser, listCentersForUser } from '../services/centerService.js';
import { getCenterInventory } from '../services/inventoryService.js';
import { centerIdParamSchema } from '../utils/validation.js';

export async function centerRoutes(app: FastifyInstance): Promise<void> {
  app.get('/centers', { preHandler: authenticate }, async (request, reply) => {
    const centers = await listCentersForUser(request.user!.id);
    return reply.send({ centers });
  });

  app.get('/centers/:id', { preHandler: authenticate }, async (request, reply) => {
    const { id } = centerIdParamSchema.parse(request.params);
    const center = await getCenterForUser(request.user!.id, id);
    return reply.send({ center });
  });

  app.get('/centers/:id/inventory', { preHandler: authenticate }, async (request, reply) => {
    const { id } = centerIdParamSchema.parse(request.params);
    const entries = await getCenterInventory(request.user!.id, id);
    return reply.send({ entries });
  });
}
