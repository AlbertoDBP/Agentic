import type { ResultSetHeader } from 'mysql2';
import { query } from '../db/pool.js';
import { AppError } from '../utils/errors.js';
import { assertCenterAccess } from './centerService.js';
import { logAudit } from './auditService.js';
import type {
  InventoryEntry,
  InventoryEntryWithProduct,
  InventorySession,
  InventorySessionDetail,
} from '../types/index.js';

export async function createSession(params: {
  centerId: number;
  agentId: number;
  notes?: string;
  ipAddress?: string;
}): Promise<InventorySession> {
  await assertCenterAccess(params.agentId, params.centerId);

  const active = await query<InventorySession[]>(
    `SELECT id, center_id, agent_id, status, started_at, completed_at, notes
     FROM inventory_sessions
     WHERE center_id = ? AND agent_id = ? AND status = 'active'
     ORDER BY id DESC
     LIMIT 1`,
    [params.centerId, params.agentId]
  );

  if (active[0]) {
    return active[0];
  }

  const result = await query<ResultSetHeader>(
    `INSERT INTO inventory_sessions (center_id, agent_id, notes)
     VALUES (?, ?, ?)`,
    [params.centerId, params.agentId, params.notes?.trim() ?? null]
  );

  const sessionId = result.insertId;

  await logAudit({
    userId: params.agentId,
    action: 'inventory_session.create',
    entityType: 'inventory_session',
    entityId: sessionId,
    centerId: params.centerId,
    ipAddress: params.ipAddress,
  });

  return getSessionById(params.agentId, sessionId);
}

export async function getSessionById(
  userId: number,
  sessionId: number
): Promise<InventorySessionDetail> {
  const rows = await query<
    Array<InventorySession & { center_name: string; agent_name: string }>
  >(
    `SELECT s.id, s.center_id, s.agent_id, s.status, s.started_at, s.completed_at, s.notes,
            c.name AS center_name, u.full_name AS agent_name
     FROM inventory_sessions s
     JOIN centers c ON c.id = s.center_id
     JOIN users u ON u.id = s.agent_id
     WHERE s.id = ?
     LIMIT 1`,
    [sessionId]
  );

  const session = rows[0];
  if (!session) {
    throw new AppError(404, 'Inventory session not found');
  }

  await assertCenterAccess(userId, session.center_id);

  const entries = await query<InventoryEntryWithProduct[]>(
    `SELECT e.id, e.session_id, e.center_id, e.agent_id, e.product_id, e.quantity,
            e.scanned_barcode, e.created_at, e.updated_at,
            p.name AS product_name, p.unit AS product_unit
     FROM inventory_entries e
     JOIN products p ON p.id = e.product_id
     WHERE e.session_id = ?
     ORDER BY e.updated_at DESC`,
    [sessionId]
  );

  return { ...session, entries };
}

export async function addEntry(params: {
  sessionId: number;
  centerId: number;
  agentId: number;
  productId: number;
  quantity: number;
  scannedBarcode?: string;
  ipAddress?: string;
}): Promise<{ entry: InventoryEntryWithProduct; incremented: boolean }> {
  await assertCenterAccess(params.agentId, params.centerId);

  const sessions = await query<InventorySession[]>(
    `SELECT id, center_id, agent_id, status, started_at, completed_at, notes
     FROM inventory_sessions
     WHERE id = ? AND center_id = ? AND agent_id = ?
     LIMIT 1`,
    [params.sessionId, params.centerId, params.agentId]
  );

  const session = sessions[0];
  if (!session) {
    throw new AppError(404, 'Inventory session not found');
  }
  if (session.status !== 'active') {
    throw new AppError(400, 'Inventory session is not active');
  }

  const existing = await query<InventoryEntry[]>(
    `SELECT id, session_id, center_id, agent_id, product_id, quantity, scanned_barcode, created_at, updated_at
     FROM inventory_entries
     WHERE session_id = ? AND product_id = ?
     LIMIT 1`,
    [params.sessionId, params.productId]
  );

  let entryId: number;
  let incremented = false;

  if (existing[0]) {
    entryId = existing[0].id;
    incremented = true;
    const newQuantity = existing[0].quantity + params.quantity;

    await query(
      `UPDATE inventory_entries
       SET quantity = ?, scanned_barcode = COALESCE(?, scanned_barcode), updated_at = CURRENT_TIMESTAMP
       WHERE id = ?`,
      [newQuantity, params.scannedBarcode ?? null, entryId]
    );

    await query(
      `INSERT INTO inventory_adjustments (entry_id, adjusted_by, previous_quantity, new_quantity, reason)
       VALUES (?, ?, ?, ?, ?)`,
      [entryId, params.agentId, existing[0].quantity, newQuantity, 'Duplicate scan increment']
    );
  } else {
    const result = await query<ResultSetHeader>(
      `INSERT INTO inventory_entries (session_id, center_id, agent_id, product_id, quantity, scanned_barcode)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [
        params.sessionId,
        params.centerId,
        params.agentId,
        params.productId,
        params.quantity,
        params.scannedBarcode ?? null,
      ]
    );
    entryId = result.insertId;
  }

  const entries = await query<InventoryEntryWithProduct[]>(
    `SELECT e.id, e.session_id, e.center_id, e.agent_id, e.product_id, e.quantity,
            e.scanned_barcode, e.created_at, e.updated_at,
            p.name AS product_name, p.unit AS product_unit
     FROM inventory_entries e
     JOIN products p ON p.id = e.product_id
     WHERE e.id = ?
     LIMIT 1`,
    [entryId]
  );

  await logAudit({
    userId: params.agentId,
    action: incremented ? 'inventory_entry.increment' : 'inventory_entry.create',
    entityType: 'inventory_entry',
    entityId: entryId,
    centerId: params.centerId,
    payload: {
      sessionId: params.sessionId,
      productId: params.productId,
      quantity: params.quantity,
      incremented,
    },
    ipAddress: params.ipAddress,
  });

  return { entry: entries[0], incremented };
}

export async function completeSession(
  userId: number,
  sessionId: number,
  ipAddress?: string
): Promise<InventorySessionDetail> {
  const session = await getSessionById(userId, sessionId);
  if (session.status !== 'active') {
    throw new AppError(400, 'Session is already completed or cancelled');
  }

  await query(
    `UPDATE inventory_sessions
     SET status = 'completed', completed_at = CURRENT_TIMESTAMP
     WHERE id = ?`,
    [sessionId]
  );

  await logAudit({
    userId,
    action: 'inventory_session.complete',
    entityType: 'inventory_session',
    entityId: sessionId,
    centerId: session.center_id,
    ipAddress,
  });

  return getSessionById(userId, sessionId);
}

export async function getCenterInventory(
  userId: number,
  centerId: number
): Promise<InventoryEntryWithProduct[]> {
  await assertCenterAccess(userId, centerId);

  return query<InventoryEntryWithProduct[]>(
    `SELECT e.id, e.session_id, e.center_id, e.agent_id, e.product_id, e.quantity,
            e.scanned_barcode, e.created_at, e.updated_at,
            p.name AS product_name, p.unit AS product_unit
     FROM inventory_entries e
     JOIN products p ON p.id = e.product_id
     JOIN inventory_sessions s ON s.id = e.session_id
     WHERE e.center_id = ? AND s.status IN ('active', 'completed')
     ORDER BY e.updated_at DESC`,
    [centerId]
  );
}
