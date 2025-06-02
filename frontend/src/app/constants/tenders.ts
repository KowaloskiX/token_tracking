export const POLISH_SOURCES = {
  ezamowienia: {
    icon: '/images/tender_sources/ezamowienia_logo.png',
    label: 'E-zamówienia',
    urlPattern: 'ezamowienia.gov.pl'
  },
  smartpzp: {
    icon: '/images/tender_sources/smartpzp_logo.png',
    label: 'SmartPZP',
    urlPattern: 'portal.smartpzp.pl'
  },
  platformazakupowa: {
    icon: '/images/tender_sources/platformazakupowa_logo.png',
    label: 'Platforma Zakupowa',
    urlPattern: 'platformazakupowa.pl'
  },
  egospodarka: {
    icon: '/images/tender_sources/egospodarka_logo.png',
    label: 'EGospodarka',
    urlPattern: 'przetargi.egospodarka.pl'
  },
  eb2b: {
    icon: '/images/tender_sources/eb2b_logo.png',
    label: 'Eb2b',
    urlPattern: 'platforma.eb2b.com.pl'
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
  epropublico: {
    icon: '/images/tender_sources/epropublico_logo.png',
    label: 'Epropublico',
    urlPattern: 'e-propublico.pl'
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

export const TED_SOURCES = {
  ted: {
    icon: '/images/tender_sources/countries/pl.png',
    label: 'Poland',
    urlPattern: 'ted.europa.eu'
  },
  ted_germany: {
    icon: '/images/tender_sources/countries/de.png',
    label: 'Germany',
    urlPattern: 'ted.europa.eu'
  },
  ted_france: {
    icon: '/images/tender_sources/countries/fr.png',
    label: 'France',
    urlPattern: 'ted.europa.eu'
  },
  ted_spain: {
    icon: '/images/tender_sources/countries/es.png',
    label: 'Spain',
    urlPattern: 'ted.europa.eu'
  },
  ted_italy: {
    icon: '/images/tender_sources/countries/it.png',
    label: 'Italy',
    urlPattern: 'ted.europa.eu'
  },
  ted_belgium: {
    icon: '/images/tender_sources/countries/be.png',
    label: 'Belgium',
    urlPattern: 'ted.europa.eu'
  },
  ted_netherlands: {
    icon: '/images/tender_sources/countries/nl.png',
    label: 'Netherlands',
    urlPattern: 'ted.europa.eu'
  },
  ted_sweden: {
    icon: '/images/tender_sources/countries/se.png',
    label: 'Sweden',
    urlPattern: 'ted.europa.eu'
  },
  ted_czechia: {
    icon: '/images/tender_sources/countries/cz.png',
    label: 'Czech Republic',
    urlPattern: 'ted.europa.eu'
  },
  ted_austria: {
    icon: '/images/tender_sources/countries/at.png',
    label: 'Austria',
    urlPattern: 'ted.europa.eu'
  },
  ted_portugal: {
    icon: '/images/tender_sources/countries/pt.png',
    label: 'Portugal',
    urlPattern: 'ted.europa.eu'
  },
  ted_denmark: {
    icon: '/images/tender_sources/countries/dk.png',
    label: 'Denmark',
    urlPattern: 'ted.europa.eu'
  },
  ted_finland: {
    icon: '/images/tender_sources/countries/fi.png',
    label: 'Finland',
    urlPattern: 'ted.europa.eu'
  },
  ted_norway: {
    icon: '/images/tender_sources/countries/no.png',
    label: 'Norway',
    urlPattern: 'ted.europa.eu'
  },
  ted_ireland: {
    icon: '/images/tender_sources/countries/ie.png',
    label: 'Ireland',
    urlPattern: 'ted.europa.eu'
  },
  ted_greece: {
    icon: '/images/tender_sources/countries/gr.png',
    label: 'Greece',
    urlPattern: 'ted.europa.eu'
  },
  ted_hungary: {
    icon: '/images/tender_sources/countries/hu.png',
    label: 'Hungary',
    urlPattern: 'ted.europa.eu'
  },
  ted_slovakia: {
    icon: '/images/tender_sources/countries/sk.png',
    label: 'Slovakia',
    urlPattern: 'ted.europa.eu'
  },
  ted_slovenia: {
    icon: '/images/tender_sources/countries/si.png',
    label: 'Slovenia',
    urlPattern: 'ted.europa.eu'
  },
  ted_croatia: {
    icon: '/images/tender_sources/countries/hr.png',
    label: 'Croatia',
    urlPattern: 'ted.europa.eu'
  },
  ted_romania: {
    icon: '/images/tender_sources/countries/ro.png',
    label: 'Romania',
    urlPattern: 'ted.europa.eu'
  },
  ted_bulgaria: {
    icon: '/images/tender_sources/countries/bg.png',
    label: 'Bulgaria',
    urlPattern: 'ted.europa.eu'
  },
  ted_estonia: {
    icon: '/images/tender_sources/countries/ee.png',
    label: 'Estonia',
    urlPattern: 'ted.europa.eu'
  },
  ted_latvia: {
    icon: '/images/tender_sources/countries/lv.png',
    label: 'Latvia',
    urlPattern: 'ted.europa.eu'
  },
  ted_lithuania: {
    icon: '/images/tender_sources/countries/lt.png',
    label: 'Lithuania',
    urlPattern: 'ted.europa.eu'
  },
  ted_luxembourg: {
    icon: '/images/tender_sources/countries/lu.png',
    label: 'Luxembourg',
    urlPattern: 'ted.europa.eu'
  }
} as const;

export const SOURCE_CONFIG = {
  ...POLISH_SOURCES,
  ...TED_SOURCES
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