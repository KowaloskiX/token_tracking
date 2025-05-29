
import { Metadata } from "next"
import Image from "next/image"
import Link from "next/link"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { SignupForm } from "../../../components/auth/SignupForm"

export const metadata: Metadata = {
  title: "Asystent AI - Rejestracja",
  description: "Utwórz nowe konto na platformie Asystent AI i rozpocznij przygodę ze sztuczną inteligencją.",
}

export default function AuthenticationPage() {
  return (
    <div className="h-[100svh]">
      <div className="container relative h-full flex-col items-center justify-center px-6 sm:px-0 md:grid lg:max-w-none lg:grid-cols-2 lg:px-0">
        <Link
          href="/dashboard/chat"
          className={cn(
            buttonVariants({ variant: "ghost" }),
            "absolute right-4 top-4 md:right-8 md:top-8"
          )}
        >
          Zaloguj się
        </Link>
        <div className="relative hidden h-full flex-col bg-muted p-10 text-white dark:border-r lg:flex">
          <div className="absolute inset-0 bg-zinc-900" />
          <div className="relative z-20 flex items-center text-lg font-medium">
            <Image 
                src="/images/asystent_ai_long.png"
                width={400}
                height={400}
                alt="Asystent AI Logo"
                className="w-auto h-8"
              />
          </div>
          <div className="absolute top-0 left-0 w-full h-full z-0">
            <div className="absolute w-full h-full bg-black bg-opacity-20"></div>
            <Image 
                src="/images/bonsai_tree.png"
                width={400}
                height={400}
                alt="Asystent AI Logo"
                className="h-full w-full object-cover"
            />
            {/* Added gradient overlay */}
            <div className="absolute bottom-0 left-0 w-full h-64 bg-gradient-to-t from-black via-black/60 to-transparent"></div>
          </div>
          <div className="relative z-20 mt-auto">
            <blockquote className="space-y-2 text-neutral-100">
              <p className="text-lg">
                &ldquo;Asystent AI totalnie zrewolucjonizował sposób, w jaki analizujemy przetargi. 
                Wcześniej spędzałem godziny na przeglądaniu setek dokumentów, teraz AI
                błyskawicznie znajduje najlepsze okazje i wskazuje kluczowe wymagania.&rdquo;
              </p>
              <footer className="text-sm">Marcin Przybylski, Specjalista ds. Przetargów</footer>
            </blockquote>
          </div>
        </div>
        <div className="lg:p-8">
          <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
            <div className="flex flex-col space-y-2 text-center">
              <h1 className="text-2xl font-semibold tracking-tight mt-28 sm:mt-0">
                Utwórz nowe konto
              </h1>
              <p className="text-sm text-muted-foreground">
                Wypełnij formularz aby się zarejestrować
              </p>
            </div>
            <SignupForm />
            <p className="px-8 text-center text-sm text-muted-foreground">
              Klikając kontynuuj, akceptujesz nasz{" "}
              <Link
                href="/documents/Polityka_Prywatności.pdf"
                className="underline underline-offset-4 hover:text-primary"
              >
                Regulamin
              </Link>{" "}
              oraz{" "}
              <Link
                href="/documents/Polityka_Prywatności.pdf"
                className="underline underline-offset-4 hover:text-primary"
              >
                Politykę Prywatności
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}