"use client";

import { useState, useRef, useEffect } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { 
  HelpCircle, 
  Sparkles, 
  Lightbulb, 
  Info,
  FileText,
  UserPlus,
  Loader2,
  KeyIcon,
  Mail,
  GripVertical
} from "lucide-react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import {CSS} from '@dnd-kit/utilities';
import { 
  HoverCard,
  HoverCardTrigger,
  HoverCardContent
} from "@/components/ui/hover-card";
import { Badge } from "@/components/ui/badge";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Search,
  Building2,
  ClipboardList,
  Type,
  Database,
  ChevronsUpDown,
  Check,
  Share2,
  X,
  Trash2,
  ChevronRight,
  ChevronDown
} from "lucide-react";
import { TenderAnalysis } from "@/types/tenders";
import { POLISH_SOURCES, TED_SOURCES, GERMAN_SOURCES, CRITERIA_CONFIG } from "@/app/constants/tenders";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { useTender } from '@/context/TenderContext';
import { AssignUsersModal } from "../AssignUsersModal";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { QuestionMarkIcon } from "@radix-ui/react-icons";
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

const criteriaSchema = z.object({
  name: z.string().min(1, "Title is required"),
  description: z.string().min(1, "Question is required"),
  weight: z.number().min(1).max(5),
  is_disqualifying: z.boolean().default(false),
  exclude_from_score: z.boolean().default(false),
  instruction: z.string().optional(),
  subcriteria: z.array(z.string()).optional(),
  keywords: z.string().optional(),
});

const formSchema = z.object({
  name: z.string().min(1, "Name is required"),
  company_description: z.string().min(1, "Company description is required"),
  search_phrase: z.string().min(1, "Search phrase is required"),
  sources: z.array(z.string()).min(1, "Select at least one source"),
  criteria: z.array(criteriaSchema).min(1, "At least one criterion is required"),
  filtering_rules: z.string().optional(),
});

type FormData = z.infer<typeof formSchema>& { assigned_users: string[], email_recipients: string[] };

type OrgMember = {
  id: string;
  name: string;
  email: string;
  role: string;
  isCurrentUser: boolean;
};

interface Props {
  analysis: TenderAnalysis;
  onSubmit: (data: FormData) => Promise<void>;
  isLoading?: boolean;
  onShareToggle?: () => Promise<void>;
  showShareButton?: boolean;
}

interface SortableCriteriaItemProps {
  field: any;
  index: number;
  form: any;
  expandedSections: Record<string, boolean>;
  toggleSection: (index: number) => void;
  remove: (index: number) => void;
  newCriteriaRef: React.RefObject<HTMLInputElement>;
  lastAddedIndex: number | null;
  t: any;
  tCommon: any;
}

function SortableCriteriaItem({
  field,
  index,
  form,
  expandedSections,
  toggleSection,
  remove,
  newCriteriaRef,
  lastAddedIndex,
  t,
  tCommon
}: SortableCriteriaItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({id: field.id});

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.8 : 1,
    backdropFilter: isDragging ? 'blur(2px)' : 'none',
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`relative space-y-4 border bg-white/10 p-4 rounded-lg shadow-sm border-secondary-border ${
        isDragging ? 'z-50' : ''
      }`}
    >
      <div className="absolute top-2 right-2 flex gap-1">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground p-1"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => remove(index)}
          className="text-muted-foreground hover:text-red-700 p-1"
          size="sm"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      <FormField
        control={form.control}
        name={`criteria.${index}.name`}
        render={({ field }) => (
          <FormItem>
            <FormLabel className="flex items-center gap-2">
              <Type className="h-4 w-4 text-primary" />
              {t('tenders.edit.criterionTitle')}
            </FormLabel>
            <FormControl>
              <Input
                placeholder={t('tenders.edit.criterionTitlePlaceholder')}
                {...field}
                ref={index === lastAddedIndex ? newCriteriaRef : null}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name={`criteria.${index}.description`}
        render={({ field }) => (
          <FormItem>
            <FormLabel className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              {t('tenders.edit.criterionQuestion')}
            </FormLabel>
            <FormControl>
              <Textarea
                placeholder={t('tenders.edit.criterionQuestionPlaceholder')}
                className="min-h-[80px]"
                {...field}
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
              <FormLabel>{t('tenders.edit.weightLabel')}</FormLabel>
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
                  {t('tenders.edit.disqualifying')}
                </FormLabel>
                <FormDescription className="text-xs">
                  {t('tenders.edit.disqualifyingDescription')}
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
                  onCheckedChange={field.onChange}
                />
              </FormControl>
              <div className="space-y-1 leading-none">
                <FormLabel>
                  {t('tenders.edit.excludeFromScore')}
                </FormLabel>
                <FormDescription className="text-xs">
                  {t('tenders.edit.excludeFromScoreDescription')}
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
                {t('tenders.edit.hideOptional')}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 text-primary-hover" />
                {t('tenders.edit.showOptional')}
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
                  {t('tenders.edit.instructionLabel')}
                  <Badge variant="outline" className="ml-1 font-normal text-xs py-0 border-secondary-border text-body-text">{tCommon('optional')}</Badge>
                </FormLabel>
                <HoverCard>
                  <HoverCardTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                      <HelpCircle className="h-3.5 w-3.5" />
                    </Button>
                  </HoverCardTrigger>
                  <HoverCardContent className="w-80 text-sm bg-background border-border text-body-text">
                    <p>{t('tenders.edit.instructionTooltip')}</p>
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
                          placeholder={t('tenders.edit.instructionPlaceholder')}
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
                  {t('tenders.edit.keywordsLabel')}
                  <Badge variant="outline" className="ml-1 font-normal text-xs py-0 border-secondary-border text-body-text">{tCommon('optional')}</Badge>
                </FormLabel>
                <HoverCard>
                  <HoverCardTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                      <HelpCircle className="h-3.5 w-3.5" />
                    </Button>
                  </HoverCardTrigger>
                  <HoverCardContent className="w-80 text-sm bg-background border-border text-body-text">
                    <p>{t('tenders.edit.keywordsTooltip')}</p>
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
                        placeholder={t('tenders.edit.keywordsPlaceholder')}
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
                  {t('tenders.edit.subcriteriaLabel')}
                  <Badge variant="outline" className="ml-1 font-normal text-xs py-0 border-secondary-border text-body-text">{tCommon('optional')}</Badge>
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
                  {t('tenders.edit.addSubquery')}
                </Button>
              </div>

              {form.watch(`criteria.${index}.subcriteria`)?.map((_: any, subIndex: number) => (
                <div key={subIndex} className="space-y-2 p-3 border rounded-md bg-white/5">
                  <div className="flex justify-between items-start">
                    <FormField
                      control={form.control}
                      name={`criteria.${index}.subcriteria.${subIndex}`}
                      render={({ field }) => (
                        <FormItem className="flex-1">
                          <FormControl>
                            <Input
                              placeholder={t('tenders.edit.instructionPlaceholder')}
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
                          currentSubcriteria.filter((_: any, i: number) => i !== subIndex)
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
  );
}

export function EditTenderAnalysisForm({ analysis, onSubmit, isLoading = false, onShareToggle, showShareButton = false }: Props) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [advancedFilteringExpanded, setAdvancedFilteringExpanded] = useState(false);
  const { assignUsers } = useTender();
  const [isShareLoading, setIsShareLoading] = useState(false);
  const [assignUsersOpen, setAssignUsersOpen] = useState(false);
  // show/hide the inline assignment section
  const [showAssignees, setShowAssignees] = useState(false);
  // fetched org members
  const [orgMembers, setOrgMembers] = useState<OrgMember[]>([]);
  // local selection
 
  const [isAssigneesLoading, setIsAssigneesLoading] = useState(false);

  // Translation hooks
  const t = useTendersTranslations();
  const tCommon = useCommonTranslations();

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Guard assigned_users to never be undefined
  const assignedUsers: string[] = Array.isArray(analysis.assigned_users) ? analysis.assigned_users : [];

  // Determine if this analysis is shared (excludes owner)
  const isShared = assignedUsers.some(id => id !== analysis.user_id);
  const [tedExpanded, setTedExpanded] = useState(false);
  const [germanExpanded, setGermanExpanded] = useState(false);

  const toggleSection = (criteriaIndex: number) => {
    setExpandedSections(prev => ({
      ...prev,
      [criteriaIndex]: !prev[criteriaIndex]
    }));
  };


  const defaultCriteria =
  analysis.criteria.length > 0
    ? analysis.criteria.map((c) => ({
        name: c.name,
        description: c.description,
        weight: c.weight,
        is_disqualifying: c.is_disqualifying || false,
        exclude_from_score: c.exclude_from_score || false,
        instruction: c.instruction || "",
        subcriteria: c.subcriteria || [],
        keywords: c.keywords || "",
      }))
    : CRITERIA_CONFIG.map((c) => ({
        name: c.name,
        description: c.description,
        weight: 3,
        is_disqualifying: false,
        exclude_from_score: false,
        instruction: "",
        subcriteria: [],
        keywords: "",
      }));

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: analysis.name,
      company_description: analysis.company_description,
      search_phrase: analysis.search_phrase,
      sources: analysis.sources,
      criteria: defaultCriteria,
      filtering_rules: analysis.filtering_rules || "",
    },
  });

  const { fields, append, remove, move } = useFieldArray({
    control: form.control,
    name: "criteria",
  });

  const handleDragEnd = (event: DragEndEvent) => {
    const {active, over} = event;

    if (over && active.id !== over.id) {
      const oldIndex = fields.findIndex(field => field.id === active.id);
      const newIndex = fields.findIndex(field => field.id === over.id);
      
      if (oldIndex !== -1 && newIndex !== -1) {
        move(oldIndex, newIndex);
      }
    }
  };
  
  const newCriteriaRef = useRef<HTMLInputElement | null>(null);
  const [lastAddedIndex, setLastAddedIndex] = useState<number | null>(null);
  useEffect(() => {
    if (!showAssignees) return;
    (async () => {
      setIsAssigneesLoading(true);
      try {
        const resp = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/organizations/members`, {
          headers:{ Authorization:`Bearer ${localStorage.getItem('token')}` }
        });
        const { members } = await resp.json();
        setOrgMembers(members || []);
      } catch {
        // handle error
      } finally {
        setIsAssigneesLoading(false);
      }
    })();
  }, [showAssignees]);


  useEffect(() => {
    if (lastAddedIndex !== null && newCriteriaRef.current) {
      newCriteriaRef.current.focus();
      setLastAddedIndex(null);
    }
  }, [lastAddedIndex]);

  async function handleSubmit(values: FormData) {
    try {
      // include selected users (assigned users) and email recipients in the payload
      const payload = {
        ...values,
        assigned_users: selectedUsers,
        email_recipients: selectedEmailRecipients,
      };
      await onSubmit(payload);
    } catch (error) {
      console.error("Submission error:", error);
    }
  }

  // Updated share-toggle handler now using guarded assignedUsers
  const handleShareToggle = async () => {
    if (!analysis._id) return;
    setIsShareLoading(true);

    try {
      const resp = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/organizations/members`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      const { members } = await resp.json();
      const orgIds = members.map((m: any) => m.id);

      // build new list using assignedUsers
      const newAssigned = isShared
        ? assignedUsers.filter(id => !orgIds.includes(id))
        : Array.from(new Set([...assignedUsers, ...orgIds]));

      await assignUsers(analysis._id, newAssigned);
      await onShareToggle?.();
    } catch (err) {
      console.error(err);
    } finally {
      setIsShareLoading(false);
    }
  };
  
  const [selectedUsers, setSelectedUsers] = useState<string[]>(assignedUsers);
  const [selectedEmailRecipients, setSelectedEmailRecipients] = useState<string[]>(
    analysis.email_recipients || analysis.assigned_users || []
  );

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="relative">
      <input
        type="hidden"
        {...form.register("assigned_users")}
        value={selectedUsers.join(",")}
      />
      <input
        type="hidden"
        {...form.register("email_recipients")}
        value={selectedEmailRecipients.join(",")}
      />

    {showShareButton && (
  <div className="mb-4 space-y-2">
     <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={handleShareToggle}
      disabled={isShareLoading}
      className="flex items-center gap-2 w-full justify-center"
    >
      {isShareLoading
        ? isShared
          ? t('tenders.edit.share.stopSharingLoading')
          : t('tenders.edit.share.sharing')
        : isShared
        ? (
            <>
              <X className="w-4 h-4" />
              {t('tenders.edit.share.stopSharing')}
            </>
          )
        : (
            <>
              <Share2 className="w-4 h-4" />
              {t('tenders.edit.share.shareInOrg')}
            </>
          )
      }
    </Button>
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => setShowAssignees(v => !v)}
      className="flex items-center gap-2 w-full justify-center"
    >
      <UserPlus className="w-4 h-4" />
      {showAssignees ? t('tenders.edit.hideAssignUsers') : t('tenders.edit.assignUsers')}
    </Button>

    {showAssignees && (
      <div className="border p-4 rounded-md bg-muted/50">
        {isAssigneesLoading
          ? <div className="text-center py-6"><Loader2 className="animate-spin mx-auto"/></div>
          : orgMembers.length === 0
            ? <p className="text-sm text-muted-foreground">{t('tenders.edit.noUsers')}</p>
            : (
              <>
              <div className="mb-4 border border-border bg-muted/50 p-3 rounded-md flex items-start gap-2">
                <Info className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
                <div className="text-xs text-muted-foreground">
                  {t('tenders.edit.assignInfo')}
                </div>
              </div>
              <ScrollArea className="max-h-52">
                {orgMembers.map(m => {
                  const isOwner = m.id === analysis.user_id;
                  const isSel   = selectedUsers.includes(m.id);
                  return (
                    <div key={m.id} className="flex items-center space-x-2 py-2">
                      <Checkbox
                        checked={isSel || isOwner}
                        disabled={isOwner}
                        onCheckedChange={() => {
                          if (isOwner) return;
                          const next = isSel
                            ? selectedUsers.filter(u => u !== m.id)
                            : [...selectedUsers, m.id];

                          // update your local state
                          setSelectedUsers(next);

                          // **also** tell RHF about it
                          form.setValue("assigned_users", next, {
                            shouldValidate: true,
                            shouldDirty:   true,
                          });
                          
                          // Update email recipients: remove user if unassigned, add if assigned (unless already excluded)
                          if (isSel) {
                            // User being removed from assignment - also remove from email recipients
                            const newEmailRecipients = selectedEmailRecipients.filter(id => id !== m.id);
                            setSelectedEmailRecipients(newEmailRecipients);
                            form.setValue("email_recipients", newEmailRecipients);
                          } else {
                            // User being added to assignment - add to email recipients by default
                            if (!selectedEmailRecipients.includes(m.id)) {
                              const newEmailRecipients = [...selectedEmailRecipients, m.id];
                              setSelectedEmailRecipients(newEmailRecipients);
                              form.setValue("email_recipients", newEmailRecipients);
                            }
                          }
                        }}
                      />
                        <Label className="flex-1">
                        {m.name} <span className="text-xs text-muted-foreground">({m.email})</span>
                        {isOwner && <Badge className="ml-2 text-xs">{t('tenders.edit.ownerBadge')}</Badge>}
                      </Label>
                    </div>
                  );
                })}
              </ScrollArea>
              </>
            )
        }
        
        {/* Email Recipients Section */}
        {showAssignees && selectedUsers.length > 0 && (
          <div className="mt-4 border-t pt-4">
            <div className="mb-4 border border-border bg-muted/50 p-3 rounded-md flex items-start gap-2">
              <Mail className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
              <div className="text-xs text-muted-foreground">
                <strong>{t('tenders.edit.emailNotifications.title')}:</strong> {t('tenders.edit.emailNotifications.description')}
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">{t('tenders.edit.emailNotifications.recipients')}</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const allAssigned = selectedUsers;
                    const newEmailRecipients = selectedEmailRecipients.length === allAssigned.length ? [] : allAssigned;
                    setSelectedEmailRecipients(newEmailRecipients);
                    form.setValue("email_recipients", newEmailRecipients);
                  }}
                >
                  {selectedEmailRecipients.length === selectedUsers.length ? t('tenders.edit.emailNotifications.disableAll') : t('tenders.edit.emailNotifications.enableAll')}
                </Button>
              </div>
              
              <ScrollArea className="max-h-32">
                {selectedUsers.map(userId => {
                  const member = orgMembers.find(m => m.id === userId);
                  if (!member) return null;
                  
                  const isEmailRecipient = selectedEmailRecipients.includes(userId);
                  return (
                    <div key={userId} className="flex items-center space-x-2 py-1">
                      <Checkbox
                        checked={isEmailRecipient}
                        onCheckedChange={() => {
                          const next = isEmailRecipient
                            ? selectedEmailRecipients.filter(id => id !== userId)
                            : [...selectedEmailRecipients, userId];
                          setSelectedEmailRecipients(next);
                          form.setValue("email_recipients", next);
                        }}
                      />
                      <Label className="flex-1 text-sm">
                        {member.name} <span className="text-xs text-muted-foreground">({member.email})</span>
                      </Label>
                    </div>
                  );
                })}
              </ScrollArea>
            </div>
          </div>
        )}
        
        <div className="mt-4 flex justify-end space-x-2">
        </div>
      </div>
    )}
  </div>
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
                    {t('tenders.edit.nameLabel')}
                  </FormLabel>
                  <FormControl>
                    <Input placeholder={t('tenders.edit.namePlaceholder')} {...field} />
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
                    {t('tenders.edit.companyDescriptionLabel')}
                    <HoverCard>
                      <HoverCardTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                          <HelpCircle className="h-3.5 w-3.5" />
                        </Button>
                      </HoverCardTrigger>
                      <HoverCardContent className="w-80 text-xs bg-background border-border text-body-text">
                        <p>{t('tenders.edit.companyDescriptionTooltip')}</p>
                      </HoverCardContent>
                    </HoverCard>
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder={t('tenders.edit.companyDescriptionPlaceholder')}
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
                    {t('tenders.edit.searchPhraseLabel')}
                    <HoverCard>
                      <HoverCardTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary">
                          <HelpCircle className="h-3.5 w-3.5" />
                        </Button>
                      </HoverCardTrigger>
                      <HoverCardContent className="w-80 text-xs bg-background border-border text-body-text">
                        <p>{t('tenders.edit.searchPhraseTooltip')}</p>
                      </HoverCardContent>
                    </HoverCard>
                  </FormLabel>
                  <FormControl>
                    <Input placeholder={t('tenders.edit.searchPhrasePlaceholder')} {...field} />
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
                const selectedGermanCount = Object.keys(GERMAN_SOURCES).filter(id => selectedSources.includes(id)).length;
                const totalGermanCount = Object.keys(GERMAN_SOURCES).length;
                
                return (
                  <FormItem>
                    <FormLabel className="flex items-center gap-2">
                      <Database className="h-4 w-4" />
                      {t('tenders.edit.sourcesLabel')}
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
                              ? t('tenders.edit.selectedSources', { count: selectedSources.length })
                              : t('tenders.edit.selectSources')}
                            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-full p-0" align="start">
                        <Command>
                          <CommandInput placeholder={tCommon('search')} />
                          <CommandList>
                            <CommandEmpty>{t('tenders.filters.noTenders')}</CommandEmpty>
                            <CommandGroup>
                              {Object.entries(POLISH_SOURCES).map(([sourceId, source]) => {
                                const isSelected = selectedSources.includes(sourceId);
                                const source_any = source as any;
                                if (source_any.hidden) return null; // Skip hidden sources
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

                              <CommandItem
                                onSelect={() => setGermanExpanded(!germanExpanded)}
                                className="cursor-pointer"
                              >
                                <div className="flex items-center gap-2 flex-1">
                                  {germanExpanded ? (
                                    <ChevronDown className="h-4 w-4" />
                                  ) : (
                                    <ChevronRight className="h-4 w-4" />
                                  )}
                                  <img 
                                    src="/images/tender_sources/countries/de_flag.jpg" 
                                    alt="German Sources"
                                    className="h-4 w-4 object-contain"
                                  />
                                  <span>German Sources</span>
                                  {selectedGermanCount > 0 && (
                                    <span className="text-xs text-muted-foreground">
                                      ({selectedGermanCount}/{totalGermanCount})
                                    </span>
                                  )}
                                </div>
                              </CommandItem>
                              
                              {germanExpanded && Object.entries(GERMAN_SOURCES).map(([sourceId, source]) => {
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
                );
              }}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <FormLabel className="text-base">
                <div className="flex items-center gap-2">
                  <ClipboardList className="h-4 w-4" />
                  {t('tenders.edit.criteriaLabel')}
                </div>
              </FormLabel>
            </div>

            <DndContext 
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext 
                items={fields.map(field => field.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-6">
                  {fields.map((field, index) => (
                    <SortableCriteriaItem
                      key={field.id}
                      field={field}
                      index={index}
                      form={form}
                      expandedSections={expandedSections}
                      toggleSection={toggleSection}
                      remove={remove}
                      newCriteriaRef={newCriteriaRef}
                      lastAddedIndex={lastAddedIndex}
                      t={t}
                      tCommon={tCommon}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>

              {fields.length === 0 && (
                <p className="mt-2 text-sm text-red-600">
                  {t('tenders.edit.emptyCriteriaError')}
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
                {t('tenders.edit.addCriterion')}
              </Button>
            </div>
            <div className="space-y-4">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setAdvancedFilteringExpanded(!advancedFilteringExpanded)}
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground p-0 h-auto font-normal justify-start"
            >
              <Sparkles className="h-4 w-4" />
              {advancedFilteringExpanded ? t('tenders.edit.hideAdvancedFiltering') : t('tenders.edit.showAdvancedFiltering')}
              {advancedFilteringExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>

            {advancedFilteringExpanded && (
              <FormField
                control={form.control}
                name="filtering_rules"
                render={({ field }) => (
                  <FormItem className="w-full">
                    <FormControl>
                      <Textarea
                        placeholder={t('tenders.edit.filteringRulesPlaceholder')}
                        className="min-h-[100px] w-full"
                        {...field}
                        value={field.value || ''}
                      />
                    </FormControl>
                    <FormDescription className="text-xs text-muted-foreground">
                      {t('tenders.edit.filteringRulesDescription')}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
          </div>

          </div>
          <Button type="submit" className="w-full bg-primary hover:bg-primary-hover shadow text-white" disabled={isLoading}>
            {isLoading ? t('tenders.edit.saving') : t('tenders.edit.saveChanges')}
          </Button>
      </form>
    </Form>
  );
}