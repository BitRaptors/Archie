import { useState, useEffect } from 'react';
import { Platform } from 'react-native';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { GoogleAuthProvider, signInWithCredential, signInWithPopup } from 'firebase/auth';
import { auth } from '../config/firebase';

WebBrowser.maybeCompleteAuthSession();

export function useGoogleSignIn() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    clientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
    iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
    androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
  });

  // Debug logging
  useEffect(() => {
    if (request) {
      console.log('[GoogleSignIn] redirectUri:', request.redirectUri);
      console.log('[GoogleSignIn] clientId used:', request.clientId);
    }
  }, [request]);

  useEffect(() => {
    if (!response) return;

    if (response.type === 'success') {
      setLoading(true);
      setError(null);
      const { id_token } = response.params;
      const credential = GoogleAuthProvider.credential(id_token);
      signInWithCredential(auth, credential)
        .catch((err) => {
          console.error('Firebase credential sign-in error:', err);
          setError(err.message || 'Failed to sign in with Google');
        })
        .finally(() => setLoading(false));
    } else if (response.type === 'error') {
      setError(response.error?.message || 'Google Sign-In failed');
    }
  }, [response]);

  const signInWithGoogle = async () => {
    setLoading(true);
    setError(null);

    try {
      if (Platform.OS === 'web') {
        const provider = new GoogleAuthProvider();
        await signInWithPopup(auth, provider);
      } else {
        await promptAsync();
        return;
      }
    } catch (err: any) {
      console.error('Google Sign-In Error:', err);
      setError(err.message || 'Failed to sign in with Google');
    } finally {
      if (Platform.OS === 'web') {
        setLoading(false);
      }
    }
  };

  return {
    signInWithGoogle,
    loading,
    error,
    isReady: Platform.OS === 'web' || !!request,
  };
}
