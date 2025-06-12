import { Metadata } from "next"
import Image from "next/image"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { AcceptInvitationForm } from "@/components/auth/AcceptInvitationForm"
import { useTranslations } from 'next-intl'
import { getTranslations } from 'next-intl/server'

/**
 * Generate dynamic metadata based on locale
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('auth.accept_invitation')
  
  return {
    title: t('page_title'),
    description: t('page_description'),
  }
}

/**
 * Viewport Configuration
 * Controls browser viewport settings like theme color for mobile browsers
 */
export const viewport = {
  themeColor: "#ffffff"
}

/**
 * Invitation Acceptance Page
 * 
 * This Server Component displays a form for users to accept an invitation to join an organization.
 * The component extracts the invitation token from URL parameters and passes it to the form.
 * If no token is provided, it displays an error message.
 * 
 * @param searchParams - Object containing URL query parameters
 * @returns The rendered page component
 */
export default async function AcceptInvitationPage({ 
  searchParams 
}: { 
  searchParams: any
}) {
  // Safely resolve searchParams in case it's a Promise
  const params = await Promise.resolve(searchParams);
  const token = params.token;
  
  // Get translations
  const t = await getTranslations('auth.accept_invitation')

  // Early return with error message if token is missing
  if (!token) {
    return (
      <div className="h-[100svh] flex items-center justify-center">
        <p className="text-red-500">{t('missing_token_error')}</p>
      </div>
    )
  }

  return (
    <div className="h-[100svh]">
      {/* Main container with responsive grid layout (1 column on mobile, 2 columns on desktop) */}
      <div className="container relative h-full flex-col items-center justify-center px-6 sm:px-0 md:grid lg:max-w-none lg:grid-cols-2 lg:px-0">
        {/* Login link in top-right corner */}
        <Link
          href="/dashboard/tenders"
          className={cn(
            buttonVariants({ variant: "ghost" }),
            "absolute right-4 top-4 md:right-8 md:top-8"
          )}
          aria-label={t('login_link')}
        >
          {t('login_link')}
        </Link>

        {/* Left sidebar with background image and testimonial (hidden on mobile) */}
        <div className="relative hidden h-full flex-col bg-muted p-10 text-white dark:border-r lg:flex">
          {/* Dark background overlay */}
          <div className="absolute inset-0 bg-zinc-900" />
          
          {/* Logo container with z-index to appear above background */}
          <div className="relative z-20 flex items-center text-lg font-medium">
            <Image 
              src="/images/asystent_ai_long.png"
              width={400}
              height={400}
              alt="Asystent AI Logo"
              className="w-auto h-8"
              priority // Prioritize loading this image
            />
          </div>
          
          {/* Background image with overlay and gradient */}
          <div className="absolute top-0 left-0 w-full h-full z-0">
            <div className="absolute w-full h-full bg-black bg-opacity-20"></div>
            <Image 
              src="/images/bonsai_tree.png"
              width={400}
              height={400}
              alt="Tło z drzewkiem bonsai"
              className="h-full w-full object-cover"
            />
            {/* Gradient overlay for better text readability */}
            <div className="absolute bottom-0 left-0 w-full h-64 bg-gradient-to-t from-black via-black/60 to-transparent"></div>
          </div>
          
          {/* Testimonial quote at bottom of sidebar */}
          <div className="relative z-20 mt-auto">
            <blockquote className="space-y-2 text-neutral-100">
              <p className="text-lg">
                &quot;{t('testimonial_quote')}&quot;
              </p>
              <footer className="text-sm">{t('testimonial_author')}</footer>
            </blockquote>
          </div>
        </div>

        {/* Right panel with the invitation acceptance form */}
        <div className="lg:p-8">
          <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
            {/* Page title and subtitle */}
            <div className="flex flex-col space-y-2 text-center">
              <h1 className="text-2xl font-semibold tracking-tight mt-28 sm:mt-0">
                {t('title')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('create_or_login_description')}
              </p>
            </div>
            
            {/* Invitation acceptance form component */}
            <AcceptInvitationForm token={token} />
            
            {/* Terms and privacy policy acceptance text */}
            <p className="px-8 text-center text-sm text-muted-foreground">
              {t('terms_acceptance')}{" "}
              <Link
                href="/documents/Polityka_Prywatności.pdf"
                className="underline underline-offset-4 hover:text-primary"
              >
                {t('terms_link')}
              </Link>{" "}
              {t('and')}{" "}
              <Link
                href="/documents/Polityka_Prywatności.pdf"
                className="underline underline-offset-4 hover:text-primary"
              >
                {t('privacy_policy_link')}
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}