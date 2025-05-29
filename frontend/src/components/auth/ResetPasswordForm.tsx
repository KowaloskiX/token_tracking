"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { resetPassword } from "@/utils/userActions";
import { useRouter } from "next/navigation";

interface ResetPasswordFormProps {
    token: string; // Reset token passed from the page component
}

export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
    // Form state management
    const [password, setPassword] = useState(""); // State for the new password
    const [confirmPassword, setConfirmPassword] = useState(""); // State for confirming the new password
    const [isLoading, setIsLoading] = useState(false); // Loading state for form submission
    const [error, setError] = useState<string | null>(null); // Error message state
    const [success, setSuccess] = useState(false); // Success state after password reset
    const router = useRouter(); // Next.js router for navigation

    /**
     * Handles form submission for setting a new password
     */
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault(); // Prevent default form submission behavior
        setError(null); // Clear any previous errors
        
        // Validate passwords match
        if (password !== confirmPassword) {
            setError("Hasła nie są identyczne."); // Set error if passwords do not match
            return;
        }
        
        // Validate password length
        if (password.length < 8) {
            setError("Hasło powinno zawierać minimum 8 znaków."); // Set error if password is too short
            return;
        }
        
        setIsLoading(true); // Set loading state to true during form submission
        
        try {
            // Attempt to reset the password using the provided token and new password
            await resetPassword(token, password);
            setSuccess(true); // Set success state to true if password reset is successful
            
            // Redirect to login page after 3 seconds
            setTimeout(() => {
                router.push('/dashboard/tenders/chat');
            }, 3000);
        } catch (err: any) {
            // Handle errors during password reset
            setError(err.message || "Wystąpił błąd podczas resetowania hasła.");
        } finally {
            setIsLoading(false); // Reset loading state after submission
        }
    };

    // Success state UI - shown after successful password reset
    if (success) {
        return (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded relative" role="alert">
                <p className="font-medium">Hasło zostało zmienione!</p>
                <p className="text-sm">Za chwilę zostaniesz przekierowany do strony logowania.</p>
            </div>
        );
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
            
            {/* Password input field */}
            <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium">
                    Nowe hasło
                </Label>
                <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)} // Update password state on input change
                    placeholder="Minimum 8 znaków"
                    required
                    className="w-full h-10 px-3 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
            </div>
            
            {/* Confirm password input field */}
            <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-sm font-medium">
                    Potwierdź hasło
                </Label>
                <Input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)} // Update confirmPassword state on input change
                    placeholder="Powtórz hasło"
                    required
                    className="w-full h-10 px-3 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <p className="text-xs text-muted-foreground">
                    Hasło powinno zawierać minimum 8 znaków.
                </p>
            </div>
            
            {/* Submit button - shows loading state during form submission */}
            <Button 
                type="submit" 
                disabled={isLoading || !password || !confirmPassword} // Disable button if loading or inputs are empty
                className="w-full h-10 bg-primary hover:bg-primary/90 text-white rounded-md transition-colors"
            >
                {isLoading ? "Przetwarzanie..." : "Zmień hasło"} {/* Show loading text if isLoading is true */}
            </Button>
        </form>
    );
}