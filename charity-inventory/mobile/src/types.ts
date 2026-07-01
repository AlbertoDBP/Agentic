export interface AuthUser {
  id: number;
  email: string;
  fullName: string;
  role: string;
}

export interface Center {
  id: number;
  name: string;
  code: string;
  address: string | null;
  is_active: number;
}

export interface ProductBarcode {
  id: number;
  product_id: number;
  barcode: string;
  barcode_type: string;
  is_primary: number;
}

export interface Product {
  id: number;
  name: string;
  description: string | null;
  unit: string;
  barcodes?: ProductBarcode[];
}

export interface InventorySession {
  id: number;
  center_id: number;
  agent_id: number;
  status: string;
  started_at: string;
  completed_at: string | null;
  notes: string | null;
  center_name?: string;
  agent_name?: string;
  entries?: InventoryEntry[];
}

export interface InventoryEntry {
  id: number;
  session_id: number;
  center_id: number;
  agent_id: number;
  product_id: number;
  quantity: number;
  scanned_barcode: string | null;
  product_name?: string;
  product_unit?: string;
}

export interface ScanContext {
  barcode: string;
  product: Product | null;
  centerId: number;
  sessionId: number;
}
