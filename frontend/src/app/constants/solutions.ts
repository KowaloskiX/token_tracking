import { AudioWaveform, Bell, BookOpen, BookText, Bot, Brain, BrainCircuit, Brush, Building2, ChartArea, CheckCheck, Clipboard, ClipboardCheck, Clock, Clock1, Clock10, Cloud, Database, DollarSign, Eye, FileQuestion, Files, FileText, GitBranch, GitCommit, GitFork, Globe, Key, Lightbulb, List, ListChecks, ListTodo, Lock, Map, MessageCircle, PaintBucket, PaintRoller, Palette, Pencil, PencilRuler, Pin, Plug, Search, SearchCheck, Server, Settings, Shield, ShieldCheck, Star, Swords, Target, UploadCloud, User, Users, Wrench, Zap } from "lucide-react"

interface SolutionContent {
  hero: {
    subtitle: string
    title: string
    description: string
    imageSrc: string
    imageAlt: string
  }
  stats?: {
    title: string
    description: string
    stats: Array<{
      value: string
      title: string
      description: string
      bgColor: string
      valueColor?: string
      titleColor?: string
      descriptionColor?: string
      widthClass: string
    }>
  }
  features: Array<{
    subtitle: string
    title: string
    description: string
    imageSrc: string
    imageAlt: string
    features: Array<{
      name: string
      description: string
      icon: any // Ideally, you'd want to type this properly for your icon library
    }>
  }>
}

export const SOLUTIONS: Record<string, SolutionContent> = {
    przetargi: {
        hero: {
            subtitle: "Zdominuj zamówienia publiczne",
            title: "Wyszukuj i analizuj przetargi z AI",
            description: "Zautomatyzuj wyszukiwanie przetargów i analizę dokumentacji zamówień publicznych - oszczędzając czas i zwiększając efektywność pracy.",
            imageSrc: "/images/public_tenders_ss.png",
            imageAlt: "App screenshot"
        },
        stats: {
            title: "Zyskaj więcej kontraktów dzięki automatyzacji przetargów z AI.",
            description: "Asystent AI pozwala firmom oszczędzać czas i wygrywać więcej przetargów dzięki precyzyjnemu wyszukiwaniu przetargów na podstawie profilu firmy.",
            stats: [
              {
                value: "450k+",
                title: "Dokumentów",
                description: "AI analizuje tysiące przetargów w poszukiwaniu okazji.",
                bgColor: "bg-secondary",
                widthClass: "sm:w-3/4 sm:max-w-md"
              },
              {
                value: "2 500+",
                title: "Dokładnie analizowanych przetargów dziennie przez AI.",
                description: "AI przegląda dokumentację każdego przetargu i wybiera najlepsze.",
                bgColor: "bg-foreground",
                valueColor: "text-background",
                titleColor: "text-background",
                descriptionColor: "text-gray-400",
                widthClass: "lg:w-full lg:max-w-sm"
              },
              {
                value: "94%",
                title: "Przyspieszony proces wyszukiwania i analizy.",
                description: "Proces analizy przetargów jest znacząco skrócony, co pozwala być zawsze pierwszym.",
                bgColor: "bg-secondary-border",
                widthClass: "sm:w-11/12 sm:max-w-xl"
              }
            ]
          },
        features: [
            {
              subtitle: "Wyszukiwarka Przetargów",
              title: "Przeszukuj tysiące przetargów",
              description: "Asystenci AI monitorują, analizują i wybierają najlepsze przetargi dla Twojej firmy spośród tysięcy przetargów.",
              imageSrc: "/images/public_tenders_ss.png",
              imageAlt: "Product screenshot",
              features: [
                {
                  name: 'Całkowity przegląd.',
                  description: 'Asystenci przeglądają tysiące przetargów dzięki czemu nic nie umknie uwadze Twojego zespołu.',
                  icon: SearchCheck,
                },
                {
                  name: 'Precyzyjne dopasowanie.',
                  description: 'Dzięki zdefiniowanym frazom kluczowym oraz profilowi firmy Asystenci AI wyszukują tylko najlepsze okazje.',
                  icon: CheckCheck,
                },
                {
                  name: 'Wiele źródeł.',
                  description: 'Asystenci przeglądają w zautomatyzowany sposób wszystkie dostępne źródła z przetargami.',
                  icon: Globe,
                }
              ]
            },
            {
              subtitle: "Analiza Kryteriów",
              title: "Weryfikuj kluczowe kryteria",
              description: "Asystenci ułatwiają Twojemu zespołowi wstępną analizę przetargów weryfikując kluczowe kryteria.",
              imageSrc: "/images/kryteria_ss.png",
              imageAlt: "Notification system screenshot",
              features: [
                {
                  name: 'Wnikliwa analiza.',
                  description: 'Asystenci AI analizują wszystkie pliki załączone do przetargów wyszukując odpowiedzi na kluczowe kryteria.',
                  icon: Eye,
                },
                {
                  name: 'Szybka ocena.',
                  description: 'Posiadając wiedzę o profilu firmy oraz kryteria asystenci przypisują każdemu przetargowi ocenę.',
                  icon: Star,
                }
              ]
            },
            {
              subtitle: "Analizuj Sprawmiej",
              title: "Analizuj pliki SIWZ z AI",
              description: "Asystent posiadając dostęp do plików znacząco przyspiesza analizę odpowiadając na wszelkie pytania odnośnie przetargu.",
              imageSrc: "/images/chat_ss.png",
              imageAlt: "Security features screenshot",
              features: [
                {
                  name: 'Błyskawiczna analiza.',
                  description: 'AI automatycznie przetwarza dokumenty SIWZ, dostarczając kluczowe informacje w kilka chwil.',
                  icon: Zap,
                },
                {
                  name: 'Precyzyjne wnioski.',
                  description: 'Inteligentne algorytmy wyodrębniają najistotniejsze wymagania i wskazują potencjalne ryzyka.',
                  icon: Pin,
                },
                {
                  name: 'Mądre decyzje.',
                  description: 'Dzięki pełnej analizie AI, zespół może skupić się na przygotowaniu skutecznych ofert z AI.',
                  icon: Brain,
                }
              ]
            }
          ]
      },
      bai: {
        hero: {
            subtitle: "Firmowi Asystenci",
            title: "Business Artificial Intelligence (BAI)",
            description: "Automatyzuj procesy biznesowe, analizuj dane i wyciągaj wnioski w sposób nieosiągalny dotychczas nawet dla firm z wewnętrznym zespołem analityków.",
            imageSrc: "/images/BAI-Architektura.png",
            imageAlt: "Architecture diagram"
        },
        stats: {
            title: "Zwiększ produktywność firmy",
            description: "Asystenci AI zasileni wiedzą Twojej firmy działają jak dodatkowi pracownicy – zawsze dostępni, niezawodni i wyposażeni w pełną wiedzę potrzebną do realizacji powtarzalnych zadań.",
            stats: [
              {
                value: "15+",
                title: "Źródeł danych",
                description: "Pionierska scentralizowana analiza danych ze źródeł jak Excel, PDF oraz SQL.",
                bgColor: "bg-secondary",
                widthClass: "sm:w-3/4 sm:max-w-md"
              },
              {
                value: "70%",
                title: "Zautomatyzowanych zadań wymagających obsługi komputera.",
                description: "Firmowy Asystent może zautomatyzować do 70% powtarzalnych zadań w codziennych operacjach biznesowych jak raportowanie, generowanie ofert itp.",
                bgColor: "bg-foreground",
                valueColor: "text-background",
                titleColor: "text-background",
                descriptionColor: "text-gray-400",
                widthClass: "lg:w-full lg:max-w-sm"
              },
              {
                value: "10X",
                title: "Szybsza praca z plikami",
                description: "Analiza danych oraz możliwość generowania plików znacząco usprawniają pracę biurową.",
                bgColor: "bg-secondary-border",
                widthClass: "sm:w-11/12 sm:max-w-xl"
              }
            ]
          },
        features: [
            {
              subtitle: "Firmowy Autopilot",
              title: "Automatyzuj zadania",
              description: "Zlecaj Asystentom monotonne zadania i wyznaczaj interwały czasowe w jakich mają pracować.",
              imageSrc: "/images/automation_ss.png",
              imageAlt: "Product screenshot",
              features: [
                {
                  name: 'Definiuj zadania.',
                  description: 'Przypisuj Asystentom zadania jak generowanie raportów, monitorowanie konkurencji, analizowanie przetargów itp.',
                  icon: ListChecks,
                },
                {
                  name: 'Wyznaczaj interwały czasowe.',
                  description: 'Definiuj jak często Asystenci mają wykonywać przypisane im zadania.',
                  icon: Clock10,
                },
                {
                  name: 'Przeglądaj rezultaty.',
                  description: 'Podaj, w jakiej formie chciałbyś otrzymać wyniki – raport, e-mail, lista czy inny format.',
                  icon: Search,
                }
              ]
            },
            {
              subtitle: "Wirtualni Pracownicy",
              title: "Twórz Asystentów AI",
              description: "Definiuj Asystentów tak, aby pomagali Ci w codziennych, powtarzalnych sprawach w firmie.",
              imageSrc: "/images/creating_assistants.png",
              imageAlt: "Notification system screenshot",
              features: [
                {
                  name: 'Konwersuj z danymi.',
                  description: 'Asystent mając wgrane informacje potrafi je na bieżąco analizować oraz interpretować, stanowiąc świetne wsparcie w codziennej pracy.',
                  icon: MessageCircle,
                },
                {
                  name: 'Pracuj kreatywnie.',
                  description: 'Mając kontekst w postaci informacji o firmie lub kliencie Asystent może pomagać w strategii, marketingu oraz innych kreatywnych przedsięwzięciach.',
                  icon: BrainCircuit,
                },
                {
                  name: 'Przypisuj role.',
                  description: 'Każdy Asystent może służyć jako specjalista w swojej dziedzinie. Daj mu znać jak chcesz aby odpowiadał.',
                  icon: User
                },
              ]
            },
            {
              subtitle: "Wszechstronna Wiedza",
              title: "Wykorzystaj Dane",
              description: "Przechowuj i pracuj na danych w bezpieczny i scentralizowany sposób ze sztuczną inteligencją.",
              imageSrc: "/images/various_datasources_feature.png",
              imageAlt: "Security features screenshot",
              features: [
                {
                  name: 'Scentralizuj źródło informacji',
                  description: 'Dzięki wsparciu ustrukturyzowanych jak i nieustrutkuryzowanych formatów, możesz przechowywać dotychczas niezależne dane w jednym miejscu.',
                  icon: Database,
                },
                {
                  name: 'Analizuj dane',
                  description: 'Mając dane z wielu niezależnych źródeł Asystenci AI łączą fakty, wyciągając właściwe wnioski.',
                  icon: ChartArea,
                },

                {
                  name: 'Zarządaj danymi',
                  description: 'Zarządzaj dostępem do danych w organizacji oraz mądrze monitoruj ich wykorzystanie w odpowiedziach AI.',
                  icon: Files,
                },
              ]
            },
            {
              subtitle: "Generator Plików",
              title: "Generuj Zasoby",
              description: "Generuj pliki jak raporty, prezentacje, zestawienia finansowe oraz oferty ze sztuczną inteligencją.",
              imageSrc: "/images/file_generation_feature.png",
              imageAlt: "Security features screenshot",
              features: [
                {
                  name: 'Identyfikacja wizualna.',
                  description: 'Wgrywając zasoby do naszego systemu uczysz AI identyfikacji wizualnej Twojej firmy.',
                  icon: Palette,
                },
                {
                  name: 'Wartościowe treści.',
                  description: 'AI mając dostęp do wiedzy firmowej generuje zasoby, które są zgodne z faktami oraz treściwe.',
                  icon: FileText,
                },
                {
                  name: 'Łatwa edycja.',
                  description: 'Do każdego wygenerowanego pliku możesz nanieść poprawki po prostu mówiąc AI co ma poprawić.',
                  icon: Pencil,
                }
              ]
            }
          ]
      },
      development: {
        hero: {
            subtitle: "Rozwiązanie Na Miarę",
            title: "Indywidualne Rozwiązania AI.",
            description: "Storzymy dedykowane produkty AI, dopasowane do potrzeb Twojego biznesu.",
            imageSrc: "/images/software_development_bg.png",
            imageAlt: "Architecture diagram"
        },
        features: [
            {
              subtitle: "Rozwiązania Przyszłości",
              title: "Możliwości Rozwiązań AI",
              description: "Nasze doświadczenie w rozwijaniu innowacyjnych produktów pozwala nam realizować najbardziej wymagające projekty AI.",
              imageSrc: "/images/aesthetic_office_2.png",
              imageAlt: "Product screenshot",
              features: [
                {
                  name: 'Analiza danych.',
                  description: 'Rozwiązania AI przekształcają dane w praktyczne wnioski, które wspierają podejmowanie decyzji.',
                  icon: Search,
                },
                {
                  name: 'Predykcje i planowanie.',
                  description: 'Wykorzystaj sztuczną inteligencję do prognozowania i efektywnego planowania strategicznego.',
                  icon: ChartArea,
                },
                {
                  name: 'Automatyzacja procesów.',
                  description: 'Zautomatyzuj powtarzalne zadania i przyspiesz operacje biznesowe dzięki AI.',
                  icon: GitBranch,
                }
              ]
            },
            {
              subtitle: "Talent i Ambicje",
              title: "Eksperci od AI",
              description: "Nasz zespół to wykwalifikowani specjaliści, którzy z pasją realizują projekty AI, zapewniając najwyższą jakość i dopasowanie do potrzeb klientów.",
              imageSrc: "/images/consultations.png",
              imageAlt: "Expert AI solutions screenshot",
              features: [
                {
                  name: 'Doświadczenie w AI.',
                  description: 'Nasza ekspertyza obejmuje uczenie maszynowe, transformację danych oraz wykorzystanie dużych modeli językowych w postaci agentów.',
                  icon: BrainCircuit,
                },
                {
                  name: 'Wsparcie projektowe.',
                  description: 'Oferujemy pełne wsparcie na każdym etapie projektu – od koncepcji po wdrożenie.',
                  icon: Clipboard,
                },
                {
                  name: 'Indywidualne podejście.',
                  description: 'Dostosowujemy nasze działania do specyficznych potrzeb Twojej firmy.',
                  icon: User
                },
              ]
            },
            {
              subtitle: "Automatyzacja AI",
              title: "Integracja systemów",
              description: "Pomagamy firmom integrować istniejące systemy z AI, aby maksymalnie wykorzystać ich potencjał, zwiększając efektywność i redukując koszty.",
              imageSrc: "/images/various_datasources_feature.png",
              imageAlt: "Integration and automation AI solutions screenshot",
              features: [
                {
                  name: 'Gotowe rozwiązania.',
                  description: 'Łączymy rozwiązania AI z istniejącymi narzędziami, jak transkrypcja spotkań czy systemy CRM.',
                  icon: Plug,
                },
                {
                  name: 'Automatyzacja procesów.',
                  description: 'Automatyzujemy kluczowe procesy biznesowe, aby usprawnić Twoje działania.',
                  icon: Settings,
                },

                {
                  name: 'Zarządzanie danymi.',
                  description: 'Zapewniamy bezpieczne zarządzanie i monitorowanie danych w zintegrowanych systemach.',
                  icon: ShieldCheck,
                },
              ]
            }
          ]
      },
      warsztaty: {
        hero: {
            subtitle: "Warsztaty AI",
            title: "Praktyczne Wykorzystanie AI w Biznesie",
            description: "Nasze warsztaty to kompleksowe wprowadzenie w świat sztucznej inteligencji, które nie tylko tłumaczy podstawowe pojęcia, ale także pokazuje praktyczne zastosowania tej technologii w codziennym biznesie.",
            imageSrc: "/images/consultations.png",
            imageAlt: "Consultations example"
        },
        stats: {
            title: "Przedstawienie AI w Biznesie.",
            description: "Warsztaty AI to okazja, by odkryć możliwości sztucznej inteligencji. Dowiedz się, jak AI może wspierać Twoją firmę, automatyzować procesy i zwiększać efektywność dzięki praktycznym przykładom i ćwiczeniom.",
            stats: [
              {
                value: "8 godzin",
                title: "Praktycznych warsztatów",
                description: "AI analizuje tysiące przetargów w poszukiwaniu okazji.",
                bgColor: "bg-secondary",
                widthClass: "sm:w-3/4 sm:max-w-md"
              },
              {
                value: "10+ firm",
                title: "Zyskało przewagę konkurencyjną dzięki praktycznym warszatom AI.",
                description: "Nasze warsztaty zostały przeprowadzone w firmach z różnych branż, które wdrożyły AI.",
                bgColor: "bg-foreground",
                valueColor: "text-background",
                titleColor: "text-background",
                descriptionColor: "text-gray-400",
                widthClass: "lg:w-full lg:max-w-sm"
              },
              {
                value: "100%",
                title: "Zadowolonych uczestników.",
                description: "Uczestniczące firmy cenią warsztaty za ich praktyczne podejście i inspirację do dalszego rozwoju.",
                bgColor: "bg-secondary-border",
                widthClass: "sm:w-11/12 sm:max-w-xl"
              }
            ]
          },
        features: [
            {
              subtitle: "Część 1",
              title: "Wprowadzenie",
              description: "Na początek wprowadzimy uczestników w świat AI, tłumacząc podstawowe pojęcia i działanie tej technologii. Wyjaśnimy, czym różnią się różne rodzaje sztucznej inteligencji i obalimy mity, które często towarzyszą tej dziedzinie.",
              imageSrc: "/images/meeting_room.jpg",
              imageAlt: "Product screenshot",
              features: [
                {
                  name: 'Co to jest AI?',
                  description: 'Przybliżymy, czym jest sztuczna inteligencja, na czym polegają algorytmy AI i jak działa uczenie maszynowe.',
                  icon: FileQuestion,
                },
                {
                  name: 'Jak przebiega adopcja AI?',
                  description: 'Przedstawimy jak przez lata przebiegała adopcja AI i zdradzimy sekret dlaczego teraz jest najlepszy moment na zainteresowanie się tematem.',
                  icon: AudioWaveform,
                },
                {
                  name: 'Mity o AI.',
                  description: 'Omówimy popularne nieporozumienia dotyczące AI oraz wyjaśnimy, co jest realne do osiągnięcia przy użyciu tej technologii.',
                  icon: BookText,
                }
              ]
            },
            {
              subtitle: "Część 2",
              title: "Praktyczne Zastosowania",
              description: "W tej części pokażemy, jak AI wpływa na Twoją jak i inne branże oraz jak może być wykorzystana w codziennych operacjach biznesowych.",
              imageSrc: "/images/software_development_bg.png",
              imageAlt: "Notification system screenshot",
              features: [
                {
                  name: 'Podejmowanie decyzji.',
                  description: 'Jak AI może pomóc w przetwarzaniu ogromnych ilości danych, aby ułatwić podejmowanie trafniejszych decyzji?',
                  icon: GitFork,
                },
                {
                  name: 'Automatyzacja procesów.',
                  description: 'Przedstawimy, jak AI automatyzuje powtarzalne zadania, oszczędzając czas i zasoby.',
                  icon: Bot,
                },
                {
                  name: 'Personalizacja.',
                  description: 'Wyjaśnimy, jak AI dostosowuje ofertę do potrzeb klientów, zwiększając ich satysfakcję.',
                  icon: Brush,
                }
              ]
            },
            {
              subtitle: "Część 3",
              title: "Praktyczny Warsztat",
              description: "Uczestnicy będą mieli okazję przeanalizować rzeczywisty problem biznesowy i zaprojektować rozwiązanie AI.",
              imageSrc: "/images/consultations.png",
              imageAlt: "Security features screenshot",
              features: [
                {
                  name: 'Case study.',
                  description: 'Uczestnicy pracują na przykładzie problemu z realnego świata biznesu, aby zaprojektować odpowiednie rozwiązanie AI.',
                  icon: Building2,
                },
                {
                  name: 'Identyfikacja obszarów automatyzacji.',
                  description: 'Przedstawimy narzędzia i metody pozwalające na ocenę potencjału AI w organizacji.',
                  icon: Search,
                },
                {
                  name: 'Przykłady narzędzi AI.',
                  description: 'Nauczymy korzystania z gotowych rozwiązań, które można szybko wdrożyć w firmie.',
                  icon: PencilRuler,
                }
              ]
            },
            {
              subtitle: "Część 4",
              title: "Przygotuj firmę na AI",
              description: "W tej sekcji poruszymy zagadnienia związane z wdrażaniem AI w organizacji, od przygotowania danych po budowanie kultury otwartej na zmiany technologiczne.",
              imageSrc: "/images/ai_office.webp",
              imageAlt: "Security features screenshot",
              features: [
                {
                  name: 'Jakie dane są potrzebne?',
                  description: 'Omówimy, jakie dane są kluczowe i jak je przygotować do pracy z systemami AI.',
                  icon: Database,
                },
                {
                  name: 'Kultura organizacyjna .',
                  description: 'Pokażemy, jak skutecznie komunikować wartość AI w organizacji, aby zyskać wsparcie wszystkich interesariuszy..',
                  icon: Users,
                },
                {
                  name: 'Najczęstsze wyzwania.',
                  description: 'Podzielimy się doświadczeniami, jak radzić sobie z typowymi przeszkodami w procesie wdrażania AI.',
                  icon: Swords,
                }
              ]
            }
          ]
      },
      audyty: {
        hero: {
            subtitle: "Audyt AI",
            title: "Identyfikacja Obszarów Automatyzacji",
            description: "Audyty to dedykowane sesje, które pomagają zrozumieć, jak AI może wspierać Twoją organizację. Zidentyfikujemy obszary z potencjałem automatyzacji, zaproponujemy rozwiązania i wskażemy wąskie gardła procesów biznesowych.",
            imageSrc: "/images/software_development_bg.png",
            imageAlt: "Audit consultation"
        },
        stats: {
            title: "Zidentyfikuj okazje na automatyzację.",
            description: "Audyt AI to najlepszy sposób, aby zidentyfikować możliwości automatyzacji w Twojej firmie i uzyskać kompleksowy raport dopasowany do Twoich potrzeb biznesowych.",
            stats: [
              {
                value: "2 godziny",
                title: "Prezentacji o AI",
                description: "Treściwa prezentacja o praktycznym wykorzystaniu AI w biznesie i Twojej branży.",
                bgColor: "bg-secondary",
                widthClass: "sm:w-3/4 sm:max-w-md"
              },
              {
                value: "1 dzień",
                title: "Rozmów z interesariuszami z wybranych działów w firmie.",
                description: "Spotkania z przedstawicielami różnych departamentów w celu zidentyfikowania możliwości automatyzacji.",
                bgColor: "bg-foreground",
                valueColor: "text-background",
                titleColor: "text-background",
                descriptionColor: "text-gray-400",
                widthClass: "lg:w-full lg:max-w-sm"
              },
              {
                value: "50+ stron",
                title: "Obszernego raportu końcowego.",
                description: "Zawiera zmapowane procesy, identyfikację wąskich gardeł oraz rekomendacje wdrożeń AI w Twojej firmie.",
                bgColor: "bg-secondary-border",
                widthClass: "sm:w-11/12 sm:max-w-xl"
              }
            ]
          },
        features: [
            {
              subtitle: "Etap 1",
              title: "Prezentacja AI",
              description: "Audyt rozpoczynamy od krótkiej, treściwej prezentacji o AI. Wyjaśniamy, jak AI działa i jakie korzyści może przynieść.",
              imageSrc: "/images/presentation_meeting.webp",
              imageAlt: "Product screenshot",
              features: [
                {
                  name: 'Co to jest AI?',
                  description: 'Wprowadzenie do sztucznej inteligencji i wyjaśnienie jej zastosowań w biznesie.',
                  icon: FileQuestion,
                },
                {
                  name: 'Przykłady zastosowań.',
                  description: 'Przedstawiamy realne case studies z różnych branż, które skorzystały z AI.',
                  icon: BookOpen,
                },
                {
                  name: 'Inspiracja.',
                  description: 'Prezentacja ma na celu zainspirowanie uczestników i otworzenie ich na nowe możliwości.',
                  icon: Lightbulb,
                }
              ]
            },
            {
              subtitle: "Etap 2",
              title: "Rozmowy z interesariuszami",
              description: "Drugi etap audytu to seria rozmów z przedstawicielami różnych działów w firmie. Celem jest zrozumienie procesów i identyfikacja obszarów z potencjałem automatyzacji.",
              imageSrc: "/images/business_meeting.webp",
              imageAlt: "Notification system screenshot",
              features: [
                {
                  name: 'Analiza procesów.',
                  description: 'Rozmawiamy z liderami działów, aby zrozumieć kluczowe procesy w firmie.',
                  icon: Search,
                },
                {
                  name: 'Identyfikacja możliwości.',
                  description: 'Wskazujemy obszary, które mogą zostać zoptymalizowane dzięki automatyzacji AI.',
                  icon: Target,
                },
                {
                  name: 'Priorytetyzacja działań.',
                  description: 'Ustalamy, które działania mają największy potencjał ROI.',
                  icon: ClipboardCheck,
                }
              ]
            },
            {
              subtitle: "Etap 3",
              title: "Raport Końcowy",
              description: "Na zakończenie audytu przygotowujemy szczegółowy raport, który zawiera pełne mapowanie procesów oraz rekomendacje dotyczące wdrożeń AI.",
              imageSrc: "/images/report.webp",
              imageAlt: "Final report screenshot",
              features: [
                {
                  name: 'Mapowanie procesów.',
                  description: 'Kompleksowe przedstawienie obecnych procesów i ich wąskich gardeł.',
                  icon: Map,
                },
                {
                  name: 'Rekomendacje wdrożeń.',
                  description: 'Sugestie rozwiązań AI dopasowane do specyfiki Twojej firmy.',
                  icon: Wrench,
                },
                {
                  name: 'Ocena ROI.',
                  description: 'Analiza potencjalnych korzyści i zwrotu z inwestycji w AI.',
                  icon: DollarSign,
                }
              ]
            }
          ]
      }
    }


    