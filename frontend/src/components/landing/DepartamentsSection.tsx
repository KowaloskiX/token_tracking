import { motion } from "framer-motion"
import Link from "next/link"

const departments = [
    {
      id: 1,
      role: 'Rozwiązania software',
      description:
        'Zawsze chętnie realizujemy ambitne projekty związane z AI. Jeśli masz pomysł na indywidualne rozwiązanie to zapraszamy do kontaktu.',
      href: '/biznes/development',
    },
    {
      id: 2,
      role: 'Audyty i warsztaty AI',
      description:
        'Pomagamy zidentyfikować obszary gdzie AI przyniesie najlepsze rezultaty oraz przybliżamy temat jakim jest AI w biznesie.',
      href: '/biznes/audyty',
    },
    {
      id: 3,
      role: 'Produkty',
      description:
        'Rozwijamy pudełkowe rozwiązanie jakim jest Asystent AI, dzięki któremu możesz w szybki i tani sposób rozpocząć pracę z AI w Twojej firmie.',
      href: '/',
    },
]

const DepartmentItem = ({ department }: any) => {
  return (
    <motion.li 
      className="p-8 hover:bg-secondary rounded-xl"
      initial="initial"
      whileHover="hover"
    >
      <dl className="relative flex flex-wrap gap-x-3">
        <dt className="sr-only">Role</dt>
        <dd className="w-full flex-none text-lg font-semibold tracking-tight text-foreground">
          <Link href={department.href}>
            {department.role}
            <span aria-hidden="true" className="absolute inset-0" />
          </Link>
        </dd>
        <dt className="sr-only">Description</dt>
        <dd className="mt-2 w-full flex-none text-base/7 text-body-text">
          {department.description}
        </dd>
        <dd className="mt-4 flex items-center gap-x-3 text-base/7 text-body-text">
          <Link href={department.href}>
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
          </Link>
        </dd>
      </dl>
    </motion.li>
  )
}

export default function DepartmentsSection() {
  return (
    <div className="py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto flex max-w-2xl flex-col items-end justify-between gap-12 lg:mx-0 lg:max-w-none lg:flex-row">
          <div className="w-full lg:max-w-lg lg:flex-auto">
            <h2 className="text-pretty text-3xl tracking-tight text-foreground sm:text-4xl">
              Jesteśmy otwarci na współpracę.
            </h2>
            <p className="mt-6 text-xl/8 text-body-text">
              Rozwijając nasz główny produkt jakim jest Asystent AI nie zamykamy się na klientów. Pomagamy wdrażać AI niezależnie od tego na jakim etapie jesteś.
            </p>
            <img
              alt=""
              src="/images/aesthetic_office_2.png"
              className="mt-16 aspect-[6/5] w-full rounded-2xl bg-gray-50 object-cover lg:aspect-auto lg:h-[34.5rem]"
            />
          </div>
          <div className="w-full lg:max-w-xl lg:flex-auto">
            <h3 className="sr-only">Departments</h3>
            <ul className="-my-8 divide-y divide-neutral-200">
              {departments.map((department) => (
                <DepartmentItem key={department.id} department={department} />
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}