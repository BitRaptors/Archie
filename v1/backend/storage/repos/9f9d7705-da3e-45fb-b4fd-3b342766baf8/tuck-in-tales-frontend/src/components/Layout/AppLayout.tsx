import React from 'react';
import Sidebar from './Sidebar';
// import { SidebarLink } from '../SidebarLink'; // Remove import
import { Users, FileText, Settings } from 'lucide-react';

interface AppLayoutProps {
  children: React.ReactNode;
}

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  return (
    <div className="flex min-h-screen">
      <Sidebar>
        {/* Sidebar content is defined within Sidebar.tsx itself */}
      </Sidebar>
      <main className="flex-1 pl-60 p-6"> {/* Add padding p-6 */}
        {/* Add padding or container here if needed for content */}
        {children}
      </main>
    </div>
  );
};

export default AppLayout; 