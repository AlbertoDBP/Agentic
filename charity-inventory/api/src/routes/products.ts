import type { FastifyInstance } from 'fastify';
import { authenticate, getClientIp } from '../middleware/auth.js';
import {
  createProduct,
  getProductById,
  lookupByBarcode,
} from '../services/productService.js';
import {
  createProductSchema,
  productIdParamSchema,
  productLookupSchema,
} from '../utils/validation.js';

export async function productRoutes(app: FastifyInstance): Promise<void> {
  app.post('/products/lookup', { preHandler: authenticate }, async (request, reply) => {
    const body = productLookupSchema.parse(request.body);
    const product = await lookupByBarcode(body.barcode);
    return reply.send({ found: Boolean(product), product });
  });

  app.post('/products', { preHandler: authenticate }, async (request, reply) => {
    const body = createProductSchema.parse(request.body);
    const product = await createProduct({
      name: body.name,
      description: body.description,
      unit: body.unit,
      barcode: body.barcode,
      barcodeType: body.barcodeType,
      createdBy: request.user!.id,
      centerId: body.centerId,
      ipAddress: getClientIp(request),
    });
    return reply.status(201).send({ product });
  });

  app.get('/products/:id', { preHandler: authenticate }, async (request, reply) => {
    const { id } = productIdParamSchema.parse(request.params);
    const product = await getProductById(id);
    return reply.send({ product });
  });
}
