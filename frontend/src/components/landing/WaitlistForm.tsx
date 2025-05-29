"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { useToast } from "@/hooks/use-toast"
import { Input } from "../ui/input"
import { useState } from "react"
import { submitToWaitlist } from "@/utils/waitlistActions"
import { Loader2 } from "lucide-react"
import { Label } from "../ui/label"
import { revalidatePath } from "next/cache"

const waitlistFormSchema = z.object({
  email: z.string().min(1, { message: "To pole jest wymagane." }).email("Niepoprawny format adresu email."),
})

type WaitlistFormValues = z.infer<typeof waitlistFormSchema>;

const defaultValues: Partial<WaitlistFormValues> = {
  email: "",
}

export default function WaitlistForm() {
  const [isLoading, setIsLoading] = useState(false);

  const { toast } = useToast();

  const form = useForm<WaitlistFormValues>({
    resolver: zodResolver(waitlistFormSchema),
    defaultValues,
  })

  async function onSubmit(data: WaitlistFormValues) {
    setIsLoading(true);
    try {
      await submitToWaitlist(data.email);

      toast({
        title: "Sukces",
        description: "Pomyślnie dołączono do listy oczekujących!"
      });
      form.reset();
    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Wystąpił błąd",
        description: error.message || "Wystąpił błąd podczas zapisu"
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8 w-full flex flex-col justify-center items-center">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem className="w-full">
              <Label className="sr-only" htmlFor="email">
                Email
              </Label>
              <FormControl>
                <Input
                  id="email"
                  type="mail"
                  placeholder="mail@example.com"
                  className="w-full"
                  {...field}
                  required
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={isLoading} className="w-full">
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Ładowanie...
            </>
          ) : (
            'Dołącz do oczekujących'
          )}
        </Button>
      </form>
    </Form>
  )
}
