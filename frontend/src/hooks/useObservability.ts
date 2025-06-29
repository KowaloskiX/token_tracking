// hooks/useObservability.ts
import { useState } from 'react';
import { observabilityApi } from '@/utils/observabilityApi';
import { useToast } from '@/hooks/use-toast';

export const useObservability = () => {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const runSearch = async (params: any, token: string) => {
    setLoading(true);
    try {
      const data = await observabilityApi.search(params, token);
      toast({
        title: "Search completed",
        description: `Found ${data.total_matches} matches`
      });
      return data;
    } catch (error) {
      toast({
        title: "Search failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const runFilter = async (params: any, token: string) => {
    setLoading(true);
    try {
      const data = await observabilityApi.filter(params, token);
      toast({
        title: "Filtering completed",
        description: `Kept ${data.total_filtered}, filtered out ${data.total_filtered_out}`
      });
      return data;
    } catch (error) {
      toast({
        title: "Filtering failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const getSearch = async (searchId: string, token: string) => {
    setLoading(true);
    try {
      const data = await observabilityApi.getSearch(searchId, token);
      toast({
        title: "Search results retrieved",
        description: `Loaded ${data.total_matches} saved results`
      });
      return data;
    } catch (error) {
      toast({
        title: "Failed to retrieve results",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const getFilter = async (filterId: string, token: string) => {
    setLoading(true);
    try {
      const data = await observabilityApi.getFilter(filterId, token);
      toast({
        title: "Filter results retrieved",
        description: `Loaded saved filter results`
      });
      return data;
    } catch (error) {
      toast({
        title: "Failed to retrieve filter results",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
      throw error;
    } finally {
      setLoading(false);
    }
  };

  return { 
    runSearch, 
    runFilter, 
    getSearch, 
    getFilter, 
    loading 
  };
};