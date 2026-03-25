import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom'; // Import for redirection
import { 
  signInWithEmailAndPassword, 
  GoogleAuthProvider, 
  signInWithPopup 
} from 'firebase/auth'; // Firebase auth functions
import { auth } from '@/firebaseConfig'; // Firebase auth instance
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"; // Import Separator

// Simple Google Icon Placeholder (replace with actual SVG if desired)
const GoogleIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="mr-2 h-4 w-4" viewBox="0 0 48 48" fill="#000000">
    <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
    <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
    <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
    <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571l0.001-0.001l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
  </svg>
);

export function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false); // Separate loading state for Google
  const navigate = useNavigate(); // Hook for navigation

  const handleEmailPasswordSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (loading || googleLoading) return; // Prevent double submit
    setLoading(true);
    setError(null);

    try {
      await signInWithEmailAndPassword(auth, email, password);
      console.log('Email/Password Login successful!');
      navigate('/account');
    } catch (err: any) {
      console.error("Firebase email/password login error:", err);
      let errorMessage = 'Failed to log in. Please check your credentials.';
      if (err.code === 'auth/user-not-found' || err.code === 'auth/wrong-password' || err.code === 'auth/invalid-credential') {
        errorMessage = 'Invalid email or password.';
      } else if (err.code === 'auth/invalid-email') {
        errorMessage = 'Please enter a valid email address.';
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    if (loading || googleLoading) return; // Prevent double submit
    setGoogleLoading(true);
    setError(null);
    const provider = new GoogleAuthProvider();

    try {
      await signInWithPopup(auth, provider);
      console.log('Google Sign-In successful!');
      navigate('/account');
    } catch (err: any) {
      console.error("Firebase Google sign-in error:", err);
      let errorMessage = 'Failed to sign in with Google.';
      // Handle common errors like popup closed, account exists with different credential, etc.
      if (err.code === 'auth/popup-closed-by-user') {
        errorMessage = 'Sign-in process cancelled.';
      } else if (err.code === 'auth/account-exists-with-different-credential') {
        errorMessage = 'An account already exists with this email using a different sign-in method.';
      }
      setError(errorMessage);
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <Card className="w-[350px]">
      <CardHeader>
        <CardTitle>Login</CardTitle>
        <CardDescription>Enter your credentials or sign in with Google.</CardDescription>
      </CardHeader>
      {/* Email/Password Form */}
      <form onSubmit={handleEmailPasswordSubmit}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input 
              id="email" 
              type="email" 
              placeholder="m@example.com" 
              required 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading || googleLoading}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input 
              id="password" 
              type="password" 
              required 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading || googleLoading}
            />
          </div>
          {/* Display error below form fields */}
        </CardContent>
        <CardFooter className="flex flex-col space-y-3">
          <Button type="submit" className="w-full" disabled={loading || googleLoading}>
            {loading ? 'Logging in...' : 'Login with Email'}
          </Button>
          {error && <p className="text-sm text-red-500 dark:text-red-400 pt-1 w-full text-center">{error}</p>}
        </CardFooter>
      </form>

      {/* Separator */}
      <div className="relative px-6 py-2">
        <div className="absolute inset-0 flex items-center">
          <Separator />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-card px-2 text-muted-foreground">
            Or continue with
          </span>
        </div>
      </div>

      {/* Google Sign-In Button */}
      <div className="p-6 pt-0">
        <Button 
          variant="outline" 
          className="w-full" 
          onClick={handleGoogleSignIn} 
          disabled={loading || googleLoading}
        >
          {googleLoading ? (
            'Signing in...' 
          ) : (
            <>
              <GoogleIcon /> Sign in with Google
            </>
          )}
        </Button>
      </div>
    </Card>
  );
} 