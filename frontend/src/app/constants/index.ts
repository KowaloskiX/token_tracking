// constants.ts

export const SUPPORTED_EXTENSIONS = {
    // Text files
    'txt': 'text/plain',
    'md': 'text/markdown',
    // Programming languages
    'py': 'text/x-python',
    'js': 'text/javascript',
    'ts': 'application/typescript',
    'html': 'text/html',
    'css': 'text/css',
    'java': 'text/x-java',
    'cpp': 'text/x-c++',
    'c': 'text/x-c',
    'cs': 'text/x-csharp',
    'go': 'text/x-golang',
    'rb': 'text/x-ruby',
    'php': 'text/x-php',
    'sh': 'application/x-sh',
    // Documents
    'tex': 'text/x-tex',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'xls': 'application/vnd.ms-excel',
    'json': 'application/json',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'pdf': 'application/pdf',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  };




 export const frequencies: Frequency[] = [
    { value: 'monthly', label: 'Miesięcznie', priceSuffix: '/miesiąc' },
    { value: 'annually', label: 'Rocznie', priceSuffix: '/rok' }
  ]
  

export const tiers: Tier[] = [
    {
      name: 'Darmowy',
      id: 'free',
      href: '#',
      description: 'Wszystko czego potrzebujesz, aby rozpocząć.',
      features: [
        'Chat z danymi',
        'Limit codziennego użytku',
        'Max 3 zasoby w projekcie',
        'Max 3 projekty',
      ],
      mostPopular: false,
      buttonText: 'Wypróbuj teraz'
    },
    {
      name: 'Standard',
      id: 'standard',
      href: '#',
      description: 'Idealne dla codziennego użytku w pracy.',
      features: [
        'Wszystkie funkcje z planu Darmowego',
        'Nielimitowana ilość projektów',
        'Nielimitowana ilość wgranych zasobów',
        'Nielimitowany dostęp',
      ],
      mostPopular: true,
      buttonText: 'Kup teraz'
    },
    {
      name: 'Enterprise',
      id: 'enterprise',
      href: '#',
      description: 'Dedykowane rozwiązania dla organizacji.',
      features: [
        'Wszystkie funkcje z planu Standard',
        'Dedykowany key account manager',
        'Automatyzacja procesów biznesowych',
        'Integracje z systemami firmowymi',
        'Dostęp do internetu',
        'Dostęp do API'
      ],
      mostPopular: false,
      buttonText: 'Skontaktuj się'
    }
  ]
  
  export const sections = [
    {
      name: 'Funkcjonalności',
      features: [
        { name: 'Chat z danymi', tiers: { Darmowy: true, Standard: true, Enterprise: true } },
        { name: 'Projekty', tiers: { Darmowy: '3', Standard: 'Nielimitowane', Enterprise: 'Nielimitowane' } },
        { name: 'Wgrane zasoby', tiers: { Darmowy: 'Do 3 na projekt', Standard: 'Nielimitowane', Enterprise: 'Nielimitowane' } },
        { name: 'Nieograniczony dostęp', tiers: { Darmowy: false, Standard: true, Enterprise: true } },
        { name: 'Dostęp do internetu', tiers: { Darmowy: false, Standard: false, Enterprise: true } },
        { name: 'Dostęp do API', tiers: { Darmowy: false, Standard: false, Enterprise: true } },
        { name: 'Liczba użytkonwików', tiers: { Darmowy: "1", Standard: "1", Enterprise: 'Nielimitowana' } },
      ],
    },
    {
      name: 'Rozszerzenia',
      features: [
        { name: 'Analiza przetargów', tiers: { Darmowy: false, Standard: false, Enterprise: true } },
        { name: 'Analiza konkurencji', tiers: { Darmowy: false, Standard: false, Enterprise: true } },
        { name: 'Analiza opinii klientów', tiers: { Darmowy: false, Standard: false, Enterprise: true } },
        { name: 'Automatyzacja raportowania', tiers: { Darmowy: false, Standard: false, Enterprise: true } },
        { name: 'Automatyzacja ofertowania', tiers: { Darmowy: false, Standard: false, Enterprise: true } },
        { name: 'Własne automatyzacje*', tiers: { Darmowy: false, Standard: false, Enterprise: true } }
      ],
    },
    {
      name: 'Wsparcie',
      features: [
        { name: 'Mail', tiers: { Darmowy: true, Standard: true, Enterprise: true } },
        { name: 'Telefon', tiers: { Darmowy: false, Standard: true, Enterprise: true } },
        { name: 'Dedykowany account manager', tiers: { Darmowy: false, Standard: false, Enterprise: true } }
      ],
    },
  ]



