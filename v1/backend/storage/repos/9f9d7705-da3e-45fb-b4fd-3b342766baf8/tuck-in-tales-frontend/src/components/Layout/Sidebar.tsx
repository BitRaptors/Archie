import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { signOut } from 'firebase/auth';
import { auth } from '@/firebaseConfig';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import {
  LogOut,
  User,
  Settings,
  BookOpen,
  Sparkles,
  ToyBrick,
  Users,
  FileText,
} from 'lucide-react'; // Import specific icons

const navItems = [
  { name: 'Account', path: '/account', icon: User },
  { name: 'Family', path: '/family', icon: Users },
  { name: 'Characters', path: '/characters', icon: ToyBrick },
  { name: 'Memories', path: '/memories/list', icon: BookOpen },
  { name: 'Stories', path: '/stories/list', icon: Sparkles },
  { name: 'Prompts', path: '/prompts', icon: FileText },
  { name: 'Profile', path: '/profile', icon: Settings },
];

export default function Sidebar() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutLoading, setLogoutLoading] = React.useState(false);

  const handleLogout = async () => {
    setLogoutLoading(true);
    try {
      await signOut(auth);
      console.log('Logout successful from sidebar');
      navigate('/login');
    } catch (error) {
      console.error('Logout Error:', error);
    } finally {
      setLogoutLoading(false);
    }
  };

  return (
    <aside className="w-60 h-screen bg-muted/40 p-4 flex flex-col fixed left-0 top-0 border-r">
      <div className="mb-4">
        {/* Placeholder for Logo or App Name */}
        <h2 className="text-xl font-semibold">Tuck-In Tales</h2>
        {currentUser && (
          <p className="text-xs text-muted-foreground truncate">
            {currentUser.email}
          </p>
        )}
      </div>
      
      <nav className="flex-grow space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Button
              key={item.name}
              variant={isActive ? 'secondary' : 'ghost'}
              className="w-full justify-start"
              asChild // Important: Allows Button to wrap Link
            >
              <Link to={item.path}>
                <item.icon className="mr-2 h-4 w-4" /> {/* Render the icon */}
                {item.name}
              </Link>
            </Button>
          );
        })}
      </nav>

      {/* Logout Button at the bottom */}
      <div className="mt-auto">
        <Button 
          variant="outline" 
          className="w-full justify-start" 
          onClick={handleLogout} 
          disabled={logoutLoading}
        >
          <LogOut className="mr-2 h-4 w-4" /> {/* Add logout icon */}
          {logoutLoading ? 'Logging out...' : 'Logout'}
        </Button>
      </div>
    </aside>
  );
} 