import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { config } from '../config.js';
import { AppError } from '../utils/errors.js';
import { getUserByEmail, getUserById } from './userService.js';
import { logAudit } from './auditService.js';
import type { AuthUser, AppJwtPayload } from '../types/index.js';

export async function login(
  email: string,
  password: string,
  ipAddress?: string
): Promise<{ token: string; user: AuthUser }> {
  const user = await getUserByEmail(email.toLowerCase().trim());
  if (!user || !user.is_active) {
    throw new AppError(401, 'Invalid email or password');
  }

  const valid = await bcrypt.compare(password, user.password_hash);
  if (!valid) {
    throw new AppError(401, 'Invalid email or password');
  }

  const authUser: AuthUser = {
    id: user.id,
    email: user.email,
    fullName: user.full_name,
    role: user.role_name ?? 'agent',
  };

  const payload: AppJwtPayload = {
    sub: authUser.id,
    email: authUser.email,
    role: authUser.role,
  };

  const token = jwt.sign(payload, config.JWT_SECRET, {
    expiresIn: config.JWT_EXPIRES_IN as jwt.SignOptions['expiresIn'],
  });

  await logAudit({
    userId: authUser.id,
    action: 'auth.login',
    entityType: 'user',
    entityId: authUser.id,
    ipAddress,
  });

  return { token, user: authUser };
}

export async function logout(userId: number, ipAddress?: string): Promise<void> {
  await logAudit({
    userId,
    action: 'auth.logout',
    entityType: 'user',
    entityId: userId,
    ipAddress,
  });
}

export function verifyToken(token: string): AppJwtPayload {
  try {
    const decoded = jwt.verify(token, config.JWT_SECRET);
    if (typeof decoded === 'string') {
      throw new AppError(401, 'Invalid token');
    }
    return decoded as unknown as AppJwtPayload;
  } catch (error) {
    if (error instanceof AppError) {
      throw error;
    }
    throw new AppError(401, 'Invalid or expired token');
  }
}

export async function getMe(userId: number): Promise<AuthUser> {
  const user = await getUserById(userId);
  if (!user) {
    throw new AppError(401, 'User not found or inactive');
  }
  return user;
}
