# To-Do List for Login Feature

- [ ] Configure Firebase Authentication in the Firebase project console.
  - [x] Enable Email/Password provider.
  - [x] Enable Google provider.
- [x] Install Firebase SDK in the frontend project (`npm install firebase`).
- [x] Create Firebase configuration file (`src/firebaseConfig.ts`).
- [x] Set up an Authentication Context/Provider (`src/context/AuthContext.tsx`).
- [x] Create a Login Form component (`src/components/Auth/LoginForm.tsx`).
  - [x] Implement Email/Password login logic.
  - [x] Implement Sign in with Google logic.
- [x] Create a Login Page (`src/pages/LoginPage.tsx`).
- [x] Add a route for the Login Page in `src/App.tsx`.
- [x] Test login flow.
  - [x] Test Email/Password login.
  - [x] Test Google Sign-In.
- [x] Create Account Home Page (`src/pages/AccountPage.tsx`).
- [x] Add route for Account Home Page in `src/App.tsx`.
- [x] Implement protected routes logic (redirect to /login if not authenticated).
- [ ] Update main `DOCS/Todo.md` to link or reflect progress on Firebase Auth setup. 