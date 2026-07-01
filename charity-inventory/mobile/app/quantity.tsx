import { router } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';
import { api } from '../src/api/client';
import { Field, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';

export default function QuantityScreen() {
  const { scanContext, setScanContext } = useApp();
  const [quantity, setQuantity] = useState('1');
  const [submitting, setSubmitting] = useState(false);

  if (!scanContext?.product) {
    router.replace('/scan');
    return null;
  }

  const product = scanContext.product;

  const saveEntry = async () => {
    const parsed = Number.parseInt(quantity, 10);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      Alert.alert('Invalid quantity', 'Enter a positive whole number.');
      return;
    }

    setSubmitting(true);
    try {
      const result = await api.addEntry({
        sessionId: scanContext.sessionId,
        centerId: scanContext.centerId,
        productId: product.id,
        quantity: parsed,
        scannedBarcode: scanContext.barcode,
      });

      Alert.alert(
        result.incremented ? 'Quantity updated' : 'Entry saved',
        `${product.name}: ${result.entry.quantity} total in session`
      );
      setScanContext(null);
      router.replace('/scan');
    } catch {
      Alert.alert('Save failed', 'Could not save inventory entry.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen>
      <Title>Enter Quantity</Title>
      <Subtitle>
        {product.name} ({product.unit})
      </Subtitle>
      <Field
        label="Quantity"
        value={quantity}
        onChangeText={setQuantity}
        keyboardType="number-pad"
      />
      <PrimaryButton
        label={submitting ? 'Saving...' : 'Save Entry'}
        onPress={saveEntry}
        disabled={submitting}
      />
    </Screen>
  );
}
