import { describe, expect, it } from 'vitest';
import {
  createEntrySchema,
  createProductSchema,
  createSessionSchema,
  loginSchema,
  productLookupSchema,
} from '../src/utils/validation.js';

describe('validation schemas', () => {
  it('validates login payload', () => {
    const result = loginSchema.parse({
      email: 'agent1@charity.local',
      password: 'password123',
    });
    expect(result.email).toBe('agent1@charity.local');
  });

  it('rejects invalid login email', () => {
    expect(() => loginSchema.parse({ email: 'bad', password: 'x' })).toThrow();
  });

  it('validates product lookup barcode', () => {
    const result = productLookupSchema.parse({ barcode: '041331024816' });
    expect(result.barcode).toBe('041331024816');
  });

  it('validates create product payload', () => {
    const result = createProductSchema.parse({
      name: 'New Item',
      barcode: '123456789012',
      centerId: 1,
    });
    expect(result.name).toBe('New Item');
  });

  it('validates inventory session payload', () => {
    const result = createSessionSchema.parse({ centerId: 2 });
    expect(result.centerId).toBe(2);
  });

  it('rejects non-positive inventory quantity', () => {
    expect(() =>
      createEntrySchema.parse({
        sessionId: 1,
        centerId: 1,
        productId: 1,
        quantity: 0,
      })
    ).toThrow();
  });

  it('accepts positive inventory quantity', () => {
    const result = createEntrySchema.parse({
      sessionId: 1,
      centerId: 1,
      productId: 1,
      quantity: 5,
    });
    expect(result.quantity).toBe(5);
  });
});
