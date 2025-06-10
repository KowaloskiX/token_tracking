"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { useTranslations } from 'next-intl'
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
      message: "Name must be at least 2 characters.",
    })
    .max(30, {
      message: "Name must not be longer than 30 characters.",
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
  const [mounted, setMounted] = useState(false)
  
  // API Key states
  const [apiKeyInfo, setApiKeyInfo] = useState<ApiKeyInfo | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [generatedApiKey, setGeneratedApiKey] = useState<string | null>(null)
  const [apiKeyPassword, setApiKeyPassword] = useState("")
  const [revokeApiKeyPassword, setRevokeApiKeyPassword] = useState("")
  const [isLoadingApiKey, setIsLoadingApiKey] = useState(false)
  const [isGeneratingApiKey, setIsGeneratingApiKey] = useState(false)
  const [isRevokingApiKey, setIsRevokingApiKey] = useState(false)
  
  const t = useTranslations('settings.profile')
  const router = useRouter()

  useEffect(() => {
    setMounted(true)
    loadApiKeyInfo()
  }, [])

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: {
      name: user?.name || "",
    },
  })

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
        title: t('success'),
        description: "Your profile has been updated successfully.",
      })
    } catch (error) {
      toast({
        title: t('error'),
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
      
      localStorage.removeItem('token');
      
      toast({
        title: t('account_deleted'),
        description: t('account_deleted_description'),
      });

      router.push('/');
    } catch (error) {
      console.error('Account deletion error:', error);
      toast({
        title: t('error'),
        description: "Failed to delete account. Please try again.",
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
        title: t('error'),
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
        title: t('error'),
        description: "Passwords do not match.",
        variant: "destructive",
      });
      return;
    }
    
    if (newPassword.length < 8) {
      toast({
        title: t('error'),
        description: "New password must be at least 8 characters long.",
        variant: "destructive",
      });
      return;
    }
    
    setIsChangingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      
      toast({
        title: t('success'),
        description: t('password_changed'),
      });
    } catch (error: any) {
      toast({
        title: t('error'),
        description: error.message || t('password_change_error'),
        variant: "destructive",
      });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleGenerateApiKey = async () => {
    if (!apiKeyPassword) {
      toast({
        title: t('error'),
        description: "Please enter your account password.",
        variant: "destructive",
      });
      return;
    }

    setIsGeneratingApiKey(true);
    try {
      const isPasswordValid = await verifyPassword(apiKeyPassword);
      if (!isPasswordValid) {
        toast({
          title: t('error'),
          description: "Invalid password.",
          variant: "destructive",
        });
        return;
      }

      const response = await generateApiKey();
      setGeneratedApiKey(response.api_key);
      setShowApiKey(true);
      setApiKeyPassword("");
      
      await loadApiKeyInfo();
      
      toast({
        title: t('success'),
        description: "API key has been generated successfully.",
      });
    } catch (error: any) {
      toast({
        title: t('error'),
        description: error.message || "Failed to generate API key.",
        variant: "destructive",
      });
    } finally {
      setIsGeneratingApiKey(false);
    }
  };

  const handleRevokeApiKey = async () => {
    if (!revokeApiKeyPassword) {
      toast({
        title: t('error'),
        description: "Please enter your account password.",
        variant: "destructive",
      });
      return;
    }

    setIsRevokingApiKey(true);
    try {
      const isPasswordValid = await verifyPassword(revokeApiKeyPassword);
      if (!isPasswordValid) {
        toast({
          title: t('error'),
          description: "Invalid password.",
          variant: "destructive",
        });
        return;
      }

      await revokeApiKey();
      setGeneratedApiKey(null);
      setShowApiKey(false);
      setRevokeApiKeyPassword("");
      
      await loadApiKeyInfo();
      
      toast({
        title: t('success'),
        description: "API key has been revoked.",
      });
    } catch (error: any) {
      toast({
        title: t('error'),
        description: error.message || "Failed to revoke API key.",
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
        title: t('copied'),
        description: t('copied_description'),
      });
    }
  };

  if (!mounted) {
    return (
      <div className="space-y-8 pb-20">
        <div className="text-sm text-muted-foreground">{t('loading')}</div>
      </div>
    );
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
              {t('enterprise_plan')}
            </h3>
          </div>
          <Button
            onClick={handleBillingPortal}
            disabled={isManagingSubscription || !user?.subscription?.stripe_customer_id}
            className="flex items-center gap-2 w-[200px]"
          >
            <CreditCard className="h-4 w-4" />
            {isManagingSubscription ? t('loading') : t('manage_subscription')}
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
                <h3 className="font-medium text-sm">{t('name')}</h3>
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input placeholder="Your name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Email Field */}
              <div className="space-y-2">
                <h3 className="font-medium text-sm">{t('email')}</h3>
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
                {isLoading ? t('updating') : t('save')}
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
            <h3 className="font-medium text-sm">{t('api_key')}</h3>
          </div>
          
          <div className="bg-secondary border border-accent rounded-lg p-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-accent mt-0.5" />
              <div className="text-sm text-primary">
                <p className="font-medium mb-1">{t('api_key_info')}</p>
                <ul className="list-disc list-inside space-y-1">
                  {t.raw('api_key_security_rules').map((rule: string, index: number) => (
                    <li key={index}>{rule}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {apiKeyInfo?.has_api_key ? (
            <div className="space-y-4">
              <div className="bg-secondary border border-accent rounded-lg p-4">
                <p className="text-sm text-primary">
                  ✓ {t('active_api_key')} {apiKeyInfo.created_at ? format(new Date(apiKeyInfo.created_at), 'd MMMM yyyy') : 'N/A'}
                  {apiKeyInfo.last_used && (
                    <span className="block mt-1">
                      {t('last_used')}: {format(new Date(apiKeyInfo.last_used), 'd MMMM yyyy, HH:mm')}
                    </span>
                  )}
                </p>
              </div>
              
              {showApiKey && generatedApiKey && (
                <div className="space-y-2">
                  <Label>{t('your_api_key')}</Label>
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
                    {t('api_key_warning')}
                  </p>
                </div>
              )}

              <div className="flex gap-2">
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline">
                      {t('generate_new_key')}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t('generate_new_key')}?</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('generate_new_key_warning')}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <div className="space-y-2">
                      <Label htmlFor="api-key-password">{t('confirm_password')}</Label>
                      <Input
                        id="api-key-password"
                        type="password"
                        value={apiKeyPassword}
                        onChange={(e) => setApiKeyPassword(e.target.value)}
                        placeholder={t('enter_password')}
                      />
                    </div>
                    <AlertDialogFooter>
                      <AlertDialogCancel onClick={() => setApiKeyPassword("")}>
                        {t('cancel')}
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleGenerateApiKey}
                        disabled={isGeneratingApiKey || !apiKeyPassword}
                      >
                        {isGeneratingApiKey ? t('generating') : t('generate_api_key')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" disabled={isRevokingApiKey}>
                      {isRevokingApiKey ? t('deactivating') : t('deactivate_key')}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t('deactivate_key')}?</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('deactivate_key_warning')}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <div className="space-y-2">
                      <Label htmlFor="revoke-api-key-password">{t('confirm_password')}</Label>
                      <Input
                        id="revoke-api-key-password"
                        type="password"
                        value={revokeApiKeyPassword}
                        onChange={(e) => setRevokeApiKeyPassword(e.target.value)}
                        placeholder={t('enter_password')}
                      />
                    </div>
                    <AlertDialogFooter>
                      <AlertDialogCancel onClick={() => setRevokeApiKeyPassword("")}>
                        {t('cancel')}
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleRevokeApiKey}
                        disabled={isRevokingApiKey || !revokeApiKeyPassword}
                        className="bg-destructive hover:bg-destructive/90"
                      >
                        {isRevokingApiKey ? t('revoking') : t('revoke_key')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t('no_api_key')}
              </p>
              
              <div className="space-y-2">
                <Label htmlFor="new-api-key-password">{t('confirm_password')}</Label>
                <Input
                  id="new-api-key-password"
                  type="password"
                  value={apiKeyPassword}
                  onChange={(e) => setApiKeyPassword(e.target.value)}
                  placeholder={t('enter_password')}
                />
              </div>
              
              <Button
                onClick={handleGenerateApiKey}
                disabled={isGeneratingApiKey || !apiKeyPassword}
                className="w-[200px]"
              >
                {isGeneratingApiKey ? t('generating') : t('generate_key')}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Change Password Section - only show for non-Google users */}
      {!user?.google_id && (
        <div className="bg-card rounded-lg border p-6">
          <h3 className="font-medium text-sm mb-4">{t('change_password')}</h3>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">{t('current_password')}</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">{t('new_password')}</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                {t('password_requirements')}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">{t('confirm_new_password')}</Label>
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
              {isChangingPassword ? t('updating') : t('change_password')}
            </Button>
          </div>
        </div>
      )}

      {/* Account Info */}
      <div className="bg-secondary/20 p-4 rounded-lg">
        <p className="text-sm text-muted-foreground">
          {t('created_account')}: {user?.created_at ? format(new Date(user.created_at), 'd MMMM yyyy') : 'N/A'}
        </p>
      </div>

      {/* Delete Account Section */}
      <div className="border-t pt-6 mt-6">
        <h3 className="text-lg font-medium text-destructive mb-4">{t('danger_zone')}</h3>
        <p className="text-sm text-muted-foreground mb-4">
          {t('delete_account_warning')}
        </p>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button 
              variant="destructive"
              disabled={isDeletingAccount}
              className="w-[200px]"
            >
              {isDeletingAccount ? t('deleting') : t('delete_account')}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('delete_account_confirmation')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('delete_account_description')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteAccount}
                className="bg-destructive hover:bg-destructive/90"
              >
                {t('delete_account')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}