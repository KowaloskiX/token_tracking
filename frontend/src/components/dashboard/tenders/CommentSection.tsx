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
    refreshTrigger?: boolean; // Add optional prop to trigger refresh
}

const CommentSection: React.FC<CommentSectionProps> = ({ tenderId, refreshTrigger }) => {
    // State variables for managing comments, loading states, and form inputs
    const [comments, setComments] = useState<CommentWithUser[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isDeleting, setIsDeleting] = useState<string | null>(null);
    const [newComment, setNewComment] = useState('');
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editText, setEditText] = useState('');
    const { user } = useDashboard(); // Current logged-in user
    const { toast } = useToast(); // Toast notifications

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
                title: "Nie udało się pobrać komentarzy",
                description: "Wystąpił problem podczas ładowania komentarzy. Spróbuj ponownie później.",
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
                user_avatar: undefined // User doesn't have avatar property
            };

            setComments(prev => [commentWithUser, ...prev]);
            setNewComment('');

            // Remove this toast notification
            // toast({
            //     title: "Komentarz dodany",
            //     description: "Twój komentarz został pomyślnie dodany.",
            // });
        } catch (error) {
            console.error('Failed to add comment:', error);
            toast({
                title: "Nie udało się dodać komentarza",
                description: "Wystąpił problem podczas dodawania komentarza. Spróbuj ponownie później.",
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
                title: "Komentarz zaktualizowany",
                description: "Twój komentarz został pomyślnie zaktualizowany.",
            });
        } catch (error) {
            console.error('Failed to edit comment:', error);
            toast({
                title: "Nie udało się zaktualizować komentarza",
                description: "Wystąpił problem podczas aktualizacji komentarza. Spróbuj ponownie później.",
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
                title: "Komentarz usunięty",
                description: "Komentarz został pomyślnie usunięty.",
            });
        } catch (error) {
            console.error('Failed to delete comment:', error);
            toast({
                title: "Nie udało się usunąć komentarza",
                description: "Wystąpił problem podczas usuwania komentarza. Spróbuj ponownie później.",
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
    }, [tenderId, refreshTrigger]); // Add refreshTrigger to dependencies

    // Format date strings for display
    const formatDate = (dateString: string): string => {
        try {
            return format(new Date(dateString), "dd.MM.yyyy, HH:mm");
        } catch (e) {
            return "Invalid date";
        }
    };

    return (
        <div className="space-y-4">
            {/* Header with refresh button */}
            <div className="flex justify-between items-center">
                <h3 className="font-semibold">Komentarze</h3>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchComments}
                    disabled={isLoading}
                    className="h-8 w-8 p-0"
                    title="Refresh comments"
                >
                    <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                    <span className="sr-only">Odśwież komentarze</span>
                </Button>
            </div>

            {/* Comment input form */}
            <div className="flex gap-3">
                <div className="flex-shrink-0">
                    <Avatar className="h-8 w-8">
                        <AvatarImage src="" /> {/* Remove user?.avatar_img */}
                        <AvatarFallback>{user?.name?.[0]?.toUpperCase() || 'U'}</AvatarFallback>
                    </Avatar>
                </div>
                <div className="flex-grow space-y-2">
                    <Textarea
                        placeholder="Dodaj komentarz..."
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
                                    Dodawanie...
                                </>
                            ) : (
                                "Dodaj komentarz"
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
                        Ładowanie komentarzy...
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
                                                    edytowany
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
                                                        <span>Edytuj</span>
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem
                                                        onClick={() => handleDeleteComment(comment._id)}
                                                        className="text-destructive"
                                                        disabled={isDeleting === comment._id}
                                                    >
                                                        {isDeleting === comment._id ? (
                                                            <>
                                                                <span className="w-4 h-4 border-2 border-destructive/20 border-t-destructive rounded-full animate-spin mr-2" />
                                                                <span>Usuwanie...</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <Trash className="mr-2 h-4 w-4" />
                                                                <span>Usuń</span>
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
                                                    Anuluj
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    onClick={handleEditComment}
                                                    disabled={!editText.trim() || isSubmitting}
                                                >
                                                    {isSubmitting ? (
                                                        <>
                                                            <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2" />
                                                            Zapisywanie...
                                                        </>
                                                    ) : (
                                                        "Zapisz"
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
                        <p className="text-sm">Brak komentarzy. Dodaj pierwszy!</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CommentSection;