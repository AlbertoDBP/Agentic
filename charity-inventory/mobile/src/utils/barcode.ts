/** Normalize UPC/EAN barcode strings from camera or manual entry. */
export function normalizeBarcode(raw: string): string {
  return raw.replace(/\s+/g, '').trim();
}

/** UPC-A is 12 digits; EAN-13 is 13 digits. Allow 8–14 for field tolerance. */
export function isValidBarcode(barcode: string): boolean {
  const normalized = normalizeBarcode(barcode);
  return /^\d{8,14}$/.test(normalized);
}
