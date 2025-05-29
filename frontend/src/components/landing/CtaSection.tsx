import { PhoneCallIcon } from "lucide-react";
import Link from "next/link";
import { Button } from "../ui/button";

export default function CtaSection() {

  return (
    <div className="">
      <div className="mx-auto max-w-7xl py-24 sm:px-6 sm:py-32 lg:px-8">
        <div className="relative isolate overflow-hidden bg-secondary border border-secondary-border px-6 py-24 text-center sm:rounded-lg sm:px-16">
          <h2 className="text-balance text-4xl tracking-tight text-foreground sm:text-5xl">
            Zwieksz swoją produktywność już dzisiaj
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-pretty text-lg/8 text-body-text">
            Zacznij korzystać z osobistego Asystenta AI lub wdróż zastosowanie Biznes w Twojej organizacji, aby osiągać więcej każdego dnia.
          </p>
          <div className="mt-10 flex items-center justify-center gap-x-6">
            <Button asChild>
              <Link href="/waitlist">
                Dołącz do oczekujących
              </Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href="/kontakt/product-question">
                <PhoneCallIcon className="size-4" />
                Skontaktuj się
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
