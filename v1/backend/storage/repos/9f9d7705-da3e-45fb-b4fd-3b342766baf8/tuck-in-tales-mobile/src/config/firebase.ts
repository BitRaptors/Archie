import { initializeApp } from 'firebase/app';
// @ts-expect-error getReactNativePersistence exists in Firebase's RN bundle but not in the TS types
import { getAuth, initializeAuth, getReactNativePersistence } from 'firebase/auth';
import ReactNativeAsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.EXPO_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

// Initialize Firebase
export const app = initializeApp(firebaseConfig);

// Initialize Auth with platform-specific persistence
// Native: AsyncStorage persistence so auth state survives app restarts
// Web: built-in localStorage persistence via getAuth()
export const auth = Platform.OS === 'web'
  ? getAuth(app)
  : initializeAuth(app, {
      persistence: getReactNativePersistence(ReactNativeAsyncStorage),
    });

// Token management functions - platform-specific storage
// Use SecureStore for native, localStorage for web
export async function saveToken(token: string) {
  if (Platform.OS === 'web') {
    localStorage.setItem('firebase_token', token);
  } else {
    await SecureStore.setItemAsync('firebase_token', token);
  }
}

export async function getToken() {
  if (Platform.OS === 'web') {
    return localStorage.getItem('firebase_token');
  } else {
    return await SecureStore.getItemAsync('firebase_token');
  }
}

export async function removeToken() {
  if (Platform.OS === 'web') {
    localStorage.removeItem('firebase_token');
  } else {
    await SecureStore.deleteItemAsync('firebase_token');
  }
}

export async function getFirebaseToken() {
  const user = auth.currentUser;
  if (user) {
    return await user.getIdToken();
  }
  return null;
}
