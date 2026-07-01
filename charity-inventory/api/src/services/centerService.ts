import { query } from '../db/pool.js';
import { AppError } from '../utils/errors.js';
import type { Center } from '../types/index.js';

export async function listCentersForUser(userId: number): Promise<Center[]> {
  return query<Center[]>(
    `SELECT c.id, c.name, c.code, c.address, c.is_active
     FROM centers c
     JOIN center_users cu ON cu.center_id = c.id
     WHERE cu.user_id = ? AND c.is_active = 1
     ORDER BY c.name ASC`,
    [userId]
  );
}

export async function getCenterForUser(userId: number, centerId: number): Promise<Center> {
  const rows = await query<Center[]>(
    `SELECT c.id, c.name, c.code, c.address, c.is_active
     FROM centers c
     JOIN center_users cu ON cu.center_id = c.id
     WHERE cu.user_id = ? AND c.id = ? AND c.is_active = 1
     LIMIT 1`,
    [userId, centerId]
  );

  const center = rows[0];
  if (!center) {
    throw new AppError(403, 'You do not have access to this center');
  }

  return center;
}

export async function assertCenterAccess(userId: number, centerId: number): Promise<void> {
  await getCenterForUser(userId, centerId);
}
