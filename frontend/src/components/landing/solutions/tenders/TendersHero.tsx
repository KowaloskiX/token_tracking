import Image from "next/image";
import Link from "next/link";
import CustomerLogos from "../../CustomerLogos";

export default function TendersHero({ 
  subtitle,
  title,
  description,
  imageSrc,
  imageAlt = "App screenshot"
}: any) {
  return (
    <div className="relative isolate py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-base font-medium text-body-text">{subtitle}</h2>
          <p className="mt-2 text-balance text-4xl tracking-tight text-foreground sm:text-5xl">
            {title}
          </p>
          <p className="mt-6 text-pretty text-lg text-body-text sm:text-xl/8">
            {description}
          </p>
          <div className="mt-10 flex flex-wrap gap-y-4 sm:gap-y-0 items-center justify-center gap-x-6">
                <Link
                  href="https://cal.com/asystent-ai/prezentacja-automatyzacji-przetargow"
                  className="rounded-md bg-primary px-12 w-full sm:w-auto sm:px-20 py-2.5 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  Umów demo
                </Link>
                <Link
                  href="/kontakt/product-question"
                  className="rounded-md bg-secondary w-full sm:w-auto hover:bg-secondary-hover border border-secondary-border px-12 sm:px-20 py-2.5 text-sm font-medium text-foreground shadow-sm hover:shadow-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  Skontaktuj się z nami
                </Link>
          </div>
        </div>
      </div>
      <div className="relative overflow-hidden pt-16">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <Image
            alt={imageAlt}
            src={imageSrc}
            width={2432}
            height={1442}
            className="mb-[-12%] rounded-xl shadow-2xl ring-8 ring-secondary"
          />
          <div aria-hidden="true" className="relative">
            <div className="absolute -inset-x-20 bottom-0 bg-gradient-to-t from-background pt-[7%]" />
          </div>
        </div>
      </div>
      <CustomerLogos />
    </div>
  )
}
