import { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";

export const metadata: Metadata = {
    title: "Asystent AI - Resetowanie hasła",
    description: "Ustaw nowe hasło do swojego konta na platformie Asystent AI.",
};

export default async function ResetPasswordPage({ searchParams }: { searchParams: any }) {
    // Safely resolve searchParams in case it's a Promise, similar to accept-invitation/page.tsx.
    const params = await Promise.resolve(searchParams);
    const token = params.token;

    if (!token) {
        return (
            <div className="h-[100svh] flex items-center justify-center">
                <p className="text-red-500">Nieprawidłowy lub brakujący token resetowania hasła.</p>
            </div>
        );
    }

    return (
        <div className="h-[100svh]">
            {/* Main container */}
            <div className="container relative h-full flex-col items-center justify-center px-6 sm:px-0 md:grid lg:max-w-none lg:grid-cols-2 lg:px-0">
                {/* Login link in the top-right corner */}
                <Link
                    href="/dashboard/tenders/chat"
                    className={cn(
                        buttonVariants({ variant: "ghost" }),
                        "absolute right-4 top-4 md:right-8 md:top-8"
                    )}
                    aria-label="Przejdź do strony logowania"
                >
                    Zaloguj się
                </Link>

                {/* Left sidebar with background image (hidden on mobile) */}
                <div className="relative hidden h-full flex-col bg-muted p-10 text-white dark:border-r lg:flex">
                    {/* Dark background overlay */}
                    <div className="absolute inset-0 bg-zinc-900" />
                    
                    {/* Logo container */}
                    <div className="relative z-20 flex items-center text-lg font-medium">
                        <Image 
                            src="/images/asystent_ai_long.png"
                            width={400}
                            height={400}
                            alt="Asystent AI Logo"
                            className="w-auto h-8"
                            priority
                        />
                    </div>
                    
                    {/* Background image */}
                    <div className="absolute top-0 left-0 w-full h-full z-0">
                        {/* Semi-transparent overlay */}
                        <div className="absolute w-full h-full bg-black bg-opacity-20"></div>
                        <Image 
                            src="/images/bonsai_tree.png"
                            width={400}
                            height={400}
                            alt="Tło z drzewkiem bonsai"
                            className="h-full w-full object-cover"
                        />
                        {/* Gradient overlay at the bottom */}
                        <div className="absolute bottom-0 left-0 w-full h-64 bg-gradient-to-t from-black via-black/60 to-transparent"></div>
                    </div>
                    
                    {/* Testimonial quote */}
                    <div className="relative z-20 mt-auto">
                        <blockquote className="space-y-2 text-neutral-100">
                            <p className="text-lg">
                                &quot;Asystent AI totalnie zrewolucjonizował sposób, w jaki analizujemy przetargi.&quot;
                            </p>
                            <footer className="text-sm">Marcin Przybylski, Specjalista ds. Przetargów</footer>
                        </blockquote>
                    </div>
                </div>

                {/* Right panel with the form */}
                <div className="lg:p-8">
                    <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
                        {/* Page title and subtitle */}
                        <div className="flex flex-col space-y-2 text-center">
                            <h1 className="text-2xl font-semibold tracking-tight mt-28 sm:mt-0">
                                Resetowanie hasła
                            </h1>
                            <p className="text-sm text-muted-foreground">
                                Wprowadź nowe hasło dla swojego konta.
                            </p>
                        </div>
                        
                        {/* Password reset form */}
                        <ResetPasswordForm token={token} />
                    </div>
                </div>
            </div>
        </div>
    );
}