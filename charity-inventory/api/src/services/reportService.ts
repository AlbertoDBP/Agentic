import { query } from '../db/pool.js';
import { assertCenterAccess } from './centerService.js';

interface ExportRow {
  product_name: string;
  product_unit: string;
  total_quantity: number;
  barcode: string | null;
  last_updated: Date;
}

export async function exportCenterInventoryCsv(
  userId: number,
  centerId: number
): Promise<string> {
  await assertCenterAccess(userId, centerId);

  const rows = await query<ExportRow[]>(
    `SELECT p.name AS product_name,
            p.unit AS product_unit,
            SUM(e.quantity) AS total_quantity,
            MAX(pb.barcode) AS barcode,
            MAX(e.updated_at) AS last_updated
     FROM inventory_entries e
     JOIN products p ON p.id = e.product_id
     JOIN inventory_sessions s ON s.id = e.session_id
     LEFT JOIN product_barcodes pb ON pb.product_id = p.id AND pb.is_primary = 1
     WHERE e.center_id = ? AND s.status IN ('active', 'completed')
     GROUP BY p.id, p.name, p.unit
     ORDER BY p.name ASC`,
    [centerId]
  );

  const header = 'product_name,product_unit,total_quantity,barcode,last_updated';
  const lines = rows.map((row) =>
    [
      csvEscape(row.product_name),
      csvEscape(row.product_unit),
      row.total_quantity,
      csvEscape(row.barcode ?? ''),
      row.last_updated.toISOString(),
    ].join(',')
  );

  return [header, ...lines].join('\n');
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
