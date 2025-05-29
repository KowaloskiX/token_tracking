import Link from "next/link";

export default function PresentationCTA() {
    return (
      <div className="">
        <div className="mx-auto max-w-7xl py-24 sm:px-6 sm:py-32 lg:px-8">
          <div className="relative isolate overflow-hidden bg-secondary border border-secondary-border px-6 py-24 text-center sm:rounded-lg sm:px-16">
            <h2 className="text-balance text-4xl tracking-tight text-foreground sm:text-5xl">
              Zyskaj przewagę z AI
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-pretty text-lg/8 text-body-text">
              Postaw na produktywną pracę wspartą sztuczną inteligencją.
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Link
                href="https://cal.com/asystent-ai/prezentacja-automatyzacji-przetargow"
                className="rounded-md bg-primary px-10 py-2.5 text-sm font-medium text-background shadow-sm hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
              >
                Umów demo
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }
  