import { auth } from '@/firebaseConfig';
import { type User } from 'firebase/auth';

/**
 * Retrieves the Firebase ID token for the currently signed-in user.
 * @returns {Promise<string | null>} A promise that resolves with the ID token string, or null if no user is signed in.
 */
export const getFirebaseToken = async (): Promise<string | null> => {
  const currentUser: User | null = auth.currentUser;
  if (currentUser) {
    try {
      const token = await currentUser.getIdToken(true); // Force refresh the token
      return token;
    } catch (error) {
      console.error("Error getting Firebase ID token:", error);
      return null;
    }
  } else {
    console.log("No user currently signed in.");
    return null;
  }
}; 