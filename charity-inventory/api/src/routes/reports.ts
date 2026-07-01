import type { FastifyInstance } from 'fastify';
import { authenticate } from '../middleware/auth.js';
import { exportCenterInventoryCsv } from '../services/reportService.js';
import { exportQuerySchema } from '../utils/validation.js';

export async function reportRoutes(app: FastifyInstance): Promise<void> {
  app.get('/reports/export', { preHandler: authenticate }, async (request, reply) => {
    const { centerId } = exportQuerySchema.parse(request.query);
    const csv = await exportCenterInventoryCsv(request.user!.id, centerId);
    reply.header('Content-Type', 'text/csv; charset=utf-8');
    reply.header('Content-Disposition', `attachment; filename="center-${centerId}-inventory.csv"`);
    return reply.send(csv);
  });
}
