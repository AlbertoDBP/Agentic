import { router } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, FlatList, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { api } from '../src/api/client';
import { LoadingState, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';
import { useRequireSession } from '../src/hooks/useRequireAuth';
import type { InventoryEntry } from '../src/types';

export default function SummaryScreen() {
  const { sessionId, selectedCenter, setSessionId, setSelectedCenter } = useApp();
  const { loading: authLoading } = useRequireSession();
  const [entries, setEntries] = useState<InventoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);

  const loadSession = async () => {
    if (!sessionId) {
      return;
    }
    setLoading(true);
    try {
      const result = await api.getSession(sessionId);
      setEntries(result.session.entries ?? []);
    } catch {
      Alert.alert('Unable to load session');
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      void loadSession();
    }, [sessionId])
  );

  const completeSession = async () => {
    if (!sessionId) {
      return;
    }
    setCompleting(true);
    try {
      await api.completeSession(sessionId);
      setSessionId(null);
      setSelectedCenter(null);
      router.replace('/centers');
    } catch {
      Alert.alert('Unable to complete session');
    } finally {
      setCompleting(false);
    }
  };

  const totalUnits = entries.reduce((sum, entry) => sum + entry.quantity, 0);

  if (authLoading) {
    return <LoadingState />;
  }

  return (
    <Screen>
      <Title>Session Summary</Title>
      <Subtitle>
        {selectedCenter?.name ?? 'Center'} · {entries.length} product(s) · {totalUnits} unit(s)
      </Subtitle>
      {loading ? (
        <Subtitle>Loading entries...</Subtitle>
      ) : (
        <FlatList
          data={entries}
          keyExtractor={(item) => String(item.id)}
          style={styles.list}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <Text style={styles.rowTitle}>{item.product_name}</Text>
              <Text style={styles.rowMeta}>
                Qty {item.quantity} {item.product_unit}
              </Text>
              {item.scanned_barcode ? (
                <Text style={styles.rowBarcode}>UPC {item.scanned_barcode}</Text>
              ) : null}
            </View>
          )}
          ListEmptyComponent={
            <Subtitle>No entries yet. Scan a product to begin.</Subtitle>
          }
        />
      )}
      <PrimaryButton label="Continue Scanning" onPress={() => router.push('/scan')} />
      <PrimaryButton
        label={completing ? 'Completing...' : 'Complete Session'}
        onPress={completeSession}
        disabled={completing}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    flex: 1,
  },
  listContent: {
    gap: 10,
    paddingBottom: 8,
  },
  row: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  rowTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#0f172a',
  },
  rowMeta: {
    fontSize: 14,
    color: '#64748b',
    marginTop: 4,
  },
  rowBarcode: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 4,
  },
});
