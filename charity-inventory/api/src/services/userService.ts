import { query } from '../db/pool.js';
import type { AuthUser, User } from '../types/index.js';

export async function getUserByEmail(email: string): Promise<(User & { password_hash: string }) | null> {
  const rows = await query<Array<User & { password_hash: string }>>(
    `SELECT u.id, u.email, u.password_hash, u.full_name, u.role_id, u.is_active, r.name AS role_name
     FROM users u
     JOIN roles r ON r.id = u.role_id
     WHERE u.email = ?
     LIMIT 1`,
    [email]
  );
  return rows[0] ?? null;
}

export async function getUserById(id: number): Promise<AuthUser | null> {
  const rows = await query<User[]>(
    `SELECT u.id, u.email, u.full_name, u.role_id, u.is_active, r.name AS role_name
     FROM users u
     JOIN roles r ON r.id = u.role_id
     WHERE u.id = ?
     LIMIT 1`,
    [id]
  );
  const user = rows[0];
  if (!user || !user.is_active) {
    return null;
  }
  return {
    id: user.id,
    email: user.email,
    fullName: user.full_name,
    role: user.role_name ?? 'agent',
  };
}
