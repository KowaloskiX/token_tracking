import { Badge } from "../ui/badge";

export default function FeatureGrid() {
    return (
      <div className="py-24 sm:py-32">
        <div className="mx-auto max-w-2xl px-6 lg:max-w-7xl lg:px-8">
          <h2 className="text-base/7 font-medium text-body-text">Pracuj efektywniej</h2>
          <p className="mt-2 max-w-2xl text-pretty text-3xl tracking-tight text-foreground sm:text-5xl">
            Twórz Asystentów Al na bazie
            danych i zacznij automatyzacje
          </p>
          <div className="mt-10 grid grid-cols-1 gap-4 sm:mt-16 lg:grid-cols-6 lg:grid-rows-2">
            <div className="relative lg:col-span-3">
              <div className="absolute inset-px rounded-md bg-secondary max-lg:rounded-t-xl lg:rounded-tl-xl" />
              <div className="relative flex h-full flex-col overflow-hidden rounded-[calc(theme(borderRadius.md)+1px)] max-lg:rounded-t-[calc(1rem+1px)] lg:rounded-tl-[calc(1rem+1px)]">
                <img
                  alt=""
                  src="/images/long_term_memory_feature.png"
                  className="h-80 object-cover object-left -mt-10 sm:mt-0"
                />
                <div className="p-10 pt-4">
                  <h3 className="text-sm/4 font-medium text-body-text">Kontekst</h3>
                  <p className="mt-1 text-lg font-medium tracking-tight text-foreground">Wgrywanie danych</p>
                  <p className="mt-2 max-w-lg text-sm/6 text-gray-600">
                    Asystent AI zapamiętuje dane, które prześlesz, jeszcze lepiej wspierając Cię <br className="hidden lg:block" />w Twoich przedsięwzięciach i codziennej pracy.
                  </p>
                </div>
              </div>
              <div className="pointer-events-none absolute inset-px rounded-md border-secondary-border border-2 max-lg:rounded-t-xl lg:rounded-tl-xl" />
            </div>
            <div className="relative lg:col-span-3">
              <div className="absolute inset-px rounded-md bg-secondary lg:rounded-tr-xl" />
              <div className="relative flex h-full flex-col overflow-hidden rounded-[calc(theme(borderRadius.md)+1px)] lg:rounded-tr-[calc(1rem+1px)]">
                <img
                  alt=""
                  src="/images/project_selection_feature.png"
                  className="h-80 object-cover object-left lg:object-right -mt-2 sm:mt-0"
                />
                <div className="p-10 pt-4">
                  <h3 className="text-sm/4 font-medium text-body-text">Projekty</h3>
                  <p className="mt-1 text-lg font-medium tracking-tight text-foreground">Segreguj dane na Projekty</p>
                  <p className="mt-2 max-w-lg text-sm/6 text-gray-600">
                    Organizuj dane w projekty, aby sprawniej zarzadządzać
                    swoimi danymi oraz zadaniami.
                  </p>
                </div>
              </div>
              <div className="pointer-events-none absolute inset-px rounded-md border-secondary-border border-2 lg:rounded-tr-xl" />
            </div>
            <div className="relative lg:col-span-2">
              <div className="absolute inset-px rounded-md bg-secondary lg:rounded-bl-xl" />
              <div className="relative flex h-full flex-col overflow-hidden rounded-[calc(theme(borderRadius.md)+1px)] lg:rounded-bl-[calc(1rem+1px)]">
                <img
                  alt=""
                  src="/images/automation_feature.png"
                  className="h-full object-cover object-center"
                />
              </div>
              <div className="pointer-events-none absolute rounded-md border-secondary-border border-2 lg:rounded-bl-xl" />
            </div>
            <div className="relative lg:col-span-2">
              <div className="absolute inset-px rounded-md bg-secondary" />
              <div className="relative flex h-full flex-col overflow-hidden rounded-[calc(theme(borderRadius.md)+1px)]">
                <img
                  alt=""
                  src="/images/various_datasources_feature.png"
                  className="h-80 object-cover"
                />
                <div className="p-10 pt-4">
                  <h3 className="text-sm/4 font-medium text-body-text">Integracje</h3>
                  <p className="mt-1 text-lg font-medium tracking-tight text-foreground">Podłącz swoje systemy</p>
                  <p className="mt-2 max-w-lg text-sm/6 text-gray-600">
                    Zintegruj swoją infrastrukturę i pracuj efektywnie na danych z AI, centralizując swoje zasoby.
                  </p>
                </div>
              </div>
              <div className="pointer-events-none absolute inset-px rounded-md border-secondary-border border-2" />
            </div>
            <div className="relative lg:col-span-2">
              <div className="absolute inset-px rounded-md bg-secondary max-lg:rounded-b-xl lg:rounded-br-xl" />
              <div className="relative flex h-full flex-col overflow-hidden rounded-[calc(theme(borderRadius.md)+1px)] max-lg:rounded-b-[calc(1rem+1px)] lg:rounded-br-[calc(1rem+1px)]">
                <img
                  alt=""
                  src="/images/file_generation_feature.png"
                  className="h-80 object-cover"
                />
                <div className="p-10 pt-4">
                    <Badge>Coming soon</Badge>
                  <p className="mt-1 text-lg font-medium tracking-tight text-foreground">Generowanie plików</p>
                  <p className="mt-2 max-w-lg text-sm/6 text-gray-600">
                    Generuj raporty, prezentacje, oferty i dokumenty <br className="hidden lg:block" /> w Twojej szacie graficznej.
                  </p>
                </div>
              </div>
              <div className="pointer-events-none absolute inset-px rounded-md border-secondary-border border-2 max-lg:rounded-b-xl lg:rounded-br-xl" />
            </div>
          </div>
        </div>
      </div>
    )
  }