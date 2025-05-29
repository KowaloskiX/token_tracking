import Link from "next/link";
import { Button } from "../ui/button";

export default function ContactCtaSection() {
  return (
    <div className="">
      <div className="mx-auto max-w-7xl py-24 sm:px-6 sm:py-32 lg:px-8">
        <div className="relative isolate overflow-hidden bg-secondary border border-secondary-border px-6 py-24 text-center sm:rounded-lg sm:px-16">
          <h2 className="text-balance text-4xl tracking-tight text-foreground sm:text-5xl">
            Zacznij automatyzację z AI już dziś
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-pretty text-lg/8 text-body-text">
            Postaw na przyszłość swojej firmy i zyskaj przewagę konkurencyjną dzięki Asystentom AI, rosnąc wraz z rozwojem technologii.
          </p>
          <div className="mt-10 flex items-center justify-center gap-x-6">
            <Button asChild>
              <Link href="/kontakt/product-question">
                Skontaktuj się
              </Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href="/">
                Dowiedz się więcej <span aria-hidden="true">→</span>
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
