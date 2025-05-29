import Image from "next/image";

export default function CustomerLogos() {
    return (
      <div className="hidden sm:block py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="flex justify-center gap-10 items-center w-full flex-wrap">
            <Image
              alt="Engie"
              src="/images/clients/engie_logo.png"
              width={158}
              height={48}
              className="col-span-2 max-h-10  opacity-40 object-contain lg:col-span-1"
            />
            <Image
              alt="Epicom"
              src="/images/clients/epicom_logo.png"
              width={158}
              height={48}
              className="col-span-2 max-h-12 opacity-40 object-contain lg:col-span-1"
            />
            <Image
              alt="WPiP"
              src="/images/clients/wpip_logo.png"
              width={100}
              height={48}
              className="col-span-2 max-h-8 opacity-40 object-contain lg:col-span-1"
            />
            <Image
              alt="Kontakt Simon"
              src="/images/clients/kontakt_simon_logo.png"
              width={158}
              height={48}
              className="col-span-2 max-h-12  opacity-40 object-contain sm:col-start-2 lg:col-span-1"
            />

            <Image
              alt="Flosmed"
              src="/images/clients/flosmed_logo.png"
              width={158}
              height={48}
              className="col-span-2 col-start-2 max-h-12  opacity-40 object-contain sm:col-start-auto lg:col-span-1"
            />
          </div>
          <div className="mt-16 flex justify-center">
            <p className="relative rounded-full bg-secondary px-4 py-1.5 text-sm/6 ring-2 shadow-sm ring-inset ring-secondary-border">
              <span className="hidden md:inline text-body-text">Cieszymy się zaufaniem przedsiębiorstw z sektora MŚP, jak i liderów rynkowych z listy <b>Fortune 500</b></span>
            </p>
          </div>
        </div>
      </div>
    )
  }
  