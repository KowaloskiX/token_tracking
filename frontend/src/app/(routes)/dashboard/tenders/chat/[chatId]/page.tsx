"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Header from "@/components/dashboard/chat/ChatHeader";
import SidebarComponent from "@/components/dashboard/sidebar/DashboardSidebar";
import ChatContainer from "@/components/dashboard/chat/ChatContainer";
import { useDashboard } from "@/hooks/useDashboard";
import LoginForm from "@/components/auth/LoginForm";
import { Loader2 } from "lucide-react";
import { getConversation } from "@/utils/conversationActions";
import { getUserAssistants, createAssistant } from "@/utils/assistantActions";
import MemorySidebar from "@/components/dashboard/sidebar/memory/MemorySidebar";
import { Assistant } from "@/types";
import { DEFAULT_PINECONE_CONFIG } from "@/app/constants/tenders";

const LoadingSpinner = () => (
  <div className="flex w-full h-screen items-center justify-center">
    <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
  </div>
);

export default function Dashboard() {
  const { 
    user, 
    setCurrentConversation, 
    setAssistants,
    currentAssistant,
    setCurrentAssistant
  } = useDashboard();
  const [isInitializing, setIsInitializing] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [showLogin, setShowLogin] = useState(false);
  const params = useParams();
  const chatId = params.chatId as string;

  useEffect(() => {
    const initializeDashboard = async () => {
      try {
        const token = localStorage.getItem("token");
        const shouldShowLogin = !token || !user;
        setShowLogin(shouldShowLogin);

        if (!shouldShowLogin && user?._id) {
          setIsLoading(true);
          
          const userAssistants = await getUserAssistants(user._id);
          setAssistants(userAssistants);

          if (chatId && chatId !== 'new') {
            const conversation = await getConversation(chatId);
            if (conversation) {
              setCurrentConversation(conversation);
              const conversationAssistant = userAssistants.find(
                a => a._id === conversation.assistant_id
              );
              if (conversationAssistant) {
                setCurrentAssistant(conversationAssistant);
              }
            }
          } else {
            let targetAssistant: Assistant;
            
            if (userAssistants.length === 0) {
              targetAssistant = await createAssistant({
                name: "Nowy Projekt",
                model: "gpt-4-turbo",
                owner_id: user._id,
                description: "Nowy projekt",
                temperature: 0.7,
                pinecone_config: DEFAULT_PINECONE_CONFIG,
                assigned_users: []
              });
              setAssistants([targetAssistant]);
              setCurrentAssistant(targetAssistant);
            } else if (!currentAssistant) {
              targetAssistant = userAssistants[userAssistants.length - 1];
              setCurrentAssistant(targetAssistant);
            } else {
              targetAssistant = currentAssistant;
            }
          }
        }
      } catch (error) {
        console.error("Error initializing dashboard:", error);
      } finally {
        setIsLoading(false);
        setIsInitializing(false);
      }
    };

    initializeDashboard();
  }, [user, chatId, setAssistants, setCurrentConversation, setCurrentAssistant]);

  // Show loading state during initialization
  if (isInitializing) {
    return <LoadingSpinner />;
  }

  // Show login if needed
  if (showLogin) {
    return <LoginForm />;
  }

  // Show loading state for secondary operations
  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <>
      <div className="flex flex-col flex-1 h-[100svh]">
        <Header />
        <ChatContainer />
      </div>
      <MemorySidebar />
    </>
  );
}