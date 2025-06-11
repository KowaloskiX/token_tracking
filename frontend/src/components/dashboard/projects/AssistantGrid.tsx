import React, { useEffect, useState, useRef } from 'react';
import { PanelsTopLeft, Loader2, Plus, Pencil, MoreHorizontal, Trash, ArrowUpAZ, CalendarRange, SortAscIcon, Settings, Settings2, Share2, X } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getUserAssistants, deleteAssistant, updateAssistant } from '@/utils/assistantActions';
import { useDashboard } from '@/hooks/useDashboard';
import { Assistant } from '@/types';
import CreateAssistantForm from '@/components/dashboard/forms/CreateAssistantForm';
import { useRouter } from 'next/navigation';
import { DeletePopup } from '../popup/DeletePopup';
import { checkOrCreateConversation } from "@/utils/conversationActions";
import { Users } from 'lucide-react';
import AssignUsersToAssistantModal from '@/components/dashboard/tenders/AssignUsersToAssistantModal';
import { useTranslations } from 'next-intl';

let memberIds: string[] | undefined;

export async function getMemberIds(): Promise<string[]> {
  if (memberIds) return memberIds;

  const token = localStorage.getItem('token');
  if (!token) throw new Error('No auth token in localStorage');

  const res = await fetch(
    `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/organizations/members`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);

  type Member = { id: string };
  type Wrapped = { members?: Member[] };

  const json = (await res.json()) as Member[] | Wrapped;

  const list: Member[] = Array.isArray(json)
    ? json
    : json.members ?? [];

  memberIds = list.map((m) => m.id);
  return memberIds;
}

type SortType = 'name' | 'date' | null;
type SortDirection = 'asc' | 'desc';

interface SortConfig {
  type: SortType;
  direction: SortDirection;
}

const AssistantGrid = () => {
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateFormOpen, setIsCreateFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | undefined | null>(null);
  const [editingName, setEditingName] = useState('');
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    type: null,
    direction: 'asc'
  });
  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean;
    assistant: Assistant | null;
    isLoading: boolean;
  }>({ isOpen: false, assistant: null, isLoading: false });
  const editInputRef = useRef<HTMLInputElement>(null);

  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assistantForAssign, setAssistantForAssign] = useState<Assistant | null>(null);
  const [assignedUsers, setAssignedUsers] = useState<string[]>([]);

  const { user, setCurrentAssistant, setCurrentConversation } = useDashboard();
  const router = useRouter();

  // Translation hooks
  const t = useTranslations('dashboard.projects');
  const tCommon = useTranslations('common');
  const tErrors = useTranslations('errors.general');

  useEffect(() => {
    const fetchAssistants = async () => {
      try {
        if (!user?._id) return;
        const fetchedAssistants = await getUserAssistants(user._id, user.org_id || '');
        setAssistants(fetchedAssistants);
      } catch (err) {
        setError(t('failed_to_load'));
        console.error('Error loading assistants:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAssistants();
  }, [user?._id, user?.org_id, t]);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingId]);

  const formatDate = (dateString: string | Date | undefined) => {
    if (!dateString) return tCommon('no_data');
    
    try {
      return new Date(dateString).toLocaleDateString('pl', {
        month: 'short',
        day: 'numeric'
      });
    } catch (e) {
      return `${tErrors('invalid_input')}: ${e}`;
    }
  };

  const handleNameEdit = (assistant: Assistant) => {
    setEditingId(assistant._id);
    setEditingName(assistant.name);
  };

  const handleNameSave = async (assistant: Assistant) => {
    try {
      await updateAssistant(assistant, { name: editingName });
      setAssistants(assistants.map(a => 
        a._id === assistant._id ? { ...a, name: editingName } : a
      ));
    } catch (err) {
      console.error('Error updating assistant name:', err);
    }
    setEditingId(null);
  };

  const getSortedAssistants = (): Assistant[] => {
    if (!sortConfig.type) return assistants;

    return [...assistants].sort((a, b) => {
      let comparison = 0;
      
      if (sortConfig.type === 'name') {
        comparison = a.name.localeCompare(b.name);
      } else if (sortConfig.type === 'date' && a.created_at && b.created_at) {
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }

      return sortConfig.direction === 'asc' ? comparison : -comparison;
    });
  };

  const handleSort = (type: SortType) => {
    setSortConfig(prevConfig => ({
      type,
      direction: 
        prevConfig.type === type 
          ? prevConfig.direction === 'asc' 
            ? 'desc' 
            : 'asc'
          : 'asc'
    }));
  };

  const handleDeleteConfirm = async (e: React.MouseEvent): Promise<void> => {
    e.stopPropagation();
    if (!deleteDialog.assistant) return;
    
    setDeleteDialog(prev => ({ ...prev, isLoading: true }));

    try {
      await deleteAssistant(deleteDialog.assistant);
      setAssistants(prev => prev.filter(a => a._id !== deleteDialog.assistant?._id));
    } finally {
      setDeleteDialog({ isOpen: false, assistant: null, isLoading: false });
    }
  };

  const handleDeleteClick = (assistant: Assistant, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteDialog({ isOpen: true, assistant, isLoading: false });
  };

  const handleOpenChange = (open: boolean) => {
    if (deleteDialog.isLoading) return;
    setDeleteDialog(prev => ({ ...prev, isOpen: open }));
  };

  const handleKeyDown = (e: React.KeyboardEvent, assistant: Assistant) => {
    if (e.key === 'Enter') {
      handleNameSave(assistant);
    } else if (e.key === 'Escape') {
      setEditingId(null);
    }
  };

  const openAssistant = async (assistant: Assistant) => {
    if (editingId === assistant._id) return;
    setCurrentAssistant(assistant);
    setCurrentConversation(null);
    try {
      const conversation = await checkOrCreateConversation(
        user?._id || '',
        assistant._id,
        assistant.org_id 
      );

      router.push(`/dashboard/tenders/chat/${conversation._id}`);
    } catch (error) {
      console.error("Error opening conversation:", error);
    }
  };

  const handleShareToggle = async (assistant: Assistant, e: React.MouseEvent) => {
    e.stopPropagation();
    const memberIds = await getMemberIds();
    const isShared = Boolean(assistant.org_id);

    const updateData: Partial<Assistant> = {
      org_id: isShared ? undefined : user?.org_id ?? undefined,
      assigned_users: isShared ? [] : memberIds,
    };

    try {
      await updateAssistant(assistant, updateData);

      setAssistants(prev =>
        prev.map(a =>
          a._id === assistant._id ? { ...a, ...updateData } : a
        )
      );
    } catch (err) {
      console.error('Error toggling share status:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  return (
    <>
      <div className="p-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-bold">{t('title')}</h1>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="p-2 hover:bg-secondary outline-none rounded-md text-sm flex items-center gap-2">
                  <span className="text-neutral-600">{tCommon('sort')}</span>
                  <Settings2 className="w-4 h-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem 
                  className="flex items-center gap-2 cursor-pointer"
                  onClick={() => handleSort('name')}
                >
                  <ArrowUpAZ className="w-4 h-4" />
                  <span className="flex-1">{tCommon('sort_by_name')}</span>
                  {sortConfig.type === 'name' && (
                    <span className="text-xs text-muted-foreground">
                      {sortConfig.direction === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </DropdownMenuItem>
                <DropdownMenuItem 
                  className="flex items-center gap-2 cursor-pointer"
                  onClick={() => handleSort('date')}
                >
                  <CalendarRange className="w-4 h-4" />
                  <span className="flex-1">{tCommon('sort_by_date')}</span>
                  {sortConfig.type === 'date' && (
                    <span className="text-xs text-muted-foreground">
                      {sortConfig.direction === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mt-6">
            {/* Create New Card */}
            <Card 
              className="group cursor-pointer rounded-xl transition-all duration-300 ease-in-out border-2 border-dashed border-body-text/50 hover:border-body-text flex flex-col items-center justify-center py-6"
              onClick={() => setIsCreateFormOpen(true)}
            >
              <div className="flex flex-col items-center space-y-2">
                <div className="p-2 bg-secondary rounded-md group-hover:bg-secondary-hover transition-colors">
                  <Plus className="w-4 h-4 text-primary" />
                </div>
                <p className="text-sm font-medium text-foreground">
                  {t('create_new')}
                </p>
              </div>
            </Card>

            {getSortedAssistants().map((assistant) => (
              <Card 
                key={assistant._id}
                className="group cursor-pointer bg-white/40 transition-all duration-300 hover:scale-102 hover:shadow-md py-2 rounded-xl"
                onClick={() => openAssistant(assistant)}
              >
                <CardHeader className="p-3 pb-2 space-y-0">
                  <div className="flex items-center justify-between mb-2">
                    <div className="p-2 bg-secondary rounded-md group-hover:bg-secondary-hover transition-colors">
                      {assistant.icon ? (
                        <img 
                          src={assistant.icon} 
                          alt={assistant.name} 
                          className="w-4 h-4"
                        />
                      ) : (
                        <PanelsTopLeft className="w-4 h-4 text-primary" />
                      )}
                    </div>
                    {(assistant.owner_id === user?._id || user?.role === 'admin') && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                        <button className="p-1 hover:bg-secondary rounded-md">
                          <MoreHorizontal className="w-4 h-4 text-foreground" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {user?.org_id && (
                          <DropdownMenuItem
                            className="focus:bg-secondary"
                            onClick={(e) => handleShareToggle(assistant, e)}
                          >
                            {(assistant.assigned_users?.length ?? 0) > 0 ? (
                              <>
                                <X className="w-4 h-4 mr-2" />
                                {t('stop_sharing')}
                              </>
                            ) : (
                              <>
                                <Share2 className="w-4 h-4 mr-2" />
                                {t('share_in_organization')}
                              </>
                            )}
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem onClick={(e) => {
                          e.stopPropagation();
                          setAssistantForAssign(assistant);
                          setAssignModalOpen(true);
                        }}>
                          <Users className="w-4 h-4 mr-2" />
                          {t('assign_users')}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-red-600 focus:text-red-600 focus:bg-secondary"
                          onClick={(e) => handleDeleteClick(assistant, e)}
                        >
                          <Trash className="w-4 h-4 mr-2" />
                          {tCommon('delete')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                    )}
                  </div>
                  <CardTitle className="text-sm font-semibold truncate relative group">
                    {editingId === assistant._id ? (
                      <input
                        ref={editInputRef}
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onBlur={() => handleNameSave(assistant)}
                        onKeyDown={(e) => handleKeyDown(e, assistant)}
                        className="w-full bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-primary rounded px-1"
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <>
                        {assistant.name}
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleNameEdit(assistant);
                          }}
                          className="ml-2 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Pencil className="w-3 h-3 text-neutral-400 hover:text-primary ml-1" />
                        </button>
                      </>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-3 pt-0 relative">
                  {assistant.description && (
                    <p className="text-xs text-foreground mb-1 line-clamp-2">
                      {assistant.description}
                    </p>
                  )}
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-foreground">
                      <span className="hidden sm:block">{t('created')}</span> {formatDate(assistant.created_at)}
                    </p>
                    <Badge
                      variant={(assistant.assigned_users?.length ?? 0) > 0 ? "default" : "secondary"}
                      className="text-xs font-medium"
                    >
                      {(assistant.assigned_users?.length ?? 0) > 0 ? t('shared') : t('private')}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>

      <CreateAssistantForm 
        open={isCreateFormOpen} 
        onOpenChange={setIsCreateFormOpen} 
      />

      <DeletePopup 
        isOpen={deleteDialog.isOpen}
        onOpenChange={handleOpenChange} 
        onConfirm={handleDeleteConfirm}
        title={t('delete_project')}
        description={t('delete_project_confirm')}
        isLoading={deleteDialog.isLoading}
      />
     {assistantForAssign && (
     <AssignUsersToAssistantModal
       assistant={assistantForAssign}
       open={assignModalOpen}
       onOpenChange={(o) => {
         setAssignModalOpen(o);
         if (!o) setAssistantForAssign(null);
       }}
       onAssignmentsChange={(newIds) => {
         setAssistants(prev =>
           prev.map(a =>
             a._id === assistantForAssign._id
               ? { ...a, assigned_users: newIds }
               : a
           )
         );
         setAssistantForAssign(a =>
           a ? { ...a, assigned_users: newIds } : null
         );
       }}
     />
   )}
    </>
  );
};

export default AssistantGrid;