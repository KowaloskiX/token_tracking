"use client"

import { useEffect } from "react"
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
  const form = useForm<NotificationsFormValues>({
    resolver: zodResolver(notificationsFormSchema),
    defaultValues: {
      communication_emails: user?.marketing_consent?.communication_emails ?? false,
      marketing_emails: user?.marketing_consent?.marketing_emails ?? false,
      social_emails: user?.marketing_consent?.social_emails ?? true,
      security_emails: true,
    },
  })

  async function onSubmit(data: NotificationsFormValues) {
    try {
      if (!user?._id) {
        toast({
          title: "Błąd",
          description: "Nie znaleziono użytkownika.",
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
        title: "Sukces",
        description: "Ustawienia powiadomień zostały zaktualizowane.",
      })
    } catch (error) {
      console.error("Błąd aktualizacji powiadomień:", error);
      toast({
        title: "Błąd",
        description: "Nie udało się zaktualizować ustawień powiadomień.",
        variant: "destructive",
      })
    }
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
                  <FormLabel className="text-base">Powiadomienia o koncie</FormLabel>
                  <FormDescription>
                    Otrzymuj wiadomości email dotyczące aktywności na Twoim koncie.
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
                  <FormLabel className="text-base">Wiadomości marketingowe</FormLabel>
                  <FormDescription>
                    Otrzymuj informacje o nowych produktach, funkcjach i innych nowościach.
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
                  <FormLabel className="text-base">Powiadomienia społecznościowe</FormLabel>
                  <FormDescription>
                    Otrzymuj powiadomienia o zaproszeniach do znajomych, obserwujących i innych aktywnościach.
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
                  <FormLabel className="text-base">Powiadomienia bezpieczeństwa</FormLabel>
                  <FormDescription>
                    Otrzymuj ważne powiadomienia dotyczące bezpieczeństwa Twojego konta.
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
          onClick={() => console.log("Przycisk kliknięty")}
        >
          Aktualizuj powiadomienia
        </Button>
      </form>
    </Form>
  )
}