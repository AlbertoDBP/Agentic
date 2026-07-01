import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Text } from 'react-native';
import { ApiError, getApiUrl } from '../src/api/client';
import { Field, PrimaryButton, Screen, Subtitle, Title } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';

export default function LoginScreen() {
  const { login } = useApp();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async () => {
    if (!email.trim() || !password) {
      Alert.alert('Missing fields', 'Enter your email and password.');
      return;
    }

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
    <Screen scroll>
      <Title>Charity Inventory</Title>
      <Subtitle>
        Sign in to scan products and log quantities for your assigned charity center.
      </Subtitle>
      <Field
        label="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        placeholder="agent@charity.local"
        autoFocus
      />
      <Field
        label="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        placeholder="Your password"
      />
      <PrimaryButton
        label={submitting ? 'Signing in...' : 'Sign In'}
        onPress={onSubmit}
        disabled={submitting}
      />
      <Text style={styles.hint}>API: {getApiUrl()}</Text>
      <Text style={styles.hint}>Demo: agent1@charity.local / password123</Text>
    </Screen>
  );
}

const styles = {
  hint: { color: '#64748b', fontSize: 13 },
};
