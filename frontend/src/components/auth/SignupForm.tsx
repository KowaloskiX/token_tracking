"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Icons } from "@/components/ui/icons"
import { motion, AnimatePresence } from "framer-motion"
import { useRouter } from "next/navigation"
import { registerUser } from "@/utils/userActions"
import { toast } from "@/hooks/use-toast"
import { useDashboard } from "@/context/DashboardContext"
import { createCheckoutSession } from '@/utils/stripe'
import { initializeGoogleAuth, handleGoogleSignIn, renderGoogleButton } from "@/utils/googleAuth"

type SignupFormProps = React.HTMLAttributes<HTMLDivElement>

interface FormErrors {
  email: string
  name: string
  password: string
}

const fadeInUp = {
  initial: { 
    opacity: 0,
    y: 20
  },
  animate: { 
    opacity: 1,
    y: 0
  },
  exit: { 
    opacity: 0,
    y: -20
  },
  transition: {
    duration: 0.3
  }
}

export function SignupForm({ className, ...props }: SignupFormProps) {
  const [isLoading, setIsLoading] = React.useState<boolean>(false)
  const [isRedirecting, setIsRedirecting] = React.useState<boolean>(false)
  const [step, setStep] = React.useState<number>(1)
  const [fieldsTouched, setFieldsTouched] = React.useState({
    email: false,
    name: false,
    password: false
  })
  const [formData, setFormData] = React.useState({
    email: '',
    name: '',
    password: ''
  })
  const [errors, setErrors] = React.useState<FormErrors>({
    email: '',
    name: '',
    password: ''
  })
  const { setUser } = useDashboard()

  const router = useRouter();

  const validateEmail = (email: string): string => {
    if (!email) return "Email jest wymagany"
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) return "Proszę podać prawidłowy adres email"
    return ""
  }

  const validateName = (name: string): string => {
    if (!name) return "Imię jest wymagane"
    if (name.length < 2) return "Imię musi mieć co najmniej 2 znaki"
    return ""
  }

  const validatePassword = (password: string): string => {
    if (!password) return "Hasło jest wymagane"
    if (password.length < 8) return "Hasło musi mieć co najmniej 8 znaków"
    if (!/(?=.*[A-Z])/.test(password)) return "Hasło musi zawierać co najmniej jedną wielką literę"
    if (!/(?=.*[0-9])/.test(password)) return "Hasło musi zawierać co najmniej jedną cyfrę"
    return ""
  }

  React.useEffect(() => {
    // Check if we're in a post-auth state AND have just completed Google auth
    const token = localStorage.getItem('token')
    const isPostGoogleAuth = localStorage.getItem('google_auth_in_progress')
    
    if (token && isPostGoogleAuth) {
      setIsRedirecting(true)
      setIsLoading(true)
      // Clear the flag
      localStorage.removeItem('google_auth_in_progress')
    }

    let isRedirectingAuth = false;
    
    const handleCallback = async (response: any) => {
      try {
        setIsLoading(true);
        setIsRedirecting(true);
        // Set a flag to indicate Google auth is in progress
        localStorage.setItem('google_auth_in_progress', 'true')
        
        const { user, access_token } = await handleGoogleSignIn(response);
        localStorage.setItem('token', access_token);
        setUser(user);
        
        const intendedPlan = localStorage.getItem('intended_plan');
        isRedirectingAuth = true;
        
        if (intendedPlan) {
          const { frequency, tierId } = JSON.parse(intendedPlan);
          localStorage.removeItem('intended_plan');
          
          const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/stripe/prices`);
          if (!response.ok) {
            throw new Error('Failed to fetch price IDs');
          }
          const priceIds = await response.json();
          
          const priceId = frequency === 'monthly' ? priceIds.monthly : priceIds.annual;
          const origin = window.location.origin;
          
          await createCheckoutSession(
            priceId,
            frequency,
            `${origin}/dashboard/tenderschat`,
            `${origin}/dashboard/tenders/chat?error=payment`
          );
        } else {
          window.location.href = '/dashboard/tenders/chat';
        }

        toast({
          title: "Zalogowano pomyślnie!",
          description: "Zostałeś automatycznie zalogowany.",
          variant: "default",
        });
        setTimeout(() => {
            setIsRedirecting(false);
        }, 2000);
      } catch (error) {
        console.error('Google auth error:', error);
        setIsRedirecting(false);
        setIsLoading(false);
        localStorage.removeItem('google_auth_in_progress')
        toast({
          title: "Błąd logowania",
          description: error instanceof Error ? error.message : "Wystąpił błąd podczas logowania przez Google",
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
          
          const googleButton = document.getElementById('googleButtonSignup');
          if (googleButton) {
            renderGoogleButton("googleButtonSignup");
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
        const googleButton = document.getElementById('googleButtonSignup');
        if (googleButton) {
          renderGoogleButton("googleButtonSignup");
        }
      }
    } else {
      loadGoogleScript();
    }

    return () => {
      const googleButton = document.getElementById('googleButtonSignup');
      if (!isRedirecting && googleButton) {
        while (googleButton.firstChild) {
          googleButton.removeChild(googleButton.firstChild);
        }
      }
      if (window.google?.accounts?.id) {
        window.google.accounts.id.cancel();
      }
      // Clean up the flag on unmount if not redirecting
      if (!isRedirectingAuth) {
        localStorage.removeItem('google_auth_in_progress')
      }
    };
  }, [router, setUser]);

  // Show loading state if redirecting
  if (isRedirecting) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="flex flex-col items-center gap-2">
          <Icons.spinner className="h-8 w-8 animate-spin" />
          <p className="text-sm text-muted-foreground">
            Przekierowywanie...
          </p>
        </div>
      </div>
    )
  }

  async function onSubmit(event: React.SyntheticEvent) {
    event.preventDefault()
    
    let currentError = ""
    
    switch (step) {
      case 1:
        setFieldsTouched(prev => ({ ...prev, email: true }))
        currentError = validateEmail(formData.email)
        setErrors(prev => ({ ...prev, email: currentError }))
        if (currentError) return
        break
      case 2:
        setFieldsTouched(prev => ({ ...prev, name: true }))
        currentError = validateName(formData.name)
        setErrors(prev => ({ ...prev, name: currentError }))
        if (currentError) return
        break
      case 3:
        setFieldsTouched(prev => ({ ...prev, password: true }))
        currentError = validatePassword(formData.password)
        setErrors(prev => ({ ...prev, password: currentError }))
        if (currentError) return
        break
    }

    if (step < 3) {
      setStep(step + 1)
      return
    }

    setIsLoading(true);
    try {
      const result = await registerUser({
        email: formData.email,
        name: formData.name,
        password: formData.password,
        org_id: "", 
        role: "member" 
      });
      
      localStorage.setItem('token', result.access_token);
      setUser(result.user);
      
      toast({
        title: "Konto utworzone pomyślnie!",
        description: "Zostałeś automatycznie zalogowany.",
        variant: "default",
      });
      
      const intendedPlan = localStorage.getItem('intended_plan');
      if (intendedPlan) {
        const { frequency, tierId } = JSON.parse(intendedPlan);
        localStorage.removeItem('intended_plan');
        
        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/stripe/prices`);
        if (!response.ok) {
          throw new Error('Failed to fetch price IDs');
        }
        const priceIds = await response.json();
        
        const priceId = frequency === 'monthly' ? priceIds.monthly : priceIds.annual;
        const origin = window.location.origin;
        
        await createCheckoutSession(
          priceId,
          frequency,
          `${origin}/dashboard/tenders/chat`,
          `${origin}/oferta?canceled=true`
        );
      } else {
        router.push('/dashboard/tenders/chat');
      }
    } catch (error) {
      console.error('Registration error:', error);
      toast({
        title: "Błąd rejestracji",
        description: error instanceof Error ? error.message : "Wystąpił nieoczekiwany błąd",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
    
    if (fieldsTouched[name as keyof typeof fieldsTouched]) {
      switch (name) {
        case 'email':
          setErrors(prev => ({ ...prev, email: validateEmail(value) }))
          break
        case 'name':
          setErrors(prev => ({ ...prev, name: validateName(value) }))
          break
        case 'password':
          setErrors(prev => ({ ...prev, password: validatePassword(value) }))
          break
      }
    }
  }
  
  
    const renderCurrentStep = () => {
      switch (step) {
        case 1:
          return (
            <motion.div
              key="email-step"
              {...fadeInUp}
              className="grid gap-1"
            >
              <Label className="sr-only" htmlFor="email">
                Email
              </Label>
              <Input
                id="email"
                name="email"
                placeholder="twoj@email.pl"
                type="email"
                autoCapitalize="none"
                autoComplete="email"
                autoCorrect="off"
                disabled={isLoading}
                value={formData.email}
                onChange={handleInputChange}
                className={fieldsTouched.email && errors.email ? "border-red-500" : " border-secondary-border border-2"}
              />
              {fieldsTouched.email && errors.email && (
                <motion.p 
                  initial={{ opacity: 0 }} 
                  animate={{ opacity: 1 }} 
                  className="text-red-500 text-sm"
                >
                  {errors.email}
                </motion.p>
              )}
            </motion.div>
          )
        case 2:
          return (
            <motion.div
              key="name-step"
              {...fadeInUp}
              className="grid gap-1"
            >
              <Label className="sr-only" htmlFor="name">
                Imię
              </Label>
              <Input
                id="name"
                name="name"
                placeholder="Twoje imię"
                type="text"
                autoCapitalize="none"
                autoCorrect="off"
                disabled={isLoading}
                value={formData.name}
                onChange={handleInputChange}
                className={fieldsTouched.name && errors.name ? "border-red-500" : ""}
              />
              {fieldsTouched.name && errors.name && (
                <motion.p 
                  initial={{ opacity: 0 }} 
                  animate={{ opacity: 1 }} 
                  className="text-red-500 text-sm"
                >
                  {errors.name}
                </motion.p>
              )}
            </motion.div>
          )
        case 3:
          return (
            <motion.div
              key="password-step"
              {...fadeInUp}
              className="grid gap-1"
            >
              <Label className="sr-only" htmlFor="password">
                Hasło
              </Label>
              <Input
                id="password"
                name="password"
                placeholder="Utwórz hasło"
                type="password"
                autoCapitalize="none"
                autoComplete="new-password"
                autoCorrect="off"
                disabled={isLoading}
                value={formData.password}
                onChange={handleInputChange}
                className={fieldsTouched.password && errors.password ? "border-red-500" : ""}
              />
              {fieldsTouched.password && errors.password && (
                <motion.p 
                  initial={{ opacity: 0 }} 
                  animate={{ opacity: 1 }} 
                  className="text-red-500 text-sm"
                >
                  {errors.password}
                </motion.p>
              )}
            </motion.div>
          )
      }
    }

  const getButtonText = () => {
    if (isLoading) return "Tworzenie konta..."
    if (step === 1) return "Kontynuuj"
    if (step === 2) return "Kontynuuj"
    return "Utwórz konto"
  }

  return (
    <div className={cn("grid gap-6 relative", className)} {...props}>
      <form onSubmit={onSubmit}>
        <div className="grid gap-2">
          <AnimatePresence mode="wait">
            {renderCurrentStep()}
          </AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Button disabled={isLoading} className="w-full cursor-pointer">
              {isLoading && (
                <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
              )}
              {getButtonText()}
            </Button>
          </motion.div>
        </div>
      </form>
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className="relative"
      >
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">
            Lub
          </span>
        </div>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, delay: 0.1 }}
        className="flex flex-col gap-4 justify-center items-center w-full"
      >
        <div
          id="googleButtonSignup"
          data-scope="openid email profile"
          onClick={(e) => {
            e.preventDefault();
            window.google?.accounts.id.prompt();
          }}
        />
      </motion.div>
    </div>
  )
}