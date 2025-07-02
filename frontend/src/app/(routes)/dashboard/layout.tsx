"use client";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import SidebarComponent from "@/components/dashboard/sidebar/DashboardSidebar";
import { Toaster } from "@/components/Toaster";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TenderProvider } from "@/context/TenderContext";
import { NotificationProvider } from "@/context/NotificationContext";
import LoginForm from "@/components/auth/LoginForm";
import { useDashboard } from "@/hooks/useDashboard";

const LoadingSpinner = () => (
  <div className="flex h-screen items-center justify-center">
    <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
  </div>
);

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, setUser } = useDashboard();
  const [isInitializing, setIsInitializing] = useState(true);
  const [showLogin, setShowLogin] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) {
          setShowLogin(true);
          return;
        }

        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/users/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          localStorage.removeItem("token");
          throw new Error(`Failed to fetch user data: ${response.status}`);
        }

        const userData = await response.json();
        setUser(userData); 
        setShowLogin(false);

      } catch (error) {
        console.error("Error checking authentication:", error);
        localStorage.removeItem("token");
        setShowLogin(true);
      } finally {
        setIsInitializing(false);
      }
    };

    checkAuth();
  }, [setUser]);

  if (isInitializing) {
    return <LoadingSpinner />;
  }

  if (showLogin) {
    return <LoginForm />;
  }

  return (
    <SidebarProvider>
      <TenderProvider>
        <NotificationProvider>
          <div className="w-full flex h-[100svh] sm:h-screen overflow-hidden">
            <SidebarComponent />
            <div className="flex h-[100svh] sm:h-screen w-full relative">
              {children}
            </div>
          </div>
          <Toaster />
        </NotificationProvider>
      </TenderProvider>
    </SidebarProvider>
  );
}