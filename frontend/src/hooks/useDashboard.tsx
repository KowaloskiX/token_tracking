import { DashboardContext } from "@/context/DashboardContext";
import { useContext } from "react";

export function useDashboard() {
    const context = useContext(DashboardContext);
    if (context === undefined) {
      throw new Error('useDashboard must be used within an AppProvider');
    }
    return context;
  }