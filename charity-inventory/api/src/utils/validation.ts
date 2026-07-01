import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export const productLookupSchema = z.object({
  barcode: z.string().min(1).max(50),
});

export const createProductSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().max(2000).optional(),
  unit: z.string().max(50).optional(),
  barcode: z.string().min(1).max(50).optional(),
  barcodeType: z.enum(['UPC', 'EAN', 'OTHER']).optional(),
  centerId: z.coerce.number().int().positive().optional(),
});

export const createSessionSchema = z.object({
  centerId: z.coerce.number().int().positive(),
  notes: z.string().max(2000).optional(),
});

export const createEntrySchema = z.object({
  sessionId: z.coerce.number().int().positive(),
  centerId: z.coerce.number().int().positive(),
  productId: z.coerce.number().int().positive(),
  quantity: z.coerce.number().int().positive(),
  scannedBarcode: z.string().max(50).optional(),
});

export const centerIdParamSchema = z.object({
  id: z.coerce.number().int().positive(),
});

export const sessionIdParamSchema = z.object({
  id: z.coerce.number().int().positive(),
});

export const productIdParamSchema = z.object({
  id: z.coerce.number().int().positive(),
});

export const exportQuerySchema = z.object({
  centerId: z.coerce.number().int().positive(),
});
