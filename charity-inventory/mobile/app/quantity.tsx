import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, View } from 'react-native';
import { api } from '../src/api/client';
import { Field, LoadingState, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';
import { useRequireSession } from '../src/hooks/useRequireAuth';

const QUICK_QUANTITIES = [1, 2, 5, 10, 24];

export default function QuantityScreen() {
  const { scanContext, setScanContext } = useApp();
  const { loading } = useRequireSession();
  const [quantity, setQuantity] = useState('1');
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <LoadingState />;
  }

  if (!scanContext?.product) {
    router.replace('/scan');
    return null;
  }

  const product = scanContext.product;

  const saveEntry = async (qty: number) => {
    if (!Number.isInteger(qty) || qty <= 0) {
      Alert.alert('Invalid quantity', 'Enter a positive whole number.');
      return;
    }

    setSubmitting(true);
    try {
      const result = await api.addEntry({
        sessionId: scanContext.sessionId,
        centerId: scanContext.centerId,
        productId: product.id,
        quantity: qty,
        scannedBarcode: scanContext.barcode,
      });

      Alert.alert(
        result.incremented ? 'Quantity updated' : 'Entry saved',
        `${product.name}: ${result.entry.quantity} total in this session`,
        [{ text: 'Scan Next', onPress: () => {
          setScanContext(null);
          router.replace('/scan');
        }}]
      );
    } catch {
      Alert.alert('Save failed', 'Could not save inventory entry.');
    } finally {
      setSubmitting(false);
    }
  };

  const onSave = () => {
    const parsed = Number.parseInt(quantity, 10);
    void saveEntry(parsed);
  };

  return (
    <Screen scroll>
      <Title>Enter Quantity</Title>
      <Subtitle>
        {product.name} ({product.unit})
      </Subtitle>
      <Field
        label="Quantity"
        value={quantity}
        onChangeText={setQuantity}
        keyboardType="number-pad"
        autoFocus
      />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {QUICK_QUANTITIES.map((value) => (
          <PrimaryButton
            key={value}
            label={String(value)}
            variant="secondary"
            onPress={() => setQuantity(String(value))}
          />
        ))}
      </View>
      <PrimaryButton
        label={submitting ? 'Saving...' : 'Save Entry'}
        onPress={onSave}
        disabled={submitting}
      />
    </Screen>
  );
}
