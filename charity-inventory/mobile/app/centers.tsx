import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { api } from '../src/api/client';
import { PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';
import type { Center } from '../src/types';

export default function CentersScreen() {
  const { centers, logout, setSelectedCenter, setSessionId } = useApp();
  const [loadingCenterId, setLoadingCenterId] = useState<number | null>(null);

  const startCenter = async (center: Center) => {
    setLoadingCenterId(center.id);
    try {
      const session = await api.createSession(center.id);
      setSelectedCenter(center);
      setSessionId(session.session.id);
      router.push('/scan');
    } catch (error) {
      Alert.alert('Unable to start session', 'Please try again.');
    } finally {
      setLoadingCenterId(null);
    }
  };

  const onLogout = async () => {
    await logout();
    router.replace('/login');
  };

  return (
    <Screen>
      <Title>Select Center</Title>
      <Subtitle>Choose the charity center where you are collecting inventory.</Subtitle>
      <View style={styles.list}>
        {centers.map((center) => (
          <Pressable
            key={center.id}
            style={styles.card}
            onPress={() => startCenter(center)}
            disabled={loadingCenterId === center.id}
          >
            <Text style={styles.cardTitle}>{center.name}</Text>
            <Text style={styles.cardMeta}>{center.code}</Text>
            {center.address ? <Text style={styles.cardMeta}>{center.address}</Text> : null}
          </Pressable>
        ))}
      </View>
      <PrimaryButton label="Sign Out" onPress={onLogout} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: 12,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 4,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#0f172a',
  },
  cardMeta: {
    fontSize: 14,
    color: '#64748b',
  },
});
