import { useEffect, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Loader2 } from "lucide-react"
import { useDashboard } from "@/context/DashboardContext"
import { Icons } from "../ui/icons"
import { loginUser } from "@/utils/userActions"
import { initializeGoogleAuth, handleGoogleSignIn, renderGoogleButton } from "@/utils/googleAuth"
import { toast } from "@/hooks/use-toast"
import { useRouter } from "next/navigation"
import { useAuthTranslations } from "@/hooks/useTranslations"

export default function LoginForm() {
  const { setUser } = useDashboard()
  const t = useAuthTranslations()
  const [isLoading, setIsLoading] = useState(false)
  const [isRedirecting, setIsRedirecting] = useState(false)
  const [formData, setFormData] = useState({
    email: "",
    password: "",
  })
  const router = useRouter()

  useEffect(() => {
    document.body.style.overflow = 'hidden'

    // Check if we're in a post-auth state AND have just completed Google auth
    const token = localStorage.getItem('token')
    const isPostGoogleAuth = localStorage.getItem('google_auth_in_progress')

    if (token && isPostGoogleAuth) {
      localStorage.removeItem('google_auth_in_progress')
      window.location.href = '/dashboard/tenders/chat';
    }

    const handleCallback = async (response: any) => {
      try {
        setIsLoading(true);
        setIsRedirecting(true);
        localStorage.setItem('google_auth_in_progress', 'true')

        const { user, access_token } = await handleGoogleSignIn(response);
        localStorage.setItem('token', access_token);
        setUser(user);

        toast({
          title: t('login.login_success'),
          description: t('login.login_success_desc'),
          variant: "default",
        });

        // Use window.location.href for a full page reload
        window.location.href = '/dashboard/tenders/chat';
      } catch (error) {
        console.error('Google auth error:', error);
        setIsRedirecting(false);
        setIsLoading(false);
        localStorage.removeItem('google_auth_in_progress')
        toast({
          title: t('login.login_error'),
          description: error instanceof Error ? error.message : t('login.login_error'),
          variant: "destructive",
        });
      }
    };

    // Load Google script and initialize
    const loadGoogleScript = () => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = () => {
        if (window.google) {
          initializeGoogleAuth(
            process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!,
            handleCallback
          );

          const googleButton = document.getElementById('googleButtonLogin');
          if (googleButton) {
            renderGoogleButton("googleButtonLogin");
          }
        }
      };
      document.body.appendChild(script);
    };

    // Check if script is already loaded
    if (document.querySelector('script[src="https://accounts.google.com/gsi/client"]')) {
      if (window.google) {
        initializeGoogleAuth(
          process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!,
          handleCallback
        );
        const googleButton = document.getElementById('googleButtonLogin');
        if (googleButton) {
          renderGoogleButton("googleButtonLogin");
        }
      }
    } else {
      loadGoogleScript();
    }

    return () => {
      document.body.style.overflow = 'unset'
      const googleButton = document.getElementById('googleButtonLogin');
      if (!isRedirecting && googleButton) {
        while (googleButton.firstChild) {
          googleButton.removeChild(googleButton.firstChild);
        }
      }
      if (window.google?.accounts?.id) {
        window.google.accounts.id.cancel();
      }
      if (!isRedirecting) {
        localStorage.removeItem('google_auth_in_progress')
      }
    };
  }, [router, setUser, t]);

  if (isRedirecting) {
    return (
      <div className="fixed top-0 left-0 z-[999] bg-black bg-opacity-50 backdrop-blur-sm flex h-screen w-full items-center justify-center px-4">
        <div className="flex flex-col items-center gap-2">
          <Icons.spinner className="h-8 w-8 animate-spin" />
          <p className="text-sm text-muted-foreground">
            {t('login.redirecting')}
          </p>
        </div>
      </div>
    )
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { id, value } = e.target
    setFormData(prev => ({
      ...prev,
      [id]: value
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const { user, token } = await loginUser(formData)
      localStorage.setItem('token', token)
      setUser(user)
      window.location.href = '/dashboard/tenders/chat';
      toast({
        title: t('login.login_success'),
        description: t('login.login_success_desc'),
        variant: "default",
      });
    } catch (error) {
      console.error('Login error:', error)
      
      // Check for inactive account (status code 403)
      if (error instanceof Error && error.message.includes('403')) {
        toast({
          title: t('login.account_deactivated'),
          description: t('login.account_deactivated_desc'),
          variant: "destructive",
        });
      } else {
        toast({
          title: t('login.login_error'),
          description: error instanceof Error ? error.message : t('login.login_error'),
          variant: "destructive",
        });
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed top-0 left-0 z-[999] bg-black bg-opacity-50 backdrop-blur-sm flex h-screen w-full items-center justify-center px-4">
      <Card className="mx-auto max-w-md px-4 py-2">
        <CardHeader>
          <CardTitle className="text-2xl">{t('login.title')}</CardTitle>
          <CardDescription>
            {t('login.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-4">
            <div className="grid gap-2">
              <label className="text-sm">{t('login.email')}</label>
              <Input
                id="email"
                type="email"
                placeholder={t('register.your_email')}
                required
                value={formData.email}
                onChange={handleChange}
                disabled={isLoading}
                className="w-full border-2 border-secondary-border shadow-inner"
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center">
                <label className="text-sm">{t('login.password')}</label>
                <Link
                  href="/forgot-password"
                  className="ml-auto inline-block text-xs underline"
                >
                  {t('login.forgot_password')}
                </Link>
              </div>
              <Input
                id="password"
                type="password"
                required
                placeholder="•••••••••"
                value={formData.password}
                onChange={handleChange}
                disabled={isLoading}
                className="w-full border-2 border-secondary-border shadow-inner"
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('login.logging_in')}
                </>
              ) : (
                t('login.submit')
              )}
            </Button>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">
                  {t('login.or')}
                </span>
              </div>
            </div>
            <div className="flex flex-col gap-4">
              <div
                id="googleButtonLogin"
                data-scope="openid email profile"
                className="w-full flex justify-center items-center [&>div]:w-full [&>div>div]:w-full [&>div>div>iframe]:w-full"
                onClick={(e) => {
                  e.preventDefault();
                  window.google?.accounts.id.prompt();
                }}
              />
            </div>
            <div className="mt-4 text-center text-sm">
              {t('login.no_account')}{" "}
              <Link href="/waitlist" className="underline">
                {t('login.sign_up')}
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}