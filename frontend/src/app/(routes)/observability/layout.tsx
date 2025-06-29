"use client"
import { useState, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, Filter, History, Settings, Target } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { DashboardProvider, useDashboard } from '@/context/DashboardContext';

function ObservabilityLayoutContent({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, setUser } = useDashboard();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  const getActiveTab = () => {
    if (pathname.includes('/search')) return 'search';
    if (pathname.includes('/filter')) return 'filter';
    if (pathname.includes('/analyze-single')) return 'analyze-single';
    if (pathname.includes('/history')) return 'history';
    if (pathname.includes('/settings')) return 'settings';
    return 'search';
  };

  const handleTabChange = (value: string) => {
    router.push(`/observability/${value}`);
  };

  // Check for existing authentication
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) {
          setUser(null); // Clear user state when no token
          setIsCheckingAuth(false);
          return;
        }

        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/users/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          localStorage.removeItem("token");
          setUser(null); // Clear user state when token is invalid
          console.log("Invalid token found, cleaned up");
        } else {
          const userData = await response.json();
          setUser(userData);
          console.log("User authenticated:", userData.name);
        }

      } catch (error) {
        console.error("Error checking authentication:", error);
        localStorage.removeItem("token");
        setUser(null); // Clear user state on error
      } finally {
        setIsCheckingAuth(false);
      }
    };

    checkAuth();
  }, [setUser]);

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Observability Panel
          </h1>
          <p className="text-muted-foreground">
            Monitor and test tender search, filtering, and analysis operations
          </p>
          {/* Show authentication status */}
          {!isCheckingAuth && (
            user ? (
              <p className="text-sm text-green-600 mt-2">
                ✓ Logged in as: <span className="font-medium">{user.name}</span> ({user.email})
              </p>
            ) : (
              <p className="text-sm text-amber-600 mt-2">
                ⚠ Not authenticated - use Settings to log in for API access
              </p>
            )
          )}
        </div>

        {/* Navigation */}
        <div className="mb-6">
          <Tabs value={getActiveTab()} onValueChange={handleTabChange}>
            <TabsList className="grid w-full max-w-2xl grid-cols-5">
              <TabsTrigger value="search" className="flex items-center gap-2">
                <Search className="h-4 w-4" />
                Search
              </TabsTrigger>
              <TabsTrigger value="filter" className="flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Filter
              </TabsTrigger>
              <TabsTrigger value="analyze-single" className="flex items-center gap-2">
                <Target className="h-4 w-4 flex-shrink-0" />
                Analyze Single
              </TabsTrigger>
              <TabsTrigger value="history" className="flex items-center gap-2">
                <History className="h-4 w-4" />
                History
              </TabsTrigger>
              <TabsTrigger value="settings" className="flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Settings
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* Content */}
        {children}
      </div>
    </div>
  );
}

export default function ObservabilityLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardProvider>
      <ObservabilityLayoutContent>
        {children}
      </ObservabilityLayoutContent>
    </DashboardProvider>
  );
}