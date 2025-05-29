import Image from "next/image";
import CustomerLogos from "../CustomerLogos";

export default function SolutionHero({ 
  subtitle,
  title,
  description,
  imageSrc,
  imageAlt = "App screenshot",
  showCustomerLogos = true
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
