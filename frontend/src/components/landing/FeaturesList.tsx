import { Database, FolderSearch, NotepadText } from "lucide-react"
import Image from "next/image"
import { motion } from "framer-motion"
import { Badge } from "../ui/badge"
import Link from "next/link"

const features = [
  {
    name: 'Analiza Przetargów Publicznych',
    description:
      'Asystenci AI znając profil firmy wyszukują oraz analizują z tysiące przetargów, prezentując najlepsze okazje dla Twojej firmy na rynku.',
    href: '/przetargi',
    icon: FolderSearch,
    available: true,
    image: '/images/kryteria_ss.png'
  },
  {
    name: 'Business Artificial Intelligence (BAI)',
    description:
      'Asystent AI zasilony danymi z systemów firmowych może zamienić się w prywatnego analityka danych Twojej firmy.',
    href: '/biznes/bai',
    icon: Database,
    available: true,
    image: '/images/various_datasources_feature.png'
  },
  {
    name: 'Generowanie Plików',
    description:
      'Asystent zasilony danymi generuje pliki automatyzując raportowanie, ofertowanie oraz przygotowania do prezentacji.',
    href: '#',
    icon: NotepadText,
    available: false,
    image: '/images/file_generation_feature.png'
  },
]

const FeatureCard = ({ feature }: any) => {
  return (
    <motion.a 
      href={feature.href}
      className="flex flex-col hover:bg-secondary hover:border-secondary-border border border-background cursor-pointer rounded-xl p-4"
      initial="initial"
      whileHover="hover"
    >
      <div className="relative w-full">
        <Image 
          src={feature.image}
          alt={`${feature.name} visualization`}
          width={800} 
          height={400}
          className="aspect-video w-full rounded-lg border-secondary-border border-2 bg-secondary object-cover sm:aspect-[2/1] lg:aspect-[3/2]"
        />
        <div className="absolute inset-0 rounded-lg border-secondary-border border-2 ring-1 ring-inset ring-foreground/10" />
      </div>
      <dt className="flex mt-6 px-2 items-center gap-x-3 text-base/7 font-medium text-foreground">
        <feature.icon aria-hidden="true" className="size-5 flex-none text-body-text" />
        {feature.name}
      </dt>
      <dd className="mt-2 flex px-2 flex-col text-base/7 text-gray-600">
        <p className="flex-auto">{feature.description}</p>
        <div className="mt-6">
        {feature.available ?
          <div className="text-sm/6 font-medium text-body-text">
            Dowiedz się więcej{' '}
            <motion.span
              aria-hidden="true"
              className="inline-block"
              variants={{
                initial: { x: 0 },
                hover: { 
                  x: 5,
                  transition: {
                    type: "spring",
                    stiffness: 400,
                    damping: 10
                  }
                }
              }}
            >
              →
            </motion.span>
          </div>
          :
          <Badge>Coming soon</Badge>
          }
        </div>
      </dd>
    </motion.a>
  )
}

export default function Example() {
  return (
    <div className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base/7 font-medium text-body-text">Realna Wartość Dla Biznesu</h2>
          <p className="mt-2 text-pretty text-4xl tracking-tight text-foreground sm:text-5xl lg:text-balance">
            Konkretne rozwiązania z solidnymi rezultatami.
          </p>
          <p className="mt-6 text-lg/8 text-gray-600">
            Implementując nasze produkty możesz być pewien rezultatów. Każde rozwiązanie jest rezultatem intensywnej pracy z realiami biznesowymi firm z różnorodnych branż.
          </p>
        </div>
        <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
          <dl className="grid max-w-xl grid-cols-1 gap-x-4 gap-y-10 lg:max-w-none lg:grid-cols-3">
            {features.map((feature) => (
              <FeatureCard key={feature.name} feature={feature} />
            ))}
          </dl>
        </div>
      </div>
    </div>
  )
}