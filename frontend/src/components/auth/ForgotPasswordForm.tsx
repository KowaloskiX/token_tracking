"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { requestPasswordReset } from "@/utils/userActions";

export function ForgotPasswordForm() {
    // State to manage the email input value
    const [email, setEmail] = useState("");
    // State to track whether the form is in a loading state
    const [isLoading, setIsLoading] = useState(false);
    // State to store any error messages
    const [error, setError] = useState<string | null>(null);
    // State to track whether the password reset request was successful
    const [success, setSuccess] = useState(false);

    /**
     * Handles form submission for password reset request
     * @param e - The form event
     */
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault(); // Prevent default form submission behavior
        setError(null); // Clear any previous errors
        setIsLoading(true); // Set loading state to true

        try {
            // Attempt to send a password reset request
            await requestPasswordReset(email);
            setSuccess(true); // Set success state to true if request succeeds
        } catch (err: any) {
            // Handle errors and set error message
            setError(err.message || "Wystąpił błąd podczas wysyłania linku resetującego hasło.");
        } finally {
            setIsLoading(false); // Reset loading state
        }
    };

    // Render success message if the password reset request was successful
    if (success) {
        return (
            <div
                className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded relative"
                role="alert"
            >
                <p className="font-medium">Link do resetowania hasła został wysłany!</p>
                <p className="text-sm">
                    Sprawdź swoją skrzynkę mailową i kliknij na link, aby zresetować hasło.
                </p>
            </div>
        );
    }

    // Render the main form UI
    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            {/* Display error message if an error occurs */}
            {error && (
                <div
                    className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative"
                    role="alert"
                >
                    <p className="font-medium">Błąd</p>
                    <p className="text-sm">{error}</p>
                </div>
            )}

            {/* Email input field */}
            <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-medium">
                    Email
                </Label>
                <Input
                    id="email"
                    type="email"
                    value={email} // Bind input value to email state
                    onChange={(e) => setEmail(e.target.value)} // Update email state on input change
                    placeholder="nazwa@example.com"
                    required // Make the input field required
                    className="w-full h-10 px-3 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <p className="text-xs text-muted-foreground">
                    Podaj adres email powiązany z Twoim kontem.
                </p>
            </div>

            {/* Submit button */}
            <Button
                type="submit"
                disabled={isLoading || !email.trim()} // Disable button if loading or email is empty
                className="w-full h-10 bg-primary hover:bg-primary/90 text-white rounded-md transition-colors"
            >
                {isLoading ? "Wysyłanie..." : "Resetuj hasło"} {/* Show loading text if isLoading is true */}
            </Button>
        </form>
    );
}