import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { toast } from "@/hooks/use-toast"
import { useDashboard } from '@/context/DashboardContext';
import { Assistant } from '@/types';
import { createAssistant } from '@/utils/assistantActions';
import { DialogDescription, DialogTitle } from '@radix-ui/react-dialog';
import { checkOrCreateConversation } from '@/utils/conversationActions';
import { DEFAULT_PINECONE_CONFIG } from '@/app/constants/tenders';

const CreateAssistantForm = ({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) => {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const { setCurrentAssistant, user, assistants, setAssistants, setCurrentConversation } = useDashboard();
  
    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setLoading(true);
  
      try {
        const formData = new FormData(e.currentTarget);
        
        const assistantData: Omit<Assistant, 'id' | 'created_at' | 'openai_assistant_id'> = {
          name: formData.get('name') as string,
          description: '',
          model: 'gpt-4-turbo',
          system_prompt: "You are a helpful assistant. You never halucinate and only tell things that you are 100% sure.",
          owner_id: user?._id || '',
          org_id: user?.org_id || '', // <-- Added org_id from user state
          tools: [{ type: 'file_search' }],
          temperature: 0.6,
          shared_with: [],
          icon: '',
          pinecone_config: DEFAULT_PINECONE_CONFIG,
          assigned_users: []
        };
        
        const newAssistant = await createAssistant(assistantData);
        
        setAssistants([...assistants, newAssistant]);
        setCurrentAssistant(newAssistant);
        onOpenChange(false);
        const newConversation = await checkOrCreateConversation(
          user?._id,
          newAssistant._id
      );
      setCurrentConversation(newConversation);
      router.push(`/dashboard/tenders/chat/${newConversation._id}`);
      } catch (error) {
        console.error('Error creating assistant:', error);
        toast({
          variant: "destructive",
          description: "Failed to create assistant. Please try again.",
        });
      } finally {
        setLoading(false);
      }
    };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <div className="relative">
          <div className="w-full border-b pb-4 space-y-1">
            <DialogTitle className="text-xl font-medium">Nowy Projekt</DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              Nowy projekt, gdzie będziesz współpracować z AI.
            </DialogDescription>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-6 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nazwa</Label>
              <Input
                id="name"
                name="name"
                placeholder="Nazwa projektu"
                className="w-full"
                required
                disabled={loading}
              />
            </div>

            {/* <div className="space-y-2">
              <Label htmlFor="personality">Personality</Label>
              <Textarea
                id="personality"
                name="personality"
                placeholder="Describe the assistant's personality and what it is supposed to do. This will directly affect how it behaves and performs."
                className="min-h-[120px] w-full"
                required
                disabled={loading}
              />
            </div> */}
            
            {/* <div className="flex flex-row items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <Label className="text-base">
                  Knowledge upload
                </Label>
                <p className="text-sm text-muted-foreground">
                  Upload files/websites to assistant knowledge.
                </p>
              </div>
              <div>
                <Switch
                  checked={fileUpload}
                  onCheckedChange={setFileUpload}
                  disabled={loading}
                />
              </div>
            </div> */}

            <Button 
              type="submit" 
              className="w-full bg-black text-white hover:bg-gray-800"
              disabled={loading}
            >
              {loading ? "Tworzenie..." : "Stwórz Projekt"}
            </Button>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default CreateAssistantForm;