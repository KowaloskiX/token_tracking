"use client";

/**
 * AcceptInvitationForm
 * 
 * This component renders a form for accepting organization invitations.
 * It handles form submission, validation, error states, and success redirection.
 */

import { useState, useEffect } from "react";
import { acceptInvitation, getInvitationByToken } from "@/utils/userActions";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

interface AcceptInvitationFormProps {
  token: string; // Invitation token passed from the page component
}

export function AcceptInvitationForm({ token }: AcceptInvitationFormProps) {
  // Form state management
  const [name, setName] = useState(""); // Add state for name
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const router = useRouter();

  // Fetch invitation details when component mounts
  useEffect(() => {
    async function fetchInvitationDetails() {
      try {
        const invitation = await getInvitationByToken(token);
        setEmail(invitation.email);
        setIsFetching(false);
      } catch (err: any) {
        setError(err.message || "Nie udało się pobrać szczegółów zaproszenia");
        setIsFetching(false);
      }
    }

    fetchInvitationDetails();
  }, [token]);

  /**
   * Handles form submission
   * 1. Prevents default form behavior
   * 2. Resets error state and sets loading state
   * 3. Calls the API to accept the invitation
   * 4. Handles success or error states
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    
    try {
      // Call the API to accept the invitation with name included
      const data = await acceptInvitation(token, email, password, name);
      // Auto-login: store the token into localStorage (or cookies)
      localStorage.setItem("token", data.access_token); // Match your other functions
      // Optionally update your auth context/state here
      // Set success state and redirect to the dashboard after a delay
      setSuccess(true);
      setTimeout(() => {
        router.push('/dashboard/tenders/chat'); // Updated destination
      }, 2000);
    } catch (err: any) {
      // Handle error cases
      setError(err.message || "Wystąpił błąd podczas akceptacji zaproszenia.");
    } finally {
      setIsLoading(false);
    }
  };

  // Success state UI - shown after successful form submission
  if (success) {
    return (
      <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded relative" role="alert">
        <p className="font-medium">Zaproszenie zaakceptowane!</p>
        <p className="text-sm">Za chwilę zostaniesz przekierowany do strony głównej.</p>
      </div>
    );
  }

  // Loading state UI - shown while fetching invitation details
  if (isFetching) {
    return <div className="text-center py-4">Ładowanie szczegółów zaproszenia...</div>;
  }

  // Main form UI
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Error alert - shown only when an error occurs */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
          <p className="font-medium">Błąd</p>
          <p className="text-sm">{error}</p>
        </div>
      )}
      
      {/* Name input field - add this before the email field */}
      <div className="space-y-2">
        <Label htmlFor="name" className="text-sm font-medium">
          Twoje imię i nazwisko
        </Label>
        <Input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Jan Kowalski"
          required
          className="w-full h-10 px-3 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
        />
      </div>
      
      {/* Email input field */}
      <div className="space-y-2">
        <Label htmlFor="email" className="text-sm font-medium">
          Email
        </Label>
        <Input
          id="email"
          type="email"
          value={email}
          readOnly
          required
          className="w-full h-10 px-3 py-2 border border-input bg-muted rounded-md cursor-not-allowed"
        />
        {/* Helper text for email field */}
        <p className="text-xs text-muted-foreground">
          To jest adres email, na który zostało wysłane zaproszenie.
        </p>
      </div>
      
      {/* Password input field */}
      <div className="space-y-2">
        <Label htmlFor="password" className="text-sm font-medium">
          Hasło
        </Label>
        <Input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Minimum 8 znaków"
          required
          className="w-full h-10 px-3 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
        />
        {/* Helper text for password requirements */}
        <p className="text-xs text-muted-foreground">
          Hasło powinno zawierać minimum 8 znaków.
        </p>
      </div>
      
      {/* Submit button - shows loading state during form submission */}
      <Button 
        type="submit" 
        disabled={isLoading}
        className="w-full h-10 bg-primary hover:bg-primary/90 text-white rounded-md transition-colors"
      >
        {isLoading ? "Przetwarzanie..." : "Akceptuj zaproszenie"}
      </Button>
    </form>
  );
}