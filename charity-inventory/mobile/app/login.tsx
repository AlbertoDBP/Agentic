import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Text } from 'react-native';
import { ApiError } from '../src/api/client';
import { Field, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';

export default function LoginScreen() {
  const { login } = useApp();
  const [email, setEmail] = useState('agent1@charity.local');
  const [password, setPassword] = useState('password123');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async () => {
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      router.replace('/centers');
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Login failed';
      Alert.alert('Login failed', message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen>
      <Title>Charity Inventory</Title>
      <Subtitle>Sign in to scan products and log quantities for your assigned center.</Subtitle>
      <Field label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" />
      <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry />
      <PrimaryButton label={submitting ? 'Signing in...' : 'Sign In'} onPress={onSubmit} disabled={submitting} />
      <Text style={{ color: '#64748b', fontSize: 13 }}>
        Demo: agent1@charity.local / password123
      </Text>
    </Screen>
  );
}
