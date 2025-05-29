const items = [
    { label: 'Szwajcarskich zegarków', value: 'Jakość' },
    { label: 'Prosto z Sillicon Valley', value: 'Innowacyjność' },
    { label: 'Niczym w Japońskim ogrodzie', value: 'Minimalizm' },
  ]
  
  export default function Mission() {
    return (
      <div className="">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-2xl lg:mx-0 lg:max-w-none">
            <h2 className="text-pretty text-4xl tracking-tight text-gray-900 sm:text-5xl">Nasza Misja</h2>
            <div className="mt-6 flex flex-col gap-x-8 gap-y-20 lg:flex-row">
              <div className="lg:w-full lg:max-w-2xl lg:flex-auto">
                <p className="text-xl/8 text-gray-600">
                Aspirujemy do zostania synonimem innowacji i jakości w AI, budując nie tylko technologie, ale również kulturę organizacyjną, która stanie się wzorem dla innych firm. Zależy nam na tym, aby tworzyć produkty, które realnie zmieniają sposób pracy i życia ludzi, a jednocześnie inspirować kolejne pokolenia do działania w duchu kreatywności i odwagi.
                </p>
                <p className="mt-10 max-w-xl text-base/7 text-gray-700">
                W obliczu ostanich przełomów w dziedzinie AI, dostrzegamy wyjątkową szansę na odegranie kluczowej roli w Polsce, a ostatecznie w całej Unii Europejskiej przywracając jej świetność.
                </p>
              </div>
              <div className="lg:flex lg:flex-auto lg:justify-center">
                <dl className="w-64 space-y-8 xl:w-80">
                  {items.map((stat) => (
                    <div key={stat.label} className="flex flex-col-reverse gap-y-4">
                      <dt className="text-base/7 text-gray-600">{stat.label}</dt>
                      <dd className="text-3xl sm:text-5xl font-medium tracking-tight text-gray-900">{stat.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }
  