# Google Sign-In Setup Guide

## Overview
This guide will help you configure Google Sign-In for your React Native app using Firebase Authentication.

## Prerequisites
- Firebase project already set up (✓ you have this)
- Google Sign-In already enabled in Firebase Console (✓ you have this)

## Step 1: Get Web Client ID

This is the most important one for development. You already have it from Firebase:

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your project: **tuck-in-tales**
3. Go to **Authentication** → **Sign-in method** → **Google**
4. You'll see a **Web SDK configuration** section
5. Copy the **Web client ID** (ends with `.apps.googleusercontent.com`)

**OR** get it from Google Cloud Console:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select project: **tuck-in-tales**
3. Go to **APIs & Services** → **Credentials**
4. Find the **Web client** credential (auto-created by Firebase)
5. Copy the **Client ID**

## Step 2: Update .env File

Open `.env` and replace the placeholder values:

```bash
# The Web Client ID works for all platforms during development
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID="YOUR_ACTUAL_WEB_CLIENT_ID.apps.googleusercontent.com"

# For iOS/Android, you can use the same Web Client ID during development
# Or get platform-specific IDs from Google Cloud Console
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID="YOUR_ACTUAL_WEB_CLIENT_ID.apps.googleusercontent.com"
EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID="YOUR_ACTUAL_WEB_CLIENT_ID.apps.googleusercontent.com"
```

**Quick Start:** For testing on web, you only need `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`.

## Step 3: Install Dependencies

```bash
npm install expo-auth-session expo-web-browser expo-crypto
```

## Step 4: Restart Expo Dev Server

After updating `.env` and installing packages:

```bash
# Stop the current server (Ctrl+C)
# Then restart:
npx expo start --web
```

## Step 5: Test Google Sign-In

1. Open the app in your browser
2. Click **"Continue with Google"**
3. You should see the Google OAuth popup
4. Select your Google account
5. After authentication, you'll be signed in and redirected to the app

## Troubleshooting

### Error: "Invalid Client ID"
- Make sure you copied the correct Web Client ID from Firebase/Google Cloud Console
- Check that there are no extra spaces in the `.env` file
- Restart the Expo dev server after updating `.env`

### Error: "redirect_uri_mismatch"
- For web development, Expo handles this automatically
- If you see this error, check the Google Cloud Console → Credentials → Your Web Client → Authorized redirect URIs
- Add: `https://auth.expo.io/@YOUR_USERNAME/tuck-in-tales-mobile` (for production)

### Google popup doesn't open
- Check browser console for errors
- Make sure `expo-web-browser` is installed
- Verify the `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` is set correctly

## Platform-Specific Setup (For Production)

### iOS
1. Get iOS Client ID from Google Cloud Console
2. Add URL scheme to `app.json`:
```json
{
  "expo": {
    "ios": {
      "bundleIdentifier": "com.yourcompany.tuckin",
      "googleServicesFile": "./GoogleService-Info.plist"
    }
  }
}
```

### Android
1. Get Android Client ID from Google Cloud Console
2. Add to `app.json`:
```json
{
  "expo": {
    "android": {
      "package": "com.yourcompany.tuckin",
      "googleServicesFile": "./google-services.json"
    }
  }
}
```

## Next Steps

Once Google Sign-In is working:
- Test the authentication flow
- Verify user data is saved correctly
- Test sign-out and re-authentication
- Proceed with building the main app features
