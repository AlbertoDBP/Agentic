export interface Role {
  id: number;
  name: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role_id: number;
  role_name?: string;
  is_active: number;
}

export interface Center {
  id: number;
  name: string;
  code: string;
  address: string | null;
  is_active: number;
}

export interface Product {
  id: number;
  name: string;
  description: string | null;
  unit: string;
  created_by: number | null;
  created_at: Date;
  updated_at: Date;
}

export interface ProductBarcode {
  id: number;
  product_id: number;
  barcode: string;
  barcode_type: 'UPC' | 'EAN' | 'OTHER';
  is_primary: number;
}

export interface InventorySession {
  id: number;
  center_id: number;
  agent_id: number;
  status: 'active' | 'completed' | 'cancelled';
  started_at: Date;
  completed_at: Date | null;
  notes: string | null;
}

export interface InventoryEntry {
  id: number;
  session_id: number;
  center_id: number;
  agent_id: number;
  product_id: number;
  quantity: number;
  scanned_barcode: string | null;
  created_at: Date;
  updated_at: Date;
}

export interface AppJwtPayload {
  sub: number;
  email: string;
  role: string;
}

export interface AuthUser {
  id: number;
  email: string;
  fullName: string;
  role: string;
}

export interface ProductWithBarcodes extends Product {
  barcodes: ProductBarcode[];
}

export interface InventoryEntryWithProduct extends InventoryEntry {
  product_name: string;
  product_unit: string;
}

export interface InventorySessionDetail extends InventorySession {
  center_name: string;
  agent_name: string;
  entries: InventoryEntryWithProduct[];
}
