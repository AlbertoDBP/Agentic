import { router } from 'expo-router';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useCallback, useRef, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { api } from '../src/api/client';
import { PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';

export default function ScanScreen() {
  const { selectedCenter, sessionId, setScanContext } = useApp();
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(true);
  const processingRef = useRef(false);

  const handleBarcode = useCallback(
    async (barcode: string) => {
      if (!scanning || processingRef.current || !selectedCenter || !sessionId) {
        return;
      }

      processingRef.current = true;
      setScanning(false);

      try {
        const lookup = await api.lookupProduct(barcode);
        setScanContext({
          barcode,
          product: lookup.product,
          centerId: selectedCenter.id,
          sessionId,
        });
        router.push('/product');
      } catch {
        Alert.alert('Lookup failed', 'Could not look up this barcode.');
        setScanning(true);
      } finally {
        processingRef.current = false;
      }
    },
    [scanning, selectedCenter, sessionId, setScanContext]
  );

  if (!permission) {
    return <Screen><Title>Requesting camera permission...</Title></Screen>;
  }

  if (!permission.granted) {
    return (
      <Screen>
        <Title>Camera permission required</Title>
        <Subtitle>Barcode scanning needs camera access on your iPhone.</Subtitle>
        <PrimaryButton label="Grant Camera Access" onPress={requestPermission} />
      </Screen>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={styles.camera}
        facing="back"
        barcodeScannerSettings={{
          barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128'],
        }}
        onBarcodeScanned={({ data }) => {
          if (data) {
            handleBarcode(data);
          }
        }}
      />
      <View style={styles.overlay}>
        <Text style={styles.overlayTitle}>Point camera at UPC barcode</Text>
        <Text style={styles.overlayMeta}>
          Center: {selectedCenter?.name ?? 'Unknown'}
        </Text>
        <PrimaryButton
          label="View Session Summary"
          onPress={() => router.push('/summary')}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  camera: {
    flex: 1,
  },
  overlay: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    padding: 20,
    gap: 12,
    backgroundColor: 'rgba(15, 23, 42, 0.75)',
  },
  overlayTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  overlayMeta: {
    color: '#cbd5e1',
    fontSize: 14,
  },
});
