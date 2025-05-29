"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDashboard } from "@/hooks/useDashboard";
import { checkOrCreateConversation } from "@/utils/conversationActions";
import { getUserAssistants, createAssistant } from "@/utils/assistantActions";
import { Assistant } from "@/types";
import { getStoredState } from "@/context/DashboardContext";
import { DEFAULT_PINECONE_CONFIG } from "@/app/constants/tenders";

export default function Dashboard() {
  const { 
    user, 
    setCurrentConversation, 
    setAssistants,
    currentAssistant,
    setCurrentAssistant
  } = useDashboard();
  const router = useRouter();

  useEffect(() => {
    const initializeDashboard = async () => {
      try {
        if (user?._id) {
          const userAssistants = await getUserAssistants(user._id);
          setAssistants(userAssistants);
  
          let targetAssistant: Assistant;
          
          const storedState = getStoredState();
          const storedAssistant = storedState?.currentAssistant;
          
          if (userAssistants.length === 0) {
            targetAssistant = await createAssistant({
              name: "Nowy Projekt",
              model: "gpt-4-turbo",
              owner_id: user._id,
              description: "Nowy projekt",
              temperature: 0.5,
              pinecone_config: DEFAULT_PINECONE_CONFIG
            });
            setAssistants([targetAssistant]);
            setCurrentAssistant(targetAssistant);
          } else if (storedAssistant && userAssistants.find(a => a._id === storedAssistant._id)) {
            targetAssistant = storedAssistant;
          } else {
            targetAssistant = userAssistants[userAssistants.length - 1];
            setCurrentAssistant(targetAssistant);
          }

          if (targetAssistant) {
            const newConversation = await checkOrCreateConversation(
              user._id,
              targetAssistant._id
            );
            setCurrentConversation(newConversation);
            router.push(`/dashboard/tenders/chat/${newConversation._id}`);
          }
        }
      } catch (error) {
        console.error("Error initializing dashboard:", error);
      }
    };

    initializeDashboard();
  }, [user, setAssistants, setCurrentConversation, setCurrentAssistant, router, currentAssistant]);

  return null;
}