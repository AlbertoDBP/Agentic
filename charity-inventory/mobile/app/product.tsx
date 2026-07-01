import { router } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';
import { api } from '../src/api/client';
import { Field, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';

export default function ProductScreen() {
  const { scanContext, setScanContext } = useApp();
  const [name, setName] = useState(scanContext?.product?.name ?? '');
  const [description, setDescription] = useState(scanContext?.product?.description ?? '');
  const [submitting, setSubmitting] = useState(false);

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
          barcode: scanContext.barcode,
          centerId: scanContext.centerId,
        });
        product = created.product;
      }

      setScanContext({
        ...scanContext,
        product,
      });
      router.push('/quantity');
    } catch {
      Alert.alert('Unable to save product', 'Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen>
      <Title>{knownProduct ? 'Product Found' : 'New Product'}</Title>
      <Subtitle>Barcode: {scanContext.barcode}</Subtitle>
      {knownProduct ? (
        <>
          <Subtitle>
            {scanContext.product?.name} ({scanContext.product?.unit})
          </Subtitle>
          <PrimaryButton
            label={submitting ? 'Continuing...' : 'Continue to Quantity'}
            onPress={continueWithProduct}
            disabled={submitting}
          />
        </>
      ) : (
        <>
          <Field label="Product name" value={name} onChangeText={setName} />
          <Field label="Description (optional)" value={description} onChangeText={setDescription} />
          <PrimaryButton
            label={submitting ? 'Saving...' : 'Create and Continue'}
            onPress={continueWithProduct}
            disabled={submitting}
          />
        </>
      )}
    </Screen>
  );
}
