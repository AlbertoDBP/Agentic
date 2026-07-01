import { router } from 'expo-router';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useRef, useState } from 'react';
import { Alert, Modal, StyleSheet, Text, View } from 'react-native';
import { api } from '../src/api/client';
import { Field, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';
import { useRequireSession } from '../src/hooks/useRequireAuth';
import { isValidBarcode, normalizeBarcode } from '../src/utils/barcode';

const SCAN_COOLDOWN_MS = 1500;

export default function ScanScreen() {
  const { selectedCenter, sessionId, setScanContext } = useApp();
  const { loading } = useRequireSession();
  const [permission, requestPermission] = useCameraPermissions();
  const [scanningEnabled, setScanningEnabled] = useState(true);
  const [manualVisible, setManualVisible] = useState(false);
  const [manualBarcode, setManualBarcode] = useState('');
  const lastScanRef = useRef(0);
  const processingRef = useRef(false);

  useFocusEffect(
    useCallback(() => {
      setScanningEnabled(true);
      processingRef.current = false;
    }, [])
  );

  const processBarcode = useCallback(
    async (rawBarcode: string) => {
      const barcode = normalizeBarcode(rawBarcode);
      if (!barcode || !selectedCenter || !sessionId) {
        return;
      }

      if (!isValidBarcode(barcode)) {
        Alert.alert('Invalid barcode', 'Enter an 8–14 digit UPC/EAN code.');
        return;
      }

      processingRef.current = true;
      setScanningEnabled(false);
      setManualVisible(false);

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
        Alert.alert('Lookup failed', 'Could not look up this barcode. Check your connection.');
        setScanningEnabled(true);
      } finally {
        processingRef.current = false;
      }
    },
    [selectedCenter, sessionId, setScanContext]
  );

  const handleBarcodeScanned = useCallback(
    ({ data }: { data: string }) => {
      if (!scanningEnabled || processingRef.current) {
        return;
      }

      const now = Date.now();
      if (now - lastScanRef.current < SCAN_COOLDOWN_MS) {
        return;
      }
      lastScanRef.current = now;

      void processBarcode(data);
    },
    [scanningEnabled, processBarcode]
  );

  if (loading) {
    return <Screen><Title>Loading...</Title></Screen>;
  }

  if (!permission) {
    return <Screen><Title>Requesting camera permission...</Title></Screen>;
  }

  if (!permission.granted) {
    return (
      <Screen>
        <Title>Camera permission required</Title>
        <Subtitle>Barcode scanning needs camera access on your iPhone.</Subtitle>
        <PrimaryButton label="Grant Camera Access" onPress={requestPermission} />
        <PrimaryButton
          label="Enter Barcode Manually"
          variant="secondary"
          onPress={() => setManualVisible(true)}
        />
        <ManualEntryModal
          visible={manualVisible}
          barcode={manualBarcode}
          onChangeBarcode={setManualBarcode}
          onClose={() => setManualVisible(false)}
          onSubmit={() => void processBarcode(manualBarcode)}
        />
      </Screen>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={styles.camera}
        facing="back"
        barcodeScannerSettings={{
          barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'],
        }}
        onBarcodeScanned={scanningEnabled ? handleBarcodeScanned : undefined}
      />
      <View style={styles.overlay}>
        <View style={styles.reticle} />
        <Text style={styles.overlayTitle}>Align UPC barcode in frame</Text>
        <Text style={styles.overlayMeta}>Center: {selectedCenter?.name ?? 'Unknown'}</Text>
        <Text style={styles.overlayHint}>
          {scanningEnabled ? 'Ready to scan' : 'Processing...'}
        </Text>
        <PrimaryButton
          label="Enter Barcode Manually"
          variant="secondary"
          onPress={() => setManualVisible(true)}
        />
        <PrimaryButton label="Session Summary" onPress={() => router.push('/summary')} />
        <PrimaryButton
          label="Change Center"
          variant="secondary"
          onPress={() => router.replace('/centers')}
        />
      </View>
      <ManualEntryModal
        visible={manualVisible}
        barcode={manualBarcode}
        onChangeBarcode={setManualBarcode}
        onClose={() => setManualVisible(false)}
        onSubmit={() => void processBarcode(manualBarcode)}
      />
    </View>
  );
}

function ManualEntryModal({
  visible,
  barcode,
  onChangeBarcode,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  barcode: string;
  onChangeBarcode: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <Title>Manual Barcode Entry</Title>
          <Subtitle>Use when the label is damaged or the camera cannot read it.</Subtitle>
          <Field
            label="UPC / EAN"
            value={barcode}
            onChangeText={onChangeBarcode}
            keyboardType="number-pad"
            placeholder="e.g. 041331024816"
            autoFocus
          />
          <PrimaryButton label="Look Up Product" onPress={onSubmit} />
          <PrimaryButton label="Cancel" variant="secondary" onPress={onClose} />
        </View>
      </View>
    </Modal>
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
    gap: 10,
    backgroundColor: 'rgba(15, 23, 42, 0.82)',
  },
  reticle: {
    position: 'absolute',
    top: -220,
    alignSelf: 'center',
    width: 260,
    height: 120,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.8)',
    borderRadius: 8,
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
  overlayHint: {
    color: '#93c5fd',
    fontSize: 13,
    marginBottom: 4,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(15,23,42,0.5)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: '#f8fafc',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 20,
    gap: 14,
  },
});
