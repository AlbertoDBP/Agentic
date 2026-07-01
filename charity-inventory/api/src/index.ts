import Fastify from 'fastify';
import cors from '@fastify/cors';
import { config, getCorsOrigins } from './config.js';
import { pool } from './db/pool.js';
import { authRoutes } from './routes/auth.js';
import { centerRoutes } from './routes/centers.js';
import { productRoutes } from './routes/products.js';
import { inventoryRoutes } from './routes/inventory.js';
import { reportRoutes } from './routes/reports.js';
import { AppError, isAppError } from './utils/errors.js';
import { ZodError } from 'zod';

const app = Fastify({
  logger: config.NODE_ENV !== 'test',
});

await app.register(cors, {
  origin: getCorsOrigins(),
});

app.get('/health', async () => ({ status: 'ok' }));

await app.register(authRoutes);
await app.register(centerRoutes);
await app.register(productRoutes);
await app.register(inventoryRoutes);
await app.register(reportRoutes);

app.setErrorHandler((error, _request, reply) => {
  if (error instanceof ZodError) {
    return reply.status(400).send({
      error: 'Validation failed',
      details: error.flatten(),
    });
  }

  if (isAppError(error)) {
    return reply.status(error.statusCode).send({
      error: error.message,
      code: error.code,
    });
  }

  app.log.error(error);
  return reply.status(500).send({ error: 'Internal server error' });
});

async function start(): Promise<void> {
  try {
    await pool.query('SELECT 1');
    await app.listen({ port: config.PORT, host: config.HOST });
    console.log(`API listening on http://${config.HOST}:${config.PORT}`);
  } catch (error) {
    app.log.error(error);
    process.exit(1);
  }
}

start();

export { app };
