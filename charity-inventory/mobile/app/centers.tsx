import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { api } from '../src/api/client';
import { Badge, LoadingState, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';
import { useRequireAuth } from '../src/hooks/useRequireAuth';
import type { Center } from '../src/types';

export default function CentersScreen() {
  const { centers, logout, setSelectedCenter, setSessionId, user } = useApp();
  const { loading } = useRequireAuth();
  const [loadingCenterId, setLoadingCenterId] = useState<number | null>(null);

  const startCenter = async (center: Center) => {
    setLoadingCenterId(center.id);
    try {
      const session = await api.createSession(center.id);
      setSelectedCenter(center);
      setSessionId(session.session.id);
      router.push('/scan');
    } catch {
      Alert.alert('Unable to start session', 'Please check your connection and try again.');
    } finally {
      setLoadingCenterId(null);
    }
  };

  const onLogout = async () => {
    await logout();
    router.replace('/login');
  };

  if (loading) {
    return <LoadingState message="Loading your centers..." />;
  }

  return (
    <Screen scroll>
      <Title>Select Center</Title>
      <Subtitle>
        Signed in as {user?.fullName}. Choose where you are collecting inventory today.
      </Subtitle>
      {centers.length === 0 ? (
        <Subtitle>No centers assigned to your account. Contact an administrator.</Subtitle>
      ) : (
        <View style={styles.list}>
          {centers.map((center) => (
            <Pressable
              key={center.id}
              style={styles.card}
              onPress={() => startCenter(center)}
              disabled={loadingCenterId === center.id}
            >
              <Text style={styles.cardTitle}>{center.name}</Text>
              <Badge label={center.code} />
              {center.address ? <Text style={styles.cardMeta}>{center.address}</Text> : null}
              <Text style={styles.cardAction}>
                {loadingCenterId === center.id ? 'Starting session...' : 'Tap to start scanning'}
              </Text>
            </Pressable>
          ))}
        </View>
      )}
      <PrimaryButton label="Sign Out" variant="secondary" onPress={onLogout} />
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
    gap: 8,
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
  cardAction: {
    fontSize: 13,
    color: '#1d4ed8',
    fontWeight: '600',
    marginTop: 4,
  },
});
