import React from 'react';
import { BrowserRouter as Router, Route, Routes, Link } from 'react-router-dom';
import LoginPage from '@/pages/LoginPage';
import AccountPage from '@/pages/AccountPage';
import CharacterCreationPage from '@/pages/CharacterCreationPage';
import MemoryLoggingPage from '@/pages/MemoryLoggingPage';
import StoryGenerationPage from '@/pages/StoryGenerationPage';
import StoryViewerPage from '@/pages/StoryViewerPage';
import ProfilePage from '@/pages/ProfilePage';
import FamilyPage from '@/pages/FamilyPage';
import ProtectedRoute from '@/components/Auth/ProtectedRoute';
import AppLayout from '@/components/Layout/AppLayout';
import { Button } from "@/components/ui/button";
import CharactersPage from './pages/CharactersPage';
import CharacterDetailPage from './pages/CharacterDetailPage';
import { AuthProvider } from './context/AuthContext';
import { Toaster } from 'sonner';
import StoryProgressPage from './pages/StoryProgressPage';
import StoryListPage from './pages/StoryListPage';
import PromptsPage from './pages/PromptsPage';
import MemoriesListPage from './pages/MemoriesListPage';

// Placeholder Home Component
function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-2xl mb-4">Home Page</h1>
      <Link to="/login">
        <Button>Go to Login</Button>
      </Link>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Routes */}
          <Route 
            path="/account" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <AccountPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/characters" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <CharactersPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/characters/create" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <CharacterCreationPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/characters/:characterId" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <CharacterDetailPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/stories/generate" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <StoryGenerationPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/stories/list" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <StoryListPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/stories/:storyId" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <StoryProgressPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/stories/:storyId/view" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <StoryViewerPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/memories"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <MemoryLoggingPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/memories/list"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <MemoriesListPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route 
            path="/family" 
            element={
              <ProtectedRoute>
                <AppLayout>
                  <FamilyPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/prompts"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <PromptsPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ProfilePage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
        </Routes>
        <Toaster richColors position="top-right" />
      </AuthProvider>
    </Router>
  );
}

export default App;
