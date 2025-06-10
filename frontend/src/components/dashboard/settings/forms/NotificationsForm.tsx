"use client"

import { useEffect, useState } from "react"
import { useTranslations } from 'next-intl'
import { useDashboard } from "@/hooks/useDashboard"
import { updateMarketingConsent } from "@/utils/userActions"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { User } from "@/types"

import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel
} from "@/components/ui/form"
import { Switch } from "@/components/ui/switch"
import { toast } from "@/hooks/use-toast"

const notificationsFormSchema = z.object({
  communication_emails: z.boolean().default(false),
  marketing_emails: z.boolean().default(false),
  social_emails: z.boolean().default(true),
  security_emails: z.boolean().default(true),
})

type NotificationsFormValues = z.infer<typeof notificationsFormSchema>

export function NotificationsForm() {
  const { user, setUser } = useDashboard()
  const [mounted, setMounted] = useState(false)
  const t = useTranslations('settings.notifications')
  
  const form = useForm<NotificationsFormValues>({
    resolver: zodResolver(notificationsFormSchema),
    defaultValues: {
      communication_emails: user?.marketing_consent?.communication_emails ?? false,
      marketing_emails: user?.marketing_consent?.marketing_emails ?? false,
      social_emails: user?.marketing_consent?.social_emails ?? true,
      security_emails: true,
    },
  })

  useEffect(() => {
    setMounted(true)
  }, [])

  async function onSubmit(data: NotificationsFormValues) {
    try {
      if (!user?._id) {
        toast({
          title: t('error'),
          description: t('user_not_found'),
          variant: "destructive",
        })
        return;
      }

      await updateMarketingConsent(user._id, data);
      
      if (user) {
        const newUserData: User = {
          ...user,
          marketing_consent: data
        };
        setUser(newUserData);
      }

      toast({
        title: t('success'),
        description: t('success_description'),
      })
    } catch (error) {
      console.error("Error updating notifications:", error);
      toast({
        title: t('error'),
        description: t('error_description'),
        variant: "destructive",
      })
    }
  }

  if (!mounted) {
    return (
      <div className="space-y-6">
        <div className="text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <div className="space-y-4">
          <FormField
            control={form.control}
            name="communication_emails"
            render={({ field }) => (
              <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <FormLabel className="text-base">{t('account_notifications')}</FormLabel>
                  <FormDescription>
                    {t('account_notifications_description')}
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="marketing_emails"
            render={({ field }) => (
              <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <FormLabel className="text-base">{t('marketing_emails')}</FormLabel>
                  <FormDescription>
                    {t('marketing_emails_description')}
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="social_emails"
            render={({ field }) => (
              <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <FormLabel className="text-base">{t('social_notifications')}</FormLabel>
                  <FormDescription>
                    {t('social_notifications_description')}
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="security_emails"
            render={({ field }) => (
              <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <FormLabel className="text-base">{t('security_notifications')}</FormLabel>
                  <FormDescription>
                    {t('security_notifications_description')}
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    disabled
                    aria-readonly
                  />
                </FormControl>
              </FormItem>
            )}
          />
        </div>
        <Button 
          type="submit"
          onClick={() => console.log("Button clicked")}
        >
          {t('update_notifications')}
        </Button>
      </form>
    </Form>
  )
}