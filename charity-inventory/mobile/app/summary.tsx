import { router } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, FlatList, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { api } from '../src/api/client';
import { PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';
import type { InventoryEntry } from '../src/types';

export default function SummaryScreen() {
  const { sessionId, selectedCenter, setSessionId, setSelectedCenter } = useApp();
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
      loadSession();
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

  return (
    <Screen>
      <Title>Session Summary</Title>
      <Subtitle>
        {selectedCenter?.name ?? 'Center'} · {entries.length} item(s)
      </Subtitle>
      {loading ? (
        <Subtitle>Loading entries...</Subtitle>
      ) : (
        <FlatList
          data={entries}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <Text style={styles.rowTitle}>{item.product_name}</Text>
              <Text style={styles.rowMeta}>
                Qty {item.quantity} {item.product_unit}
              </Text>
            </View>
          )}
          ListEmptyComponent={<Subtitle>No entries yet. Scan a product to begin.</Subtitle>}
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
});
