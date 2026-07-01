import type { FastifyInstance } from 'fastify';
import { authenticate, getClientIp } from '../middleware/auth.js';
import {
  addEntry,
  completeSession,
  createSession,
  getSessionById,
} from '../services/inventoryService.js';
import {
  createEntrySchema,
  createSessionSchema,
  sessionIdParamSchema,
} from '../utils/validation.js';

export async function inventoryRoutes(app: FastifyInstance): Promise<void> {
  app.post('/inventory-sessions', { preHandler: authenticate }, async (request, reply) => {
    const body = createSessionSchema.parse(request.body);
    const session = await createSession({
      centerId: body.centerId,
      agentId: request.user!.id,
      notes: body.notes,
      ipAddress: getClientIp(request),
    });
    return reply.status(201).send({ session });
  });

  app.get('/inventory-sessions/:id', { preHandler: authenticate }, async (request, reply) => {
    const { id } = sessionIdParamSchema.parse(request.params);
    const session = await getSessionById(request.user!.id, id);
    return reply.send({ session });
  });

  app.post(
    '/inventory-sessions/:id/complete',
    { preHandler: authenticate },
    async (request, reply) => {
      const { id } = sessionIdParamSchema.parse(request.params);
      const session = await completeSession(request.user!.id, id, getClientIp(request));
      return reply.send({ session });
    }
  );

  app.post('/inventory-entries', { preHandler: authenticate }, async (request, reply) => {
    const body = createEntrySchema.parse(request.body);
    const result = await addEntry({
      sessionId: body.sessionId,
      centerId: body.centerId,
      agentId: request.user!.id,
      productId: body.productId,
      quantity: body.quantity,
      scannedBarcode: body.scannedBarcode,
      ipAddress: getClientIp(request),
    });
    return reply.status(result.incremented ? 200 : 201).send(result);
  });
}
