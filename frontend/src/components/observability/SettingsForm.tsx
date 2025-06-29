"use client"
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Settings, User, Loader2, CheckCircle, LogOut } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { loginUser } from '@/utils/userActions';
import { useDashboard } from '@/context/DashboardContext';

interface SettingsFormProps {
  baseUrl: string;
  setBaseUrl: (value: string) => void;
  authToken: string;
  setAuthToken: (value: string) => void;
  onSave: () => void;
}

export function SettingsForm({
  baseUrl,
  setBaseUrl,
  authToken,
  setAuthToken,
  onSave,
}: SettingsFormProps) {
  const { toast } = useToast();
  const { user, setUser } = useDashboard();
  
  // Login form state
  const [loginCredentials, setLoginCredentials] = useState({
    email: '',
    password: ''
  });
  const [loginLoading, setLoginLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!loginCredentials.email.trim() || !loginCredentials.password.trim()) {
      toast({
        title: "Error",
        description: "Please enter both email and password",
        variant: "destructive"
      });
      return;
    }

    setLoginLoading(true);
    try {
      const { user: loggedInUser, token } = await loginUser(loginCredentials);
      
      // Store token and set user context (this logs them into main app too!)
      localStorage.setItem('token', token);
      setUser(loggedInUser);
      setAuthToken(token);
      
      // Save settings
      onSave();
      
      toast({
        title: "Login successful",
        description: `Welcome, ${loggedInUser.name}! You're now logged in.`
      });
      
      // Clear login form
      setLoginCredentials({ email: '', password: '' });
    } catch (error) {
      console.error('Login error:', error);
      toast({
        title: "Login failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    // Remove token and clear user context (logs out of main app too!)
    localStorage.removeItem('token');
    localStorage.removeItem('observability-auth-token');
    setUser(null);
    setAuthToken('');
    setLoginCredentials({ email: '', password: '' });
    
    toast({
      title: "Logged out",
      description: "You have been logged out."
    });
  };

  const isAuthenticated = !!authToken && !!user;

  return (
    <div className="space-y-6">
      {/* Authentication */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Authentication
          </CardTitle>
          <CardDescription>
            {isAuthenticated 
              ? "Manage your authentication status"
              : "Log in to access API features and sync with main application"
            }
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isAuthenticated ? (
            <Alert>
              <CheckCircle className="h-4 w-4" />
              <AlertDescription className="flex items-center justify-between">
                <span>Authenticated as: <strong>{user.name}</strong> ({user.email})</span>
                <Button variant="outline" size="sm" onClick={handleLogout}>
                  <LogOut className="h-4 w-4 mr-2" />
                  Logout
                </Button>
              </AlertDescription>
            </Alert>
          ) : (
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="login-email">Email</Label>
                <Input
                  id="login-email"
                  type="email"
                  placeholder="your.email@example.com"
                  value={loginCredentials.email}
                  onChange={(e) => setLoginCredentials(prev => ({ ...prev, email: e.target.value }))}
                  disabled={loginLoading}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="login-password">Password</Label>
                <Input
                  id="login-password"
                  type="password"
                  placeholder="••••••••"
                  value={loginCredentials.password}
                  onChange={(e) => setLoginCredentials(prev => ({ ...prev, password: e.target.value }))}
                  disabled={loginLoading}
                />
              </div>
              
              <div className="flex justify-center">
                <Button 
                  type="submit"
                  className="min-w-[200px]"
                  disabled={loginLoading}
                >
                  {loginLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Logging in...
                    </>
                  ) : (
                    'Log in'
                  )}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Configuration
          </CardTitle>
          <CardDescription>
            Configure API endpoints
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* API Base URL */}
          <div className="space-y-2">
            <Label htmlFor="base-url">API Base URL</Label>
            <Input
              id="base-url"
              placeholder="http://localhost:8000"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>

          {/* Save Configuration */}
          <div className="pt-4 border-t">
            <div className="flex justify-center">
              <Button 
                className="min-w-[200px]"
                onClick={onSave}
                variant="default"
              >
                Save Configuration
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}