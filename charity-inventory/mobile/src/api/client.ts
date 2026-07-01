import AsyncStorage from '@react-native-async-storage/async-storage';
import type {
  AuthUser,
  Center,
  InventoryEntry,
  InventorySession,
  Product,
} from '../types';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:3000';
const TOKEN_KEY = 'charity_inventory_token';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function getToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function setToken(token: string | null): Promise<void> {
  if (token) {
    await AsyncStorage.setItem(TOKEN_KEY, token);
  } else {
    await AsyncStorage.removeItem(TOKEN_KEY);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  if (auth) {
    const token = await getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new ApiError(data.error ?? 'Request failed', response.status);
  }

  return data as T;
}

export const api = {
  login(email: string, password: string) {
    return request<{ token: string; user: AuthUser }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      },
      false
    );
  },

  logout() {
    return request<{ success: boolean }>('/auth/logout', { method: 'POST' });
  },

  me() {
    return request<{ user: AuthUser }>('/me');
  },

  centers() {
    return request<{ centers: Center[] }>('/centers');
  },

  lookupProduct(barcode: string) {
    return request<{ found: boolean; product: Product | null }>('/products/lookup', {
      method: 'POST',
      body: JSON.stringify({ barcode }),
    });
  },

  createProduct(payload: {
    name: string;
    description?: string;
    unit?: string;
    barcode?: string;
    centerId?: number;
  }) {
    return request<{ product: Product }>('/products', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  createSession(centerId: number) {
    return request<{ session: InventorySession }>('/inventory-sessions', {
      method: 'POST',
      body: JSON.stringify({ centerId }),
    });
  },

  getSession(sessionId: number) {
    return request<{ session: InventorySession }>(`/inventory-sessions/${sessionId}`);
  },

  completeSession(sessionId: number) {
    return request<{ session: InventorySession }>(
      `/inventory-sessions/${sessionId}/complete`,
      { method: 'POST' }
    );
  },

  addEntry(payload: {
    sessionId: number;
    centerId: number;
    productId: number;
    quantity: number;
    scannedBarcode?: string;
  }) {
    return request<{ entry: InventoryEntry; incremented: boolean }>('/inventory-entries', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};

export function getApiUrl(): string {
  return API_URL;
}
