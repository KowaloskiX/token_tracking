"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { createInvitation } from "@/utils/userActions";
import { useToast } from "@/hooks/use-toast"; // Hook for displaying toast notifications

export function CreateInvitationForm() {
  // State for email input
  const [email, setEmail] = useState("");
  // State for role selection, default is "member"
  const [role, setRole] = useState("member");
  // State to track loading status during form submission
  const [isLoading, setIsLoading] = useState(false);
  // Toast function for displaying notifications
  const { toast } = useToast();

  // Handler for form submission
  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      // Call API to create invitation and get response
      const response = await createInvitation(email, role);
      
      // Build the invitation URL with the token from response
      // The token is inside the invitation object
      const inviteUrl = `${window.location.origin}/accept-invitation?token=${response.invitation.token}`;
      
      // Copy the URL to clipboard
      await navigator.clipboard.writeText(inviteUrl);
      
      // Display success message with clipboard confirmation
      toast({
        title: "Sukces",
        description: "Zaproszenie zostało wysłane na podany adres e-mail i link do zaproszenia został skopiowany do schowka.",
      });
      
      // Clear the form
      setEmail("");
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Błąd",
        description: err.message || "Wystąpił błąd podczas wysyłania zaproszenia",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-card rounded-lg border p-6">
      {/* Form title */}
      <h3 className="text-lg font-medium mb-4">Zaproś nowych użytkowników</h3>
      {/* Form for inviting users */}
      <form onSubmit={handleInvite} className="flex flex-col sm:flex-row gap-3 items-end">
        {/* Email input field */}
        <div className="flex-1">
          <label htmlFor="email" className="text-sm font-medium mb-1 block">
            Adres email
          </label>
          <Input
            id="email"
            type="email"
            placeholder="jan.kowalski@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)} // Update email state on change
            required // Make the field required
          />
        </div>
        {/* Role selection dropdown */}
        <div className="w-full sm:w-40">
          <label htmlFor="role" className="text-sm font-medium mb-1 block">
            Rola
          </label>
          <Select value={role} onValueChange={setRole}> {/* Update role state on selection */}
            <SelectTrigger id="role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="admin">Administrator</SelectItem>
              <SelectItem value="member">Członek zespołu</SelectItem>
              <SelectItem value="guest">Gość</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {/* Submit button */}
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Wysyłanie..." : "Zaproś"} {/* Show loading text if isLoading is true */}
        </Button>
      </form>
    </div>
  );
}