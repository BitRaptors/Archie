import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { currentUser, loading } = useAuth();

  if (loading) {
    // Optional: Render a loading spinner or placeholder
    return <div>Loading...</div>; 
  }

  if (!currentUser) {
    // User not logged in, redirect to login page
    return <Navigate to="/login" replace />; 
  }

  // User is logged in, render the requested component
  return <>{children}</>; 
};

export default ProtectedRoute; 