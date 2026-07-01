import { query } from '../db/pool.js';

export async function logAudit(params: {
  userId?: number;
  action: string;
  entityType: string;
  entityId?: number;
  centerId?: number;
  payload?: Record<string, unknown>;
  ipAddress?: string;
}): Promise<void> {
  await query(
    `INSERT INTO audit_logs (user_id, action, entity_type, entity_id, center_id, payload, ip_address)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [
      params.userId ?? null,
      params.action,
      params.entityType,
      params.entityId ?? null,
      params.centerId ?? null,
      params.payload ? JSON.stringify(params.payload) : null,
      params.ipAddress ?? null,
    ]
  );
}
