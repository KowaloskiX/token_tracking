"use client";

import { useState, useRef, useEffect } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { 
  HelpCircle, 
  Sparkles, 
  Lightbulb, 
  Info,
  FileText,
  KeyIcon
} from "lucide-react";
import { 
  HoverCard,
  HoverCardTrigger,
  HoverCardContent
} from "@/components/ui/hover-card";
import { Badge } from "@/components/ui/badge";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { 
  Search, 
  Building2, 
  ClipboardList, 
  Type, 
  X, 
  Database,
  ChevronsUpDown,
  Check, 
  Trash2,
  ChevronRight,
  ChevronDown
} from "lucide-react";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { POLISH_SOURCES, TED_SOURCES, CRITERIA_CONFIG} from "@/app/constants/tenders";
import { Slider } from "@/components/ui/slider";
import { QuestionMarkIcon } from "@radix-ui/react-icons";

const criteriaSchema = z.object({
  name: z.string().min(1, "Kryterium jest wymagane"),
  description: z.string(),
  weight: z.number().min(1).max(5),
  is_disqualifying: z.boolean().default(false),
  exclude_from_score: z.boolean().default(false),
  instruction: z.string().optional(),
  subcriteria: z.array(z.string()).optional(),
  keywords: z.string().optional(),
});

const formSchema = z.object({
  name: z.string().min(1, "Nazwa jest wymagana"),
  company_description: z.string().min(1, "Opis firmy jest wymagany"),
  search_phrase: z.string().min(1, "Fraza kluczowa jest wymagana"),
  sources: z.array(z.string()).min(1, "Wybierz co najmniej jedno źródło"),
  criteria: z.array(criteriaSchema)
    .min(1, "Co najmniej jedno kryterium jest wymagane")
    .max(20, "Możesz dodać maks. 20 kryteriów"),
  assigned_users: z.array(z.string()).default([]),
});

type FormData = z.infer<typeof formSchema>;

interface Props {
  onSubmit: (data: FormData) => Promise<void>;
  onCancel?: () => void;
  isLoading?: boolean;
}

export function TenderAnalysisCreateForm({ onSubmit, onCancel, isLoading = false }: Props) {
  const [tedExpanded, setTedExpanded] = useState(false);
  const [weights, setWeights] = useState<Record<string, number>>(
    CRITERIA_CONFIG.reduce((acc, curr) => {
      acc[curr.id] = 3;
      return acc;
    }, {} as Record<string, number>)
  );
  
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      company_description: "",
      search_phrase: "",
      sources: [],
      assigned_users: [],
      criteria: CRITERIA_CONFIG.map(c => ({
        name: c.name,
        description: c.description,
        weight: 3,
        is_disqualifying: false,
        exclude_from_score: false,
        instruction: "",
        subcriteria: [],
        keywords: "",
      }))
    },
  });

  const handleWeightChange = (newWeights: Record<string, number>) => {
    setWeights(newWeights);
    const criteria = CRITERIA_CONFIG.map(c => ({
      name: c.name,
      description: c.description,
      weight: newWeights[c.id],
      is_disqualifying: false,
      exclude_from_score: false,
    }));
    form.setValue("criteria", criteria);
  };
  
  const newCriteriaRef = useRef<HTMLInputElement | null>(null);
  
  const [lastAddedIndex, setLastAddedIndex] = useState<number | null>(null);
  
  useEffect(() => {
    if (lastAddedIndex !== null && newCriteriaRef.current) {
      newCriteriaRef.current.focus();
      setLastAddedIndex(null);
    }
  }, [lastAddedIndex]);
  
  async function handleSubmit(values: FormData) {
    try {
      await onSubmit(values);
      form.reset();
    } catch (error) {
      console.error("Submission error:", error);
    }
  }

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "criteria",
  });

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  const toggleSection = (criteriaIndex: number) => {
    setExpandedSections(prev => ({
      ...prev,
      [criteriaIndex]: !prev[criteriaIndex]
    }));
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="relative">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="absolute right-6 -top-6 hover:text-muted-foreground/80"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        <div className="p-6 space-y-6">
          <div className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="flex items-center gap-2">
                    <Type className="h-4 w-4" />
                    Nazwa
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="Nazwij wyszukiwarkę..." {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="company_description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="flex items-center gap-2">
                    <Search className="h-4 w-4" />
                    Jakie przetargi chcesz wyszukiwać?
                    <HoverCard>
                      <HoverCardTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                          <HelpCircle className="h-3.5 w-3.5" />
                        </Button>
                      </HoverCardTrigger>
                      <HoverCardContent className="w-80 text-xs bg-background border-border text-body-text">
                        <p>Opisz swoją firmę, branżę i rodzaj usług/produktów, które oferujesz. AI będzie używało tych informacji do preselekcji przetargów na podstawie ich tytułów.</p>
                      </HoverCardContent>
                    </HoverCard>
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Opisz jakich przetargów szukasz oraz swoją firmę, aby AI wiedziało co Cię interesuje..."
                      className="min-h-[100px]"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="search_phrase"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="flex items-center gap-2">
                    <KeyIcon className="h-4 w-4" />
                    Słowa kluczowe
                    <HoverCard>
                      <HoverCardTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                          <HelpCircle className="h-3.5 w-3.5" />
                        </Button>
                      </HoverCardTrigger>
                      <HoverCardContent className="w-80 text-xs bg-background border-border text-body-text">
                        <p>Wprowadź główne słowa kluczowe, które występują w tytułach przetargów, które cię interesują. <br />AI będzie używało tych informacji do wyszukiwania przetargów.</p>
                      </HoverCardContent>
                    </HoverCard>
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="Np. Budowa infrastruktury drogowej" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="sources"
              render={({ field }) => {
                const selectedSources = field.value || [];
                const selectedTedCount = Object.keys(TED_SOURCES).filter(id => selectedSources.includes(id)).length;
                const totalTedCount = Object.keys(TED_SOURCES).length;
                
                return (
                <FormItem>
                  <FormLabel className="flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    Źródła
                  </FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          variant="outline"
                          role="combobox"
                          className="w-full justify-between bg-white/10 shadow-sm hover:bg-background hover:shadow-sm"
                        >
                          {selectedSources.length > 0
                            ? `Wybrano ${selectedSources.length} ${selectedSources.length === 1 ? "źródło" : "źródła"}`
                            : "Wybierz źródła..."}
                          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className="w-full p-0" align="start">
                      <Command>
                        <CommandInput placeholder="Szukaj źródła..." />
                        <CommandList>
                          <CommandEmpty>Nie znaleziono źródła.</CommandEmpty>
                          <CommandGroup>
                            {Object.entries(POLISH_SOURCES).map(([sourceId, source]) => {
                              const isSelected = selectedSources.includes(sourceId);
                              return (
                                <CommandItem
                                  key={sourceId}
                                  onSelect={() => {
                                    const newValue = isSelected
                                      ? selectedSources.filter((value) => value !== sourceId)
                                      : [...selectedSources, sourceId];
                                    field.onChange(newValue);
                                  }}
                                >
                                  <div className="flex items-center gap-2 flex-1">
                                    <img 
                                      src={source.icon} 
                                      alt={source.label}
                                      className="h-4 w-4 object-contain"
                                    />
                                    <span>{source.label}</span>
                                  </div>
                                  <Check
                                    className={cn(
                                      "ml-auto h-4 w-4",
                                      isSelected ? "opacity-100" : "opacity-0"
                                    )}
                                  />
                                </CommandItem>
                              );
                            })}
                            
                            <CommandItem
                              onSelect={() => setTedExpanded(!tedExpanded)}
                              className="cursor-pointer"
                            >
                              <div className="flex items-center gap-2 flex-1">
                                {tedExpanded ? (
                                  <ChevronDown className="h-4 w-4" />
                                ) : (
                                  <ChevronRight className="h-4 w-4" />
                                )}
                                <img 
                                  src="/images/tender_sources/ted_logo.png" 
                                  alt="TED Europa"
                                  className="h-4 w-4 object-contain"
                                />
                                <span>TED Europa</span>
                                {selectedTedCount > 0 && (
                                  <span className="text-xs text-muted-foreground">
                                    ({selectedTedCount}/{totalTedCount})
                                  </span>
                                )}
                              </div>
                            </CommandItem>
                            
                            {tedExpanded && Object.entries(TED_SOURCES).map(([sourceId, source]) => {
                              const isSelected = selectedSources.includes(sourceId);
                              return (
                                <CommandItem
                                  key={sourceId}
                                  onSelect={() => {
                                    const newValue = isSelected
                                      ? selectedSources.filter((value) => value !== sourceId)
                                      : [...selectedSources, sourceId];
                                    field.onChange(newValue);
                                  }}
                                  className="pl-8"
                                >
                                  <div className="flex items-center gap-2 flex-1">
                                    <img 
                                      src={source.icon} 
                                      alt={source.label}
                                      className="h-4 w-4 object-contain"
                                    />
                                    <span>{source.label}</span>
                                  </div>
                                  <Check
                                    className={cn(
                                      "ml-auto h-4 w-4",
                                      isSelected ? "opacity-100" : "opacity-0"
                                    )}
                                  />
                                </CommandItem>
                              );
                            })}
                          </CommandGroup>
                        </CommandList>
                      </Command>
                    </PopoverContent>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )}}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <FormLabel className="text-base">
                <div className="flex items-center gap-2">
                  <ClipboardList className="h-4 w-4" />
                  Kryteria analizy
                </div>
              </FormLabel>
            </div>

            <div className="space-y-6">
            {fields.map((field, index) => (
              <div key={field.id} className="relative space-y-4 border bg-white/10 p-4 rounded-lg shadow-sm border-secondary-border">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => remove(index)}
                  className="absolute top-2 right-2 text-black-600"
                  size="sm"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>

                <FormField
                  control={form.control}
                  name={`criteria.${index}.name`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-primary" />
                        Opis kryterium
                      </FormLabel>
                      <FormControl>
                        <Input
                          placeholder="Np. jaka jest wartość kontraktu?"
                          value={field.value}
                          onChange={(e) => {
                            field.onChange(e);
                            form.setValue(`criteria.${index}.description`, e.target.value);
                          }}
                          ref={index === lastAddedIndex ? newCriteriaRef : null}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className={`transition-all duration-300 ease-in-out ${!form.watch(`criteria.${index}.exclude_from_score`) ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0 overflow-hidden'}`}>
                  <FormField
                    control={form.control}
                    name={`criteria.${index}.weight`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Waga (1-5)</FormLabel>
                        <div className="flex gap-4 items-center">
                          <Slider
                            min={1}
                            max={5}
                            step={1}
                            value={[field.value]}
                            onValueChange={(val) => field.onChange(val[0])}
                            className="flex-1"
                          />
                          <span className="w-8 text-center font-medium">
                            {field.value}
                          </span>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  <FormField
                    control={form.control}
                    name={`criteria.${index}.is_disqualifying`}
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-3 bg-white/10 shadow-sm">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                        <div className="space-y-1 leading-none">
                          <FormLabel>
                            Kryterium dyskwalifikujące
                          </FormLabel>
                          <FormDescription className="text-xs">
                            Niespełnienie tego kryterium dyskwalifikuje przetarg
                          </FormDescription>
                        </div>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name={`criteria.${index}.exclude_from_score`}
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-3 bg-white/10 shadow-sm">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              if (checked) {
                                form.setValue(`criteria.${index}.weight`, 1);
                              }
                            }}
                          />
                        </FormControl>
                        <div className="space-y-1 leading-none">
                          <FormLabel>
                            Wyklucz z oceny
                          </FormLabel>
                          <FormDescription className="text-xs">
                            Nie uwzględniaj przy wyliczaniu relewantności
                          </FormDescription>
                        </div>
                      </FormItem>
                    )}
                  />
                </div>
                <div className="mt-5 pt-4 border-t border-border">
                  <div className="flex items-center justify-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleSection(index)}
                      className="text-muted-foreground hover:text-foreground flex items-center gap-2"
                    >
                      {expandedSections[index] ? (
                        <>
                          <X className="h-4 w-4" />
                          Ukryj opcjonalne
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4 text-primary-hover" />
                          Pokaż opcjonalne
                        </>
                      )}
                    </Button>
                  </div>

                  {expandedSections[index] && (
                    <div className="space-y-4 mt-4">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <FormLabel className="text-sm font-medium flex items-center gap-1.5 text-foreground">
                            <Sparkles className="h-4 w-4 text-primary-hover" />
                            Instrukcja dla AI
                            <Badge variant="outline" className="ml-1 font-normal text-xs py-0 border-secondary-border text-body-text">opcjonalna</Badge>
                          </FormLabel>
                          <HoverCard>
                            <HoverCardTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                                <HelpCircle className="h-3.5 w-3.5" />
                              </Button>
                            </HoverCardTrigger>
                            <HoverCardContent className="w-80 text-sm bg-background border-border text-body-text">
                              <p>Dodatkowe wskazówki dla AI, które doprecyzowują, jak analizować to kryterium i kiedy uznać je za spełnione.</p>
                            </HoverCardContent>
                          </HoverCard>
                        </div>

                        <FormField
                          control={form.control}
                          name={`criteria.${index}.instruction`}
                          render={({ field }) => (
                            <FormItem>
                              <FormControl>
                                <div className="relative">
                                  <Textarea
                                    placeholder="Np. 'Sprawdź dokładną kwotę budżetu i uznaj kryterium za spełnione, jeśli budżet przekracza 500 000 PLN'"
                                    className="min-h-[90px] pl-9 text-sm resize-y bg-secondary border-input shadow-inner"
                                    {...field}
                                    value={field.value || ''}
                                  />
                                  <Lightbulb className="absolute left-3 top-3 h-4 w-4 text-chart-4" />
                                </div>
                              </FormControl>
                            </FormItem>
                          )}
                        />
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <FormLabel className="text-sm font-medium flex items-center gap-1.5 text-foreground">
                            Słowa kluczowe
                            <Badge variant="outline" className="ml-1 font-normal text-xs py-0 border-secondary-border text-body-text">opcjonalne</Badge>
                          </FormLabel>
                          <HoverCard>
                            <HoverCardTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                                <HelpCircle className="h-3.5 w-3.5" />
                              </Button>
                            </HoverCardTrigger>
                            <HoverCardContent className="w-80 text-sm bg-background border-border text-body-text">
                              <p>Wprowadź słowa kluczowe oddzielone przecinkami, np. &quot;certyfikacja, ISO, budżet&quot;</p>
                            </HoverCardContent>
                          </HoverCard>
                        </div>

                        <FormField
                          control={form.control}
                          name={`criteria.${index}.keywords`}
                          render={({ field }) => (
                            <FormItem>
                              <FormControl>
                                <Textarea
                                  placeholder="Wprowadź słowa kluczowe oddzielone przecinkami, np. 'certyfikacja, ISO, budżet'"
                                  className="min-h-[60px] text-sm resize-y bg-secondary border-input shadow-inner"
                                  {...field}
                                  value={field.value || ''}
                                />
                              </FormControl>
                            </FormItem>
                          )}
                        />
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <FormLabel className="text-sm font-medium flex items-center gap-1.5 text-foreground">
                            Dodatkowe zapytania
                            <Badge variant="outline" className="ml-1 font-normal text-xs py-0 border-secondary-border text-body-text">opcjonalne</Badge>
                          </FormLabel>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              const currentSubcriteria = form.getValues(`criteria.${index}.subcriteria`) || [];
                              form.setValue(`criteria.${index}.subcriteria`, [
                                ...currentSubcriteria,
                                ""
                              ]);
                            }}
                          >
                            + Dodaj zapytanie
                          </Button>
                        </div>

                        {form.watch(`criteria.${index}.subcriteria`)?.map((_, subIndex) => (
                          <div key={subIndex} className="space-y-2 p-3 border rounded-md bg-white/5">
                            <div className="flex justify-between items-start">
                              <FormField
                                control={form.control}
                                name={`criteria.${index}.subcriteria.${subIndex}`}
                                render={({ field }) => (
                                  <FormItem className="flex-1">
                                    <FormControl>
                                      <Input
                                        placeholder="Np. 'Jakie są wymagane certyfikaty?'"
                                        className="text-sm"
                                        {...field}
                                      />
                                    </FormControl>
                                  </FormItem>
                                )}
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="ml-2"
                                onClick={() => {
                                  const currentSubcriteria = form.getValues(`criteria.${index}.subcriteria`) || [];
                                  form.setValue(
                                    `criteria.${index}.subcriteria`,
                                    currentSubcriteria.filter((_, i) => i !== subIndex)
                                  );
                                }}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

              {fields.length === 0 && (
                <p className="mt-2 text-sm text-red-600">
                  Nie można stworzyć wyszukiwarki bez kryteriów. Dodaj przynajmniej jedno kryterium.
                </p>
              )}

              <Button
                type="button"
                variant="outline"
                className="flex items-center gap-2 w-full justify-center"
                onClick={() => {
                  append({ 
                    name: "", 
                    description: "", 
                    weight: 3,
                    is_disqualifying: false,
                    exclude_from_score: false,
                    instruction: "",
                    subcriteria: [],
                    keywords: "",
                  });
                  setLastAddedIndex(fields.length);
                }}
              >
                + Dodaj nowe kryterium
              </Button>
            </div>
          </div>

          <Button type="submit" className="w-full bg-primary hover:bg-primary-hover shadow text-white" disabled={isLoading}>
            {isLoading ? "Tworzę..." : "Stwórz wyszukiwarkę"}
          </Button>
        </div>
      </form>
    </Form>
  );
}