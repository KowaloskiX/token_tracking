"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { toast } from "@/hooks/use-toast"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useDashboard } from "@/context/DashboardContext"
import { updateUserProfile } from "@/utils/userActions"
import { useState, useEffect } from "react"
import { format } from "date-fns"
import { Sparkles, CreditCard, Key, Copy, AlertTriangle } from "lucide-react"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { useRouter } from "next/navigation"
import { deleteUserAccount } from "@/utils/userActions"
import { Label } from "@/components/ui/label"
import { changePassword } from "@/utils/userActions"
import { getApiKeyInfo, generateApiKey, revokeApiKey, verifyPassword, type ApiKeyInfo } from "@/utils/apiKeyActions"

const profileFormSchema = z.object({
  name: z
    .string()
    .min(2, {
      message: "Imię musi mieć co najmniej 2 znaki.",
    })
    .max(30, {
      message: "Imię nie może być dłuższe niż 30 znaków.",
    }),
})

type ProfileFormValues = z.infer<typeof profileFormSchema>

export function ProfileForm() {
  const { user, setUser } = useDashboard()
  const [isLoading, setIsLoading] = useState(false)
  const [isDeletingAccount, setIsDeletingAccount] = useState(false)
  const [isManagingSubscription, setIsManagingSubscription] = useState(false)
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  
  // API Key states
  const [apiKeyInfo, setApiKeyInfo] = useState<ApiKeyInfo | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [generatedApiKey, setGeneratedApiKey] = useState<string | null>(null)
  const [apiKeyPassword, setApiKeyPassword] = useState("")
  const [revokeApiKeyPassword, setRevokeApiKeyPassword] = useState("")
  const [isLoadingApiKey, setIsLoadingApiKey] = useState(false)
  const [isGeneratingApiKey, setIsGeneratingApiKey] = useState(false)
  const [isRevokingApiKey, setIsRevokingApiKey] = useState(false)
  
  const router = useRouter()

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: {
      name: user?.name || "",
    },
  })

  // Load API key info on component mount
  useEffect(() => {
    loadApiKeyInfo()
  }, [])

  const loadApiKeyInfo = async () => {
    try {
      const info = await getApiKeyInfo()
      setApiKeyInfo(info)
    } catch (error) {
      console.error('Error loading API key info:', error)
    }
  }

  // Get user initials for avatar
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(word => word[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  async function onSubmit(data: ProfileFormValues) {
    if (!user?._id) return

    setIsLoading(true)
    try {
      const updatedUser = await updateUserProfile(user._id, { name: data.name })
      setUser({ ...user, ...updatedUser })
      toast({
        title: "Profile updated",
        description: "Your profile has been updated successfully.",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update profile. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (!user?._id) return;

    setIsDeletingAccount(true);
    try {
      await deleteUserAccount(user._id);
      
      // Clear local storage
      localStorage.removeItem('token');
      
      // Show success message
      toast({
        title: "Konto usunięte",
        description: "Twoje konto zostało pomyślnie usunięte.",
      });

      // Redirect to home page
      router.push('/');
    } catch (error) {
      console.error('Account deletion error:', error);
      toast({
        title: "Błąd",
        description: "Nie udało się usunąć konta. Spróbuj ponownie.",
        variant: "destructive",
      });
    } finally {
      setIsDeletingAccount(false);
    }
  };

  const handleBillingPortal = async () => {
    try {
      if (!user?.subscription?.stripe_customer_id) {
        toast({
          title: "No subscription found",
          description: "You don't have an active subscription to manage.",
          variant: "destructive",
        })
        return
      }

      setIsManagingSubscription(true)
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/stripe/create-portal-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          customer_id: user.subscription.stripe_customer_id,
          return_url: `${window.location.origin}/dashboard/settings`
        })
      })

      if (!response.ok) {
        throw new Error('Failed to create portal session')
      }

      const { url } = await response.json()
      window.location.href = url
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to open subscription management. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsManagingSubscription(false)
    }
  }

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast({
        title: "Błąd",
        description: "Hasła nie są identyczne.",
        variant: "destructive",
      });
      return;
    }
    
    if (newPassword.length < 8) {
      toast({
        title: "Błąd",
        description: "Nowe hasło musi mieć co najmniej 8 znaków.",
        variant: "destructive",
      });
      return;
    }
    
    setIsChangingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      
      // Clear form fields
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      
      toast({
        title: "Sukces",
        description: "Twoje hasło zostało pomyślnie zmienione.",
      });
    } catch (error: any) {
      toast({
        title: "Błąd",
        description: error.message || "Nie udało się zmienić hasła. Spróbuj ponownie.",
        variant: "destructive",
      });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleGenerateApiKey = async () => {
    if (!apiKeyPassword) {
      toast({
        title: "Błąd",
        description: "Wprowadź hasło do swojego konta.",
        variant: "destructive",
      });
      return;
    }

    setIsGeneratingApiKey(true);
    try {
      // First verify password
      const isPasswordValid = await verifyPassword(apiKeyPassword);
      if (!isPasswordValid) {
        toast({
          title: "Błąd",
          description: "Nieprawidłowe hasło.",
          variant: "destructive",
        });
        return;
      }

      // Generate API key
      const response = await generateApiKey();
      setGeneratedApiKey(response.api_key);
      setShowApiKey(true);
      setApiKeyPassword("");
      
      // Reload API key info
      await loadApiKeyInfo();
      
      toast({
        title: "Sukces",
        description: "Klucz API został wygenerowany pomyślnie.",
      });
    } catch (error: any) {
      toast({
        title: "Błąd",
        description: error.message || "Nie udało się wygenerować klucza API.",
        variant: "destructive",
      });
    } finally {
      setIsGeneratingApiKey(false);
    }
  };

  const handleRevokeApiKey = async () => {
    if (!revokeApiKeyPassword) {
      toast({
        title: "Błąd",
        description: "Wprowadź hasło do swojego konta.",
        variant: "destructive",
      });
      return;
    }

    setIsRevokingApiKey(true);
    try {
      // First verify password
      const isPasswordValid = await verifyPassword(revokeApiKeyPassword);
      if (!isPasswordValid) {
        toast({
          title: "Błąd",
          description: "Nieprawidłowe hasło.",
          variant: "destructive",
        });
        return;
      }

      // Revoke API key
      await revokeApiKey();
      setGeneratedApiKey(null);
      setShowApiKey(false);
      setRevokeApiKeyPassword("");
      
      // Reload API key info
      await loadApiKeyInfo();
      
      toast({
        title: "Sukces",
        description: "Klucz API został odwołany.",
      });
    } catch (error: any) {
      toast({
        title: "Błąd",
        description: error.message || "Nie udało się odwołać klucza API.",
        variant: "destructive",
      });
    } finally {
      setIsRevokingApiKey(false);
    }
  };

  const copyApiKeyToClipboard = () => {
    if (generatedApiKey) {
      navigator.clipboard.writeText(generatedApiKey);
      toast({
        title: "Skopiowano",
        description: "Klucz API został skopiowany do schowka.",
      });
    }
  };

  const getSubscriptionStatus = () => {
    if (!user?.subscription) return "Darmowy Plan"
    return user.subscription.plan_type === 'standard' ? "Plan Standard" : "Darmowy Plan"
  }

  return (
    <div className="space-y-8 pb-20">
      {/* Avatar Section */}
      <div className="flex items-center gap-4">
        <Avatar className="h-16 w-16">
          <AvatarFallback className="text-base">
            {user?.name ? getInitials(user.name) : "??"}
          </AvatarFallback>
        </Avatar>
        <div>
          <h2 className="text-xl font-medium">{user?.name}</h2>
          <p className="text-muted-foreground">{user?.email}</p>
        </div>
      </div>

      {/* Subscription Section */}
      <div className="bg-secondary/20 p-4 rounded-lg space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h3 className="font-medium flex items-center gap-4">
              <Sparkles className="h-4 w-4" />
              Plan Enterprise
            </h3>
          </div>
          <Button
            onClick={handleBillingPortal}
            disabled={isManagingSubscription || !user?.subscription?.stripe_customer_id}
            className="flex items-center gap-2 w-[200px]"
          >
            <CreditCard className="h-4 w-4" />
            {isManagingSubscription ? "Ładowanie..." : "Zarządzaj Subskrypcją"}
          </Button>
        </div>
      </div>

      {/* Profile Fields Section */}
      <div className="bg-card rounded-lg border p-6">
        <div className="space-y-4">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
              {/* Name Field */}
              <div className="space-y-2">
                <h3 className="font-medium text-sm">Imię</h3>
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input placeholder="Twoje imię" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Email Field */}
              <div className="space-y-2">
                <h3 className="font-medium text-sm">Email</h3>
                <Input 
                  value={user?.email || ''} 
                  disabled 
                  className="w-full bg-muted cursor-not-allowed"
                />
              </div>

              {/* Save Button */}
              <Button 
                type="submit" 
                disabled={isLoading}
                className="w-[200px]"
              >
                {isLoading ? "Aktualizacja..." : "Zapisz"}
              </Button>
            </form>
          </Form>
        </div>
      </div>

      {/* API Key Management Section */}
      <div className="bg-card rounded-lg border p-6">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Key className="h-4 w-4" />
            <h3 className="font-medium text-sm">Klucz API</h3>
          </div>
          
          <div className="bg-secondary border border-accent rounded-lg p-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-accent mt-0.5" />
              <div className="text-sm text-primary">
                <p className="font-medium mb-1">Ważne informacje o bezpieczeństwie:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Nigdy nie udostępniaj swojego klucza API innym osobom</li>
                  <li>Nie umieszczaj klucza w publicznych repozytoriach kodu</li>
                  <li>Jeśli podejrzewasz kompromitację klucza, natychmiast go odwołaj</li>
                  <li>Klucz jest wyświetlany tylko raz - zapisz go w bezpiecznym miejscu</li>
                </ul>
              </div>
            </div>
          </div>

          {apiKeyInfo?.has_api_key ? (
            <div className="space-y-4">
              <div className="bg-secondary border border-accent rounded-lg p-4">
                <p className="text-sm text-primary">
                  ✓ Masz aktywny klucz API utworzony {apiKeyInfo.created_at ? format(new Date(apiKeyInfo.created_at), 'd MMMM yyyy') : 'N/A'}
                  {apiKeyInfo.last_used && (
                    <span className="block mt-1">
                      Ostatnio używany: {format(new Date(apiKeyInfo.last_used), 'd MMMM yyyy, HH:mm')}
                    </span>
                  )}
                </p>
              </div>
              
              {showApiKey && generatedApiKey && (
                <div className="space-y-2">
                  <Label>Twój klucz API:</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      type="text"
                      value={generatedApiKey}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={copyApiKeyToClipboard}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Ten klucz nie będzie więcej wyświetlony. Zapisz go w bezpiecznym miejscu.
                  </p>
                </div>
              )}

              <div className="flex gap-2">
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline">
                      Wygeneruj nowy klucz
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Wygenerować nowy klucz API?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Wygenerowanie nowego klucza spowoduje unieważnienie obecnego klucza. 
                        Wszystkie aplikacje używające starego klucza przestaną działać.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <div className="space-y-2">
                      <Label htmlFor="api-key-password">Potwierdź hasłem do konta:</Label>
                      <Input
                        id="api-key-password"
                        type="password"
                        value={apiKeyPassword}
                        onChange={(e) => setApiKeyPassword(e.target.value)}
                        placeholder="Wprowadź hasło"
                      />
                    </div>
                    <AlertDialogFooter>
                      <AlertDialogCancel onClick={() => setApiKeyPassword("")}>
                        Anuluj
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleGenerateApiKey}
                        disabled={isGeneratingApiKey || !apiKeyPassword}
                      >
                        {isGeneratingApiKey ? "Generowanie..." : "Wygeneruj nowy klucz"}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" disabled={isRevokingApiKey}>
                      {isRevokingApiKey ? "Dezaktywacja..." : "Dezaktywuj klucz"}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Dezaktywować klucz API?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Ta akcja jest nieodwracalna. Wszystkie aplikacje używające tego klucza 
                        przestaną działać natychmiast.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <div className="space-y-2">
                      <Label htmlFor="revoke-api-key-password">Potwierdź hasłem do konta:</Label>
                      <Input
                        id="revoke-api-key-password"
                        type="password"
                        value={revokeApiKeyPassword}
                        onChange={(e) => setRevokeApiKeyPassword(e.target.value)}
                        placeholder="Wprowadź hasło"
                      />
                    </div>
                    <AlertDialogFooter>
                      <AlertDialogCancel onClick={() => setRevokeApiKeyPassword("")}>
                        Anuluj
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleRevokeApiKey}
                        disabled={isRevokingApiKey || !revokeApiKeyPassword}
                        className="bg-destructive hover:bg-destructive/90"
                      >
                        {isRevokingApiKey ? "Odwoływanie..." : "Odwołaj klucz"}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Nie masz jeszcze klucza API. Wygeneruj go, aby móc korzystać z naszego API.
              </p>
              
              <div className="space-y-2">
                <Label htmlFor="new-api-key-password">Potwierdź hasłem do konta:</Label>
                <Input
                  id="new-api-key-password"
                  type="password"
                  value={apiKeyPassword}
                  onChange={(e) => setApiKeyPassword(e.target.value)}
                  placeholder="Wprowadź hasło"
                />
              </div>
              
              <Button
                onClick={handleGenerateApiKey}
                disabled={isGeneratingApiKey || !apiKeyPassword}
                className="w-[200px]"
              >
                {isGeneratingApiKey ? "Generowanie..." : "Wygeneruj klucz API"}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Change Password Section - only show for non-Google users */}
      {!user?.google_id && (
        <div className="bg-card rounded-lg border p-6">
          <h3 className="font-medium text-sm mb-4">Zmień hasło</h3>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">Obecne hasło</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">Nowe hasło</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                Hasło powinno zawierać minimum 8 znaków.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Potwierdź nowe hasło</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full"
              />
            </div>
            <Button
              onClick={handleChangePassword}
              disabled={isChangingPassword || !currentPassword || !newPassword || !confirmPassword || newPassword !== confirmPassword || newPassword.length < 8}
              className="w-[200px]"
            >
              {isChangingPassword ? "Aktualizacja..." : "Zmień hasło"}
            </Button>
          </div>
        </div>
      )}

      {/* Account Info */}
      <div className="bg-secondary/20 p-4 rounded-lg">
        <p className="text-sm text-muted-foreground">
          Konto utworzone: {user?.created_at ? format(new Date(user.created_at), 'd MMMM yyyy') : 'N/A'}
        </p>
      </div>

      {/* Delete Account Section */}
      <div className="border-t pt-6 mt-6">
        <h3 className="text-lg font-medium text-destructive mb-4">Strefa Niebezpieczna</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Po usunięciu konta nie ma możliwości jego przywrócenia. Proszę upewnij się przed wykonaniem tej operacji.
        </p>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button 
              variant="destructive"
              disabled={isDeletingAccount}
              className="w-[200px]"
            >
              {isDeletingAccount ? "Usuwanie..." : "Usuń Konto"}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Czy na pewno chcesz usunąć swoje konto?</AlertDialogTitle>
              <AlertDialogDescription>
                Ta akcja jest nieodwracalna. Spowoduje to trwałe usunięcie Twojego konta
                i wszystkich związanych z nim danych.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Anuluj</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteAccount}
                className="bg-destructive hover:bg-destructive/90"
              >
                Usuń Konto
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}