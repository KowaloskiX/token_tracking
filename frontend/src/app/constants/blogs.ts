export interface Blog {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  image: string;
  date: string;
  datetime: string;
  category: {
    title: string;
    href: string;
  };
  author: {
    name: string;
    role: string;
    avatar: string;
  };
  content: {
    mainPoints: {
      title: string;
      description: string;
    }[];
    blocks: {
      type: 'section' | 'image' | 'mainPoints';
      content: {
        title?: string;
        text?: string;
        image?: {
          src: string;
          alt: string;
          caption?: string;
        };
      };
    }[];
  };
  quote?: {
    text: string;
    author: string;
    role: string;
  };
}

export const blogs: Blog[] = [
    {
      "id": "asystent-ai-biznes",
      "title": "Asystent AI Biznes już dostępny!",
      "subtitle": "Nowość",
      "description": "Asystent AI Biznes jest już dostępny! Odkryj jego wszechstronne możliwości i dowiedz się, w jaki sposób może realnie wesprzeć codzienną pracę w Twojej firmie.",
      "image": "/images/aesthetic_office_2.png",
      "date": "Gru 10, 2024",
      "datetime": "2024-12-10",
      "category": {
        "title": "AI",
        "href": "/blog/category/ai"
      },
      "author": {
        "name": "Anna Kowalska",
        "role": "Product Manager",
        "avatar": "/images/anna-avatar.png"
      },
      "content": {
        "mainPoints": [
          {
            "title": "Automatyzacja zadań",
            "description": "Asystenci AI mogą przejąć nawet do 70% powtarzalnych obowiązków biurowych, w tym tworzenie raportów, przygotowywanie ofert czy przetwarzanie dokumentów, znacząco oszczędzając Twój czas i zasoby."
          },
          {
            "title": "Inteligentna analiza danych",
            "description": "Innowacyjna, scentralizowana analiza danych z ponad 15 źródeł (m.in. Excel, PDF oraz SQL) dostarcza pełnego obrazu sytuacji, ułatwiając podejmowanie trafnych decyzji biznesowych."
          },
          {
            "title": "Zwiększona produktywność",
            "description": "Dziesięciokrotnie szybsze przetwarzanie dokumentów i informacji dzięki zaawansowanym narzędziom analitycznym oraz automatycznemu generowaniu plików, co znacząco podnosi efektywność pracy zespołu."
          }
        ],
        "blocks": [
          {
            "type": "section",
            "content": {
              "title": "Rewolucja w Zarządzaniu Firmą",
              "text": "Business Artificial Intelligence (BAI) wyznacza nowy standard funkcjonowania przedsiębiorstw. Asystenci AI działają jak dodatkowi, niezawodni członkowie zespołu, zawsze gotowi do realizacji powtarzalnych zadań oraz dostarczania aktualnej wiedzy. To nie tylko narzędzie, lecz strategiczny partner, który pomaga firmom efektywniej wykorzystać zasoby, usprawnić procesy i przyspieszyć rozwój."
            }
          },
          {
            "type": "image",
            "content": {
              "image": {
                "src": "/images/automation_ss.png",
                "alt": "Automatyzacja zadań z Asystentem AI",
                "caption": "Intuicyjny panel do zarządzania procesami automatyzacji w Asystencie AI Biznes"
              }
            }
          },
          {
            "type": "section",
            "content": {
              "title": "Firmowy Autopilot",
              "text": "Wyobraź sobie, że masz do dyspozycji zespół wirtualnych pomocników, którzy nigdy nie potrzebują przerwy, a każde zadanie wykonują skrupulatnie i terminowo. Możesz im zlecać regularne generowanie raportów, monitorowanie zmian na rynku czy analizę kluczowych wskaźników — wszystko to w ściśle określonych przedziałach czasowych. Dzięki temu otrzymujesz wyniki we właściwym momencie, w preferowanej formie, a Twoi pracownicy mogą skupić się na bardziej kreatywnych i strategicznych inicjatywach."
            }
          },
          {
            "type": "image",
            "content": {
              "image": {
                "src": "/images/creating_assistants.png",
                "alt": "Tworzenie Asystentów AI",
                "caption": "Przejrzysty interfejs do kreowania i konfiguracji wyspecjalizowanych Asystentów AI"
              }
            }
          },
          {
            "type": "section",
            "content": {
              "title": "Wirtualni Specjaliści na Żądanie",
              "text": "Każdy Asystent AI może zostać ukierunkowany na wybraną dziedzinę, dzięki czemu zyskujesz dostęp do dedykowanych ekspertów w konkretnych obszarach biznesowych. Mając bezpośredni dostęp do firmowych danych, asystenci mogą przeprowadzać szczegółowe analizy, wspierać proces decyzyjny, a nawet uczestniczyć w inicjatywach kreatywnych. Intuicyjny, konwersacyjny interfejs ułatwia współpracę, sprawiając, że komunikacja z Asystentem AI jest równie prosta, jak rozmowa z człowiekiem."
            }
          },
          {
            "type": "mainPoints",
            "content": {}
          },
          {
            "type": "section",
            "content": {
              "title": "Przyszłość Pracy Biurowej",
              "text": "BAI to znacznie więcej niż automatyzacja. To kompleksowa transformacja sposobu, w jaki firmy funkcjonują na co dzień. Dzięki integracji z różnorodnymi źródłami danych oraz zaawansowanym funkcjom analitycznym, Asystenci AI stają się kluczowym elementem strategii rozwoju. Umożliwiają zespołom skupienie się na kluczowych zadaniach o najwyższej wartości — takich jak tworzenie innowacji, budowanie relacji z klientami czy skalowanie działalności — jednocześnie zachowując pełną kontrolę i przejrzystość działań operacyjnych."
            }
          }
        ]
      },
      "quote": {
        "text": "Asystent AI Biznes naprawdę zrewolucjonizował nasze codzienne zarządzanie. Automatyzując powtarzalne zadania i błyskawicznie analizując dane, zyskaliśmy setki dodatkowych godzin miesięcznie. To pozwoliło zespołowi skupić się na strategicznym planowaniu i innowacjach, dzięki czemu firma rozwija się szybciej niż kiedykolwiek wcześniej.",
        "author": "Marek Nowicki",
        "role": "CEO, Innovate Solutions"
      }
    },
    {
      "id": "rewolucja-w-przetargach-publicznych",
      "title": "Rewolucja w Przetargach: AI Zmienia Zasady Gry",
      "subtitle": "Premiera Rozwiązania",
      "description": "Poznaj nasze innowacyjne narzędzie oparte na AI, które automatyzuje i usprawnia analizę przetargów publicznych, otwierając przed firmą zupełnie nowe możliwości biznesowe.",
      "image": "/images/tenders_image.webp",
      "date": "Gru 16, 2024",
      "datetime": "2024-12-16",
      "category": {
        "title": "Przetargi",
        "href": "/blog/category/przetargi"
      },
      "author": {
        "name": "Piotr Gerke",
        "role": "CTO Asystent AI",
        "avatar": "/images/nexo-avatar.png"
      },
      "content": {
        "mainPoints": [
          {
            "title": "Automatyzacja wyszukiwania",
            "description": "Asystenci AI nieprzerwanie skanują tysiące dostępnych przetargów, na bieżąco sprawdzając ich zgodność z profilem Twojej organizacji. Dzięki temu zawsze masz pewność, że żadna szansa biznesowa nie umknie Twojej uwadze."
          },
          {
            "title": "Inteligentna analiza",
            "description": "Zaawansowane algorytmy AI pozwalają na natychmiastową analizę dokumentów przetargowych. System automatycznie wyłuskuje kluczowe wymagania, identyfikuje potencjalne ryzyka i istotne kryteria, dzięki czemu możesz skupić się na przygotowaniu konkurencyjnej oferty."
          },
          {
            "title": "Potwierdzona skuteczność",
            "description": "Klienci, którzy wdrożyli nasze rozwiązanie, zdobyli już kontrakty warte ponad 350 milionów złotych, a czas analizy dokumentacji skrócił się średnio o 94%. To imponujące wyniki przekładające się na realną przewagę konkurencyjną."
          }
        ],
        "blocks": [
          {
            "type": "section",
            "content": {
              "title": "Era Cyfrowej Transformacji w Zamówieniach Publicznych",
              "text": "Rynek zamówień publicznych w Polsce przechodzi głęboką metamorfozę. W świecie, w którym kluczowe znaczenie ma szybkość i precyzja, tradycyjne, ręczne metody analizy stają się niewystarczające. Nasze rozwiązanie oparte na AI odpowiada na te potrzeby: automatyzuje, upraszcza i udoskonala każdy etap procesu, od wstępnego wyszukiwania przetargów aż po dogłębną analizę dokumentacji. W efekcie firmy zyskują elastyczność, oszczędzają cenny czas i zwiększają swoją skuteczność na dynamicznie zmieniającym się rynku."
            }
          },
          {
            "type": "image",
            "content": {
              "image": {
                "src": "/images/public_tenders_ss.png",
                "alt": "Wyszukiwarka Przetargów AI",
                "caption": "Zaawansowane narzędzie monitorujące tysiące ogłoszeń w czasie rzeczywistym, gwarantując szybką i precyzyjną selekcję odpowiednich przetargów"
              }
            }
          },
          {
            "type": "section",
            "content": {
              "title": "Kompleksowa Analiza z Asystentem AI",
              "text": "Nasz system to znacznie więcej niż prosta wyszukiwarka. Dzięki zaawansowanym mechanizmom analizy, Asystenci AI prześwietlają dokumentację SIWZ, automatycznie wskazując kluczowe warunki, terminy i potencjalne utrudnienia. Proces, który jeszcze niedawno wymagał długich godzin pracy analityków, dziś można zrealizować w zaledwie kilka minut. To oznacza większą efektywność i więcej czasu na przygotowanie jakościowych, dobrze dopracowanych ofert."
            }
          },
          {
            "type": "image",
            "content": {
              "image": {
                "src": "/images/kryteria_ss.png",
                "alt": "Analiza Kryteriów Przetargowych",
                "caption": "Inteligentne narzędzie do automatycznego rozpoznawania i interpretacji kryteriów przetargowych w dokumentacji"
              }
            }
          },
          {
            "type": "mainPoints",
            "content": {}
          },
          {
            "type": "section",
            "content": {
              "title": "Potwierdzona Skuteczność w Liczbach",
              "text": "Dzięki naszym rozwiązaniom firmy zyskują realną wartość. Analiza ponad 100 tysięcy przetargów, 350 milionów złotych w wygranych kontraktach oraz skrócenie czasu analizy aż o 94% to nie tylko imponujące statystyki, ale dowód na to, że innowacje AI realnie wpływają na sukces organizacji. Szybciej przygotowujesz oferty, sprawniej reagujesz na zmiany i budujesz trwałą przewagę konkurencyjną."
            }
          },
          {
            "type": "image",
            "content": {
              "image": {
                "src": "/images/chat_ss.png",
                "alt": "Interfejs Asystenta AI",
                "caption": "Czytelny i intuicyjny interfejs asystenta AI, umożliwiający dogłębną analizę dokumentacji przetargowej w czasie rzeczywistym"
              }
            }
          },
          {
            "type": "section",
            "content": {
              "title": "Przyszłość Zamówień Publicznych",
              "text": "Wkraczamy w epokę, w której technologia staje się kluczem do sukcesu w zamówieniach publicznych. Firmy, które postawią na rozwiązania AI, zyskają nie tylko automatyzację i optymalizację procesów, ale przede wszystkim cenną wiedzę i sprawdzoną strategię. Dzięki temu będą mogły skuteczniej konkurować na rynku, realizować ambitne projekty i szybciej odpowiadać na pojawiające się możliwości."
            }
          }
        ]
      }
    },
    {
      "id": "business-ai-transformacja",
      "title": "BAI: Transformacja Procesów Biznesowych",
      "subtitle": "Przewodnik",
      "description": "Poznaj, w jaki sposób sztuczna inteligencja (AI) zmienia oblicze procesów biznesowych, znacząco zwiększając efektywność działania i otwierając nowe horyzonty rozwoju.",
      "image": "/images/BAI-Architektura.png",
      "date": "Gru 8, 2024",
      "datetime": "2024-12-08",
      "category": {
        "title": "AI",
        "href": "/blog/category/ai"
      },
      "author": {
        "name": "Piotr Gerke",
        "role": "CTO Asystent AI",
        "avatar": "/images/nexo-avatar.png"
      },
      "content": {
        "mainPoints": [
          {
            "title": "Kompleksowa analiza danych",
            "description": "Możliwość scentralizowanej analizy danych pochodzących z ponad 15 źródeł zapewnia całościowy obraz kondycji firmy, ułatwiając precyzyjne planowanie i podejmowanie optymalnych decyzji."
          },
          {
            "title": "Automatyzacja procesów",
            "description": "Automatyzacja nawet 70% powtarzalnych zadań – od przygotowywania raportów po analizę dokumentów czy tworzenie ofert – pozwala zespołom skupić się na innowacjach i strategii."
          },
          {
            "title": "Wsparcie decyzyjne",
            "description": "Zaawansowane algorytmy predykcyjne pomagają przewidywać przyszłe scenariusze i trendy, efektywnie wspierając kadrę zarządzającą w podejmowaniu kluczowych, dalekowzrocznych decyzji."
          }
        ],
        "blocks": [
          {
            "type": "section",
            "content": {
              "title": "Era Inteligentnej Automatyzacji",
              "text": "Business Artificial Intelligence (BAI) nie jest już tylko futurystyczną wizją, lecz nieodzownym elementem nowoczesnych przedsiębiorstw. W obliczu lawinowo rosnącej ilości danych i coraz bardziej złożonych procesów, BAI staje się kluczem do utrzymania konkurencyjności. Dzięki niemu organizacje są w stanie przyspieszyć realizację zadań, zminimalizować koszty operacyjne oraz usprawnić komunikację na każdym poziomie."
            }
          },
          {
            "type": "image",
            "content": {
              "image": {
                "src": "/images/aesthetic_office_2.png",
                "alt": "Nowoczesne biuro z systemami AI",
                "caption": "Przestrzeń pracy przyszłości, w której BAI aktywnie wspiera każdy aspekt działalności firmy"
              }
            }
          },
          {
            "type": "section",
            "content": {
              "title": "Praktyczne Zastosowania BAI",
              "text": "Zastosowanie BAI nie ogranicza się do analizy danych. Dzięki inteligentnym systemom możliwe jest również przewidywanie przyszłych trendów, automatyczna generacja dokumentów czy personalizacja oferty dla klientów. W efekcie zespoły nie muszą już tracić czasu na monotonne zadania, a mogą skupić się na tworzeniu wartości – np. opracowywaniu nowatorskich produktów, pogłębianiu relacji z klientami czy doskonaleniu strategii biznesowej."
            }
          },
          {
            "type": "mainPoints",
            "content": {}
          },
          {
            "type": "section",
            "content": {
              "title": "Przygotowanie Organizacji na AI",
              "text": "Wdrożenie BAI wymaga zarówno zaplecza technologicznego, jak i odpowiedniej kultury organizacyjnej. Firmy, które odnoszą sukcesy w tym obszarze, zwykle rozpoczynają od analizy swoich procesów i identyfikacji tych, które przyniosą największe korzyści po zastosowaniu AI. Kluczem jest ciągłe doskonalenie: dostosowywanie strategii wdrożenia, monitorowanie rezultatów i dbanie o rozwój kompetencji zespołu, aby w pełni wykorzystać potencjał tej technologii."
            }
          },
          {
            "type": "image",
            "content": {
              "image": {
                "src": "/images/consultations.png",
                "alt": "Proces wdrażania AI",
                "caption": "Etapy wdrożenia rozwiązań AI – od analizy potrzeb, poprzez planowanie, aż po pełną integrację i optymalizację procesów"
              }
            }
          },
          {
            "type": "section",
            "content": {
              "title": "Mierzalne Rezultaty",
              "text": "Wdrożenie BAI przynosi wymierne i szybko dostrzegalne efekty. Dziesięciokrotnie szybsze przetwarzanie dokumentów, automatyzacja 70% powtarzalnych działań czy scentralizowana analiza danych z kilkunastu źródeł to tylko część korzyści. Dzięki temu organizacje mogą nie tylko oszczędzać czas i pieniądze, ale też znacząco podnosić jakość podejmowanych decyzji i kreować solidne fundamenty dla dalszego wzrostu."
            }
          }
        ]
      },
      "quote": {
        "text": "Business AI to nie zwykłe narzędzie, lecz solidna dźwignia wzrostu i przewagi rynkowej. Przedsiębiorstwa, które szybko wdrażają inteligentne rozwiązania, nie tylko obniżają koszty operacyjne i usprawniają procesy, ale przede wszystkim otwierają sobie drogę do trwałego rozwoju i innowacyjności.",
        "author": "Dr Aleksandra Nowak",
        "role": "Dyrektor ds. Transformacji Cyfrowej, Digital Enterprise Solutions"
      }
    }
]


export const getRecentPosts = (count: number = 2) => {
  return blogs
    .sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime())
    .slice(0, count)
    .map(blog => ({
      id: blog.id,
      title: blog.title,
      href: `/blog/${blog.id}`,
      date: blog.date,
      datetime: blog.datetime,
      category: blog.category,
      imageUrl: blog.image,
      description: blog.description
    }));
};