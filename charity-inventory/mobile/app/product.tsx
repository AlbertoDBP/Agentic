import { router } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';
import { api } from '../src/api/client';
import { Card, Field, LoadingState, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';
import { useRequireSession } from '../src/hooks/useRequireAuth';

export default function ProductScreen() {
  const { scanContext, setScanContext } = useApp();
  const { loading } = useRequireSession();
  const [name, setName] = useState(scanContext?.product?.name ?? '');
  const [description, setDescription] = useState(scanContext?.product?.description ?? '');
  const [unit, setUnit] = useState(scanContext?.product?.unit ?? 'each');
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <LoadingState />;
  }

  if (!scanContext) {
    router.replace('/scan');
    return null;
  }

  const knownProduct = Boolean(scanContext.product);

  const continueWithProduct = async () => {
    setSubmitting(true);
    try {
      let product = scanContext.product;
      if (!product) {
        if (!name.trim()) {
          Alert.alert('Product name required', 'Enter a name for this unknown product.');
          setSubmitting(false);
          return;
        }
        const created = await api.createProduct({
          name: name.trim(),
          description: description.trim() || undefined,
          unit: unit.trim() || 'each',
          barcode: scanContext.barcode,
          centerId: scanContext.centerId,
        });
        product = created.product;
      }

      setScanContext({ ...scanContext, product });
      router.push('/quantity');
    } catch {
      Alert.alert('Unable to save product', 'Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen scroll>
      <Title>{knownProduct ? 'Product Found' : 'New Product'}</Title>
      <Subtitle>Barcode: {scanContext.barcode}</Subtitle>

      {knownProduct && scanContext.product ? (
        <Card>
          <Subtitle>{scanContext.product.name}</Subtitle>
          <Subtitle>Unit: {scanContext.product.unit}</Subtitle>
          {scanContext.product.description ? (
            <Subtitle>{scanContext.product.description}</Subtitle>
          ) : null}
        </Card>
      ) : (
        <>
          <Field label="Product name" value={name} onChangeText={setName} placeholder="e.g. Canned Beans" />
          <Field label="Unit" value={unit} onChangeText={setUnit} placeholder="each, can, bag..." />
          <Field
            label="Description (optional)"
            value={description}
            onChangeText={setDescription}
            placeholder="Size, brand, notes..."
          />
        </>
      )}

      <PrimaryButton
        label={submitting ? 'Continuing...' : knownProduct ? 'Continue to Quantity' : 'Create and Continue'}
        onPress={continueWithProduct}
        disabled={submitting}
      />
      <PrimaryButton label="Scan Again" variant="secondary" onPress={() => router.back()} />
    </Screen>
  );
}
