export const SOURCE_CONFIG = {
  ezamowienia: {
      icon: '/images/tender_sources/ezamowienia_logo.png',
      label: 'E-zamówienia',
      urlPattern: 'ezamowienia.gov.pl'
  },
  ted: {
      icon: '/images/tender_sources/ted_logo.png',
      label: 'TED Europa',
      urlPattern: 'ted.europa.eu'
  },
  eb2b: {
    icon: '/images/tender_sources/eb2b_logo.png',
    label: 'Eb2b',
    urlPattern: 'platforma.eb2b.com.pl'
},
  egospodarka: {
    icon: '/images/tender_sources/egospodarka_logo.png',
    label: 'EGospodarka',
    urlPattern: 'przetargi.egospodarka.pl'
},
  ezamawiajacy: {
      icon: '/images/tender_sources/ezamawiajacy_logo.png',
      label: 'Ezamawiajacy',
      urlPattern: 'ezamawiajacy.pl'
},
logintrade: {
  icon: '/images/tender_sources/logintrade_logo.png',
  label: 'Logintrade',
  urlPattern: 'logintrade.net'
},
  smartpzp: {
    icon: '/images/tender_sources/smartpzp_logo.png',
    label: 'SmartPZP',
    urlPattern: 'portal.smartpzp.pl'
},
    epropublico: {
    icon: '/images/tender_sources/epropublico_logo.png',
    label: 'Epropublico',
    urlPattern: 'e-propublico.pl'
},
  platformazakupowa: {
    icon: '/images/tender_sources/platformazakupowa_logo.png',
    label: 'Platforma Zakupowa',
    urlPattern: 'platformazakupowa.pl'
},
bazakonkurencyjnosci: {
    icon: '/images/tender_sources/bazakonkurencyjnosci_logo.png',
    label: 'Baza Konkurencyjnosci',
    urlPattern: 'bazakonkurencyjnosci.funduszeeuropejskie.gov.pl'
},
orlenconnect: {
  icon: '/images/tender_sources/orlen_logo.png',
  label: 'Orlen Connect',
  urlPattern: 'connect.orlen.pl'
}, 
pge: {
  icon: '/images/tender_sources/pge_logo.png',
  label: 'Grupa PGE',
  urlPattern: 'swpp2.gkpge.pl'
}
} as const;

export const CRITERIA_CONFIG = [
  {
    id: 'value',
    name: "Czy jest wymagane wadium?",
    description: "Czy jest wymagane wadium?"
  }
];

export const DEFAULT_PINECONE_CONFIG = {
  index_name: "",
  namespace: "",
  embedding_model: "",
}