"use client"
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronLeft, Trash2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from '@/components/ui/switch';
import { useDashboard } from '@/context/DashboardContext';
import { Assistant } from '@/types';
import { updateAssistant, deleteAssistant, AssistantUpdateData } from '@/utils/assistantActions';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface EditAssistantFormProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    assistant: Assistant;
  }
  
  const EditAssistantForm = ({ open, onOpenChange, assistant }: EditAssistantFormProps) => {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { setCurrentAssistant, assistants, setAssistants } = useDashboard();
  
    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setLoading(true);
      setError(null);
  
      try {
        const formData = new FormData(e.currentTarget);
        const name = formData.get('name') as string;

        const updatedData: AssistantUpdateData = {};
        
        if (name !== assistant.name) {
          updatedData.name = name;
        }
        

        if (Object.keys(updatedData).length > 0) {
          const updatedAssistant = await updateAssistant(assistant, updatedData);
          
          const updatedAssistants = assistants.map(a => 
            a._id === updatedAssistant._id ? updatedAssistant : a
          );
          setAssistants(updatedAssistants);
          setCurrentAssistant(updatedAssistant);
          
          onOpenChange(false);
          router.refresh();
        } else {
          onOpenChange(false);
        }
      } catch (error) {
        console.error('Error updating project:', error);
        setError('Failed to update project. Please try again.');
      } finally {
        setLoading(false);
      }
    };
  
      const handleDelete = async () => {
        try {
          await deleteAssistant(assistant);
          
          // Update assistants in context
          const updatedAssistants = assistants.filter(a => a._id !== assistant._id);
          setAssistants(updatedAssistants);
          setCurrentAssistant(null);
          
          onOpenChange(false);
          router.push('/dashboard/tenders/chat');
          setShowDeleteConfirm(false);
        } catch (error) {
          console.error('Error deleting assistant:', error);
        }
      };

  if (!open) return null;

  return (
    <div className="fixed top-0 left-0 w-[100svw] h-[100svh] bg-background z-[9999] flex justify-center">
      <div className="bg-background max-w-lg w-full relative py-10 border border-neutral-100 shadow px-10">
        <Button 
          variant="outline" 
          className="rounded-full p-2 h-auto"
          onClick={() => onOpenChange(false)}
        >
          <ChevronLeft className="h-6 w-6" />
        </Button>
        
        <div className="w-full border-b py-4 space-y-1">
          <h3 className="text-xl font-medium">Edit assistant</h3>
          <p className="text-sm text-muted-foreground">
            Modify your assistant`&apos;`s settings and behavior.
          </p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-6 py-6">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              name="name"
              placeholder="Assistant's Name"
              className="w-full"
              required
              disabled={loading}
              defaultValue={assistant.name}
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
              defaultValue={assistant.system_prompt}
            />
          </div>
          
          <div className="flex flex-row items-center justify-between rounded-lg border p-4">
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

          <div className="space-y-4">
            <Button 
              type="submit" 
              className="w-full bg-black text-white hover:bg-gray-800"
              disabled={loading}
            >
              {loading ? "Saving..." : "Save Changes"}
            </Button>

            <Button 
              type="button"
              variant="outline"
              className="w-full text-red-500 border-red-500 hover:bg-red-50"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={loading}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete Assistant
            </Button>
          </div>
        </form>
      </div>

      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete your assistant
              and remove all of its data from our servers.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-500 hover:bg-red-600"
              onClick={handleDelete}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default EditAssistantForm;