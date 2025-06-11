import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Textarea } from "@/components/ui/textarea";
import { RefreshCw, Edit, Trash, MessageSquare } from "lucide-react";
import { format } from 'date-fns';
import { useDashboard } from '@/hooks/useDashboard';
import { useToast } from "@/hooks/use-toast";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Comment } from '@/types/comments';
import { createComment, deleteComment, getComments, updateComment } from '@/utils/commentActions';
import { useTendersTranslations, useCommonTranslations } from "@/hooks/useTranslations";

// Extended comment interface to include user-specific fields for UI
interface CommentWithUser extends Comment {
    user_name?: string;
    user_avatar?: string;
    user_info?: {
        name: string;
        avatar_img?: string;
        [key: string]: any;
    };
}

interface CommentSectionProps {
    tenderId: string;
    refreshTrigger?: boolean;
}

const CommentSection: React.FC<CommentSectionProps> = ({ tenderId, refreshTrigger }) => {
    const [comments, setComments] = useState<CommentWithUser[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isDeleting, setIsDeleting] = useState<string | null>(null);
    const [newComment, setNewComment] = useState('');
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editText, setEditText] = useState('');
    const { user } = useDashboard();
    const { toast } = useToast();
    const t = useTendersTranslations();
    const commonT = useCommonTranslations();

    // Fetch comments for the given tender ID
    const fetchComments = async () => {
        if (!tenderId) return;

        setIsLoading(true);
        try {
            const commentsData = await getComments(tenderId);

            // Extract user data from the user_info field that's already included
            const commentsWithUserData = commentsData.map((comment) => {
                return {
                    ...comment,
                    user_name: comment.user_info?.name || 'Unknown User',
                    user_avatar: comment.user_info?.avatar_img
                };
            });

            setComments(commentsWithUserData);
        } catch (error) {
            console.error('Failed to fetch comments:', error);
            toast({
                title: t('tenders.comments.fetchError'),
                description: t('tenders.comments.fetchErrorDesc'),
                variant: "destructive",
            });
        } finally {
            setIsLoading(false);
        }
    };

    // Handle adding a new comment
    const handleAddComment = async () => {
        if (!tenderId || !newComment.trim()) return;

        setIsSubmitting(true);
        try {
            const newCommentData = await createComment(tenderId, newComment);

            // Add user data to the new comment
            const commentWithUser = {
                ...newCommentData,
                user_name: user?.name || 'You',
                user_avatar: undefined
            };

            setComments(prev => [commentWithUser, ...prev]);
            setNewComment('');

        } catch (error) {
            console.error('Failed to add comment:', error);
            toast({
                title: t('tenders.comments.addError'),
                description: t('tenders.comments.addErrorDesc'),
                variant: "destructive",
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    // Handle editing an existing comment
    const handleEditComment = async () => {
        if (!editingId) return;

        setIsSubmitting(true);
        try {
            const updatedComment = await updateComment(editingId, editText);

            setComments(prev => prev.map(comment =>
                comment._id === editingId ? {
                    ...updatedComment,
                    user_name: comment.user_name,
                    user_avatar: comment.user_avatar
                } : comment
            ));

            setEditingId(null);
            setEditText('');

            toast({
                title: t('tenders.comments.updateSuccess'),
                description: t('tenders.comments.updateSuccessDesc'),
            });
        } catch (error) {
            console.error('Failed to edit comment:', error);
            toast({
                title: t('tenders.comments.updateError'),
                description: t('tenders.comments.updateErrorDesc'),
                variant: "destructive",
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    // Handle deleting a comment
    const handleDeleteComment = async (commentId: string) => {
        setIsDeleting(commentId);
        try {
            await deleteComment(commentId);
            setComments(prev => prev.filter(comment => comment._id !== commentId));

            toast({
                title: t('tenders.comments.deleteSuccess'),
                description: t('tenders.comments.deleteSuccessDesc'),
            });
        } catch (error) {
            console.error('Failed to delete comment:', error);
            toast({
                title: t('tenders.comments.deleteError'),
                description: t('tenders.comments.deleteErrorDesc'),
                variant: "destructive",
            });
        } finally {
            setIsDeleting(null);
        }
    };

    // Fetch comments when the component mounts or tenderId changes
    useEffect(() => {
        if (tenderId) {
            fetchComments();
        }
    }, [tenderId, refreshTrigger]);

    // Format date strings for display
    const formatDate = (dateString: string): string => {
        try {
            return format(new Date(dateString), "dd.MM.yyyy, HH:mm");
        } catch (e) {
            return t('common.dates.invalidDate');
        }
    };

    return (
        <div className="space-y-4">
            {/* Header with refresh button */}
            <div className="flex justify-between items-center">
                <h3 className="font-semibold">{t('tenders.comments.title')}</h3>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchComments}
                    disabled={isLoading}
                    className="h-8 w-8 p-0"
                    title={t('tenders.comments.refreshComments')}
                >
                    <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                    <span className="sr-only">{t('tenders.comments.refreshComments')}</span>
                </Button>
            </div>

            {/* Comment input form */}
            <div className="flex gap-3">
                <div className="flex-shrink-0">
                    <Avatar className="h-8 w-8">
                        <AvatarImage src="" />
                        <AvatarFallback>{user?.name?.[0]?.toUpperCase() || 'U'}</AvatarFallback>
                    </Avatar>
                </div>
                <div className="flex-grow space-y-2">
                    <Textarea
                        placeholder={t('tenders.comments.addCommentPlaceholder')}
                        value={newComment}
                        onChange={(e) => setNewComment(e.target.value)}
                        className="min-h-[80px] resize-none"
                    />
                    <div className="flex justify-end">
                        <Button
                            onClick={handleAddComment}
                            disabled={!newComment.trim() || isSubmitting}
                            size="sm"
                        >
                            {isSubmitting ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2" />
                                    {t('tenders.comments.adding')}
                                </>
                            ) : (
                                t('tenders.comments.addComment')
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Existing comments */}
            <div className="space-y-4">
                {isLoading && comments.length === 0 ? (
                    <div className="text-sm text-muted-foreground p-2 flex items-center justify-center">
                        <span className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin mr-2" />
                        {t('tenders.comments.loading')}
                    </div>
                ) : comments.length > 0 ? (
                    comments.map(comment => (
                        <Card key={comment._id} className="p-3 border border-neutral-200">
                            <div className="flex gap-3">
                                <div className="flex-shrink-0">
                                    <Avatar className="h-8 w-8">
                                        <AvatarImage src={comment.user_avatar || ''} />
                                        <AvatarFallback>{comment.user_name?.[0]?.toUpperCase() || 'U'}</AvatarFallback>
                                    </Avatar>
                                </div>
                                <div className="flex-grow space-y-2">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <span className="font-medium text-sm">{comment.user_name}</span>
                                            <span className="text-xs text-muted-foreground ml-2">
                                                {formatDate(comment.created_at)}
                                            </span>
                                            {comment.updated_at && (
                                                <Badge variant="outline" className="ml-2 text-[10px] px-1 py-0">
                                                    {t('tenders.comments.edited')}
                                                </Badge>
                                            )}
                                        </div>
                                        {String(user?._id) === String(comment.user_id) && (
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                        <span className="sr-only">Open menu</span>
                                                        <svg width="15" height="3" viewBox="0 0 15 3" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                            <path d="M1.5 1.5C1.5 2.15 2.05 2.7 2.7 2.7C3.35 2.7 3.9 2.15 3.9 1.5C3.9 0.85 3.35 0.3 2.7 0.3C2.05 0.3 1.5 0.85 1.5 1.5ZM6.3 1.5C6.3 2.15 6.85 2.7 7.5 2.7C8.15 2.7 8.7 2.15 8.7 1.5C8.7 0.85 8.15 0.3 7.5 0.3C6.85 0.3 6.3 0.85 6.3 1.5ZM11.1 1.5C11.1 2.15 11.65 2.7 12.3 2.7C12.95 2.7 13.5 2.15 13.5 1.5C13.5 0.85 12.95 0.3 12.3 0.3C11.65 0.3 11.1 0.85 11.1 1.5Z" fill="currentColor"/>
                                                        </svg>
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => {
                                                        setEditingId(comment._id);
                                                        setEditText(comment.text);
                                                    }}>
                                                        <Edit className="mr-2 h-4 w-4" />
                                                        <span>{t('tenders.comments.edit')}</span>
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem
                                                        onClick={() => handleDeleteComment(comment._id)}
                                                        className="text-destructive"
                                                        disabled={isDeleting === comment._id}
                                                    >
                                                        {isDeleting === comment._id ? (
                                                            <>
                                                                <span className="w-4 h-4 border-2 border-destructive/20 border-t-destructive rounded-full animate-spin mr-2" />
                                                                <span>{t('tenders.comments.deleting')}</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <Trash className="mr-2 h-4 w-4" />
                                                                <span>{t('tenders.comments.delete')}</span>
                                                            </>
                                                        )}
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        )}
                                    </div>

                                    {editingId === comment._id ? (
                                        <div className="space-y-2">
                                            <Textarea
                                                value={editText}
                                                onChange={(e) => setEditText(e.target.value)}
                                                className="min-h-[60px] resize-none"
                                            />
                                            <div className="flex justify-end gap-2">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => {
                                                        setEditingId(null);
                                                        setEditText('');
                                                    }}
                                                    disabled={isSubmitting}
                                                >
                                                    {commonT('cancel')}
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    onClick={handleEditComment}
                                                    disabled={!editText.trim() || isSubmitting}
                                                >
                                                    {isSubmitting ? (
                                                        <>
                                                            <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2" />
                                                            {t('tenders.comments.saving')}
                                                        </>
                                                    ) : (
                                                        commonT('save')
                                                    )}
                                                </Button>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-sm">{comment.text}</p>
                                    )}
                                </div>
                            </div>
                        </Card>
                    ))
                ) : (
                    <div className="text-center py-6 text-muted-foreground">
                        <MessageSquare className="h-10 w-10 mx-auto mb-2 opacity-20" />
                        <p className="text-sm">{t('tenders.comments.noComments')}</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CommentSection;