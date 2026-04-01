import React from 'react';
// import { useNavigate } from 'react-router-dom'; // No longer needed here
// import { signOut } from 'firebase/auth'; // No longer needed here
// import { auth } from '@/firebaseConfig'; // No longer needed here
import { useAuth } from '@/context/AuthContext';
// import { Button } from '@/components/ui/button'; // No longer needed here
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge"; 

export default function AccountPage() {
  const { currentUser } = useAuth();
  // const navigate = useNavigate(); // No longer needed here
  // const [logoutLoading, setLogoutLoading] = React.useState(false); // No longer needed here

  // const handleLogout = async () => { ... }; // Removed logout logic

  if (!currentUser) {
    // Keep this check for robustness
    return <div>Loading user data...</div>; 
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      {/* Removed bg-gray-100 dark:bg-gray-900 as layout handles background */}
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Account Details</CardTitle>
          <CardDescription>
            Welcome, {currentUser.displayName || currentUser.email}!
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-muted-foreground">Email:</span>
            <span className="text-sm">{currentUser.email}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-muted-foreground">Email Verified:</span>
            <Badge variant={currentUser.emailVerified ? "default" : "destructive"}>
              {currentUser.emailVerified ? 'Yes' : 'No'}
            </Badge>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-muted-foreground">User ID:</span>
            <span className="text-sm font-mono text-muted-foreground break-all">{currentUser.uid}</span>
          </div>
          
          {/* Removed Logout Button */}
        </CardContent>
      </Card>
    </div>
  );
} 