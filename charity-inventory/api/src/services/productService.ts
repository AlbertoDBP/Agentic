import type { ResultSetHeader } from 'mysql2';
import { query } from '../db/pool.js';
import { AppError } from '../utils/errors.js';
import { logAudit } from './auditService.js';
import type { Product, ProductBarcode, ProductWithBarcodes } from '../types/index.js';

function mapProductWithBarcodes(
  product: Product,
  barcodes: ProductBarcode[]
): ProductWithBarcodes {
  return { ...product, barcodes };
}

export async function lookupByBarcode(barcode: string): Promise<ProductWithBarcodes | null> {
  const rows = await query<Product[]>(
    `SELECT p.id, p.name, p.description, p.unit, p.created_by, p.created_at, p.updated_at
     FROM products p
     JOIN product_barcodes pb ON pb.product_id = p.id
     WHERE pb.barcode = ?
     LIMIT 1`,
    [barcode.trim()]
  );

  const product = rows[0];
  if (!product) {
    return null;
  }

  const barcodes = await query<ProductBarcode[]>(
    `SELECT id, product_id, barcode, barcode_type, is_primary
     FROM product_barcodes
     WHERE product_id = ?
     ORDER BY is_primary DESC, id ASC`,
    [product.id]
  );

  return mapProductWithBarcodes(product, barcodes);
}

export async function getProductById(productId: number): Promise<ProductWithBarcodes> {
  const rows = await query<Product[]>(
    `SELECT id, name, description, unit, created_by, created_at, updated_at
     FROM products
     WHERE id = ?
     LIMIT 1`,
    [productId]
  );

  const product = rows[0];
  if (!product) {
    throw new AppError(404, 'Product not found');
  }

  const barcodes = await query<ProductBarcode[]>(
    `SELECT id, product_id, barcode, barcode_type, is_primary
     FROM product_barcodes
     WHERE product_id = ?
     ORDER BY is_primary DESC, id ASC`,
    [productId]
  );

  return mapProductWithBarcodes(product, barcodes);
}

export async function createProduct(params: {
  name: string;
  description?: string;
  unit?: string;
  barcode?: string;
  barcodeType?: 'UPC' | 'EAN' | 'OTHER';
  createdBy: number;
  centerId?: number;
  ipAddress?: string;
}): Promise<ProductWithBarcodes> {
  const existing = params.barcode ? await lookupByBarcode(params.barcode) : null;
  if (existing) {
    return existing;
  }

  const result = await query<ResultSetHeader>(
    `INSERT INTO products (name, description, unit, created_by)
     VALUES (?, ?, ?, ?)`,
    [
      params.name.trim(),
      params.description?.trim() ?? null,
      params.unit?.trim() || 'each',
      params.createdBy,
    ]
  );

  const productId = result.insertId;

  if (params.barcode) {
    await query(
      `INSERT INTO product_barcodes (product_id, barcode, barcode_type, is_primary)
       VALUES (?, ?, ?, 1)`,
      [productId, params.barcode.trim(), params.barcodeType ?? 'UPC']
    );
  }

  await logAudit({
    userId: params.createdBy,
    action: 'product.create',
    entityType: 'product',
    entityId: productId,
    centerId: params.centerId,
    payload: { name: params.name, barcode: params.barcode },
    ipAddress: params.ipAddress,
  });

  return getProductById(productId);
}
