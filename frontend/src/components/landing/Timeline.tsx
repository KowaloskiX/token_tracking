const timeline = [
    {
      name: 'Założenie spółki',
      description:
        'Zainspirowani wizją przyszłości opartej na sztucznej inteligencji, Wiktor i Piotr, mimo dzielących ich niemalże tysiąca kilometrów, zakładają zdalnie spółkę, której celem jest zrewolucjonizowanie firm jako software house AI.',
      date: 'Paź 2022',
      dateTime: '2022-10',
    },
    {
      name: 'Pierwszy globalny produkt',
      description:
        'Rozpoczęcie skalowania innowacyjnej platformy SaaS do generowania treści marketingowych z wykorzystaniem AI. Na czas projektu centrum operacyjne spółki przeniesiono do San Francisco, wzmacniając naszą globalną obecność.',
      date: 'May 2023',
      dateTime: '2023-05',
    },
    {
      name: 'Otwarcie działu software',
      description:
        'Przeniesienie zdobytego w Dolinie Krzemowej know-how na rynek polski, zaowocowało realizacją prestiżowych kontraktów enterprise, które umocniły naszą pozycję na lokalnym rynku.',
      date: 'Jan 2024',
      dateTime: '2024-06',
    },
    {
      name: 'Start Asystenta AI',
      description:
        'Premiera naszej kompleksowej platformy AI, która pomaga zarówno klientom indywidualnym, jak i firmom, w automatyzacji i usprawnianiu codziennych zadań, redefiniując sposób, w jaki korzystamy z technologii.',
      date: 'Dec 2024',
      dateTime: '2024-12',
    },
  ]
  
  export default function Timeline() {
    return (
      <div className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="max-w-2xl">
          <h2 className="text-base/7 font-medium text-body-text">Od zera do lidera</h2>
          <p className="mt-2 text-pretty text-4xl tracking-tight text-foreground sm:text-5xl lg:text-balance">
            Nasza Historia
          </p>
          <p className="mt-4 text-lg/8 text-body-text">
            Zaczynając od pierwszych projektów dwóch studentów przez własny globalny produkt po duże kontrakty rangi enterprise i doradztwo w dziedzinie AI.
          </p>
        </div>
          <div className="mx-auto grid mt-12 max-w-2xl grid-cols-1 gap-8 overflow-hidden lg:mx-0 lg:max-w-none lg:grid-cols-4">
            {timeline.map((item) => (
              <div key={item.name}>
                <time dateTime={item.dateTime} className="flex items-center text-sm/6 font-semibold text-foreground">
                  <svg viewBox="0 0 4 4" aria-hidden="true" className="mr-4 size-1 flex-none">
                    <circle r={2} cx={2} cy={2} fill="currentColor" />
                  </svg>
                  {item.date}
                  <div
                    aria-hidden="true"
                    className="absolute -ml-2 h-px w-screen -translate-x-full bg-foreground/10 sm:-ml-4 lg:static lg:-mr-6 lg:ml-8 lg:w-auto lg:flex-auto lg:translate-x-0"
                  />
                </time>
                <p className="mt-6 text-lg/8 font-semibold tracking-tight text-foreground">{item.name}</p>
                <p className="mt-1 text-base/7 text-base-text text-justify">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }
  