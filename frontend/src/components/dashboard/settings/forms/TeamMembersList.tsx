"use client";

import { useState, useEffect } from "react";
import { useTranslations } from 'next-intl';
import { 
    Table, 
    TableBody, 
    TableCell, 
    TableHead, 
    TableHeader, 
    TableRow 
} from "@/components/ui/table";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { AlertCircle, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { getOrganizationMembers, updateMemberRole, removeMember, leaveOrganization } from "@/utils/organizationActions";
import { useRouter } from "next/navigation";

interface TeamMember {
    id: string;
    name: string;
    email: string;
    role: string;
    isCurrentUser: boolean;
}

export function TeamMembersList() {
    const router = useRouter();
    const [members, setMembers] = useState<TeamMember[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notInOrganization, setNotInOrganization] = useState(false);
    const [pendingChanges, setPendingChanges] = useState<Record<string, string>>({});
    const [mounted, setMounted] = useState(false);
    const { toast } = useToast();
    const [isCurrentUserAdmin, setIsCurrentUserAdmin] = useState(false);
    const t = useTranslations('settings.organization');

    useEffect(() => {
        setMounted(true);
    }, []);

    useEffect(() => {
        const fetchMembers = async () => {
            try {
                const data = await getOrganizationMembers();
                setMembers(data);
                
                const currentUser = data.find((member: { isCurrentUser: any; }) => member.isCurrentUser);
                setIsCurrentUserAdmin(currentUser?.role === "admin");
                
                setNotInOrganization(false);
            } catch (err: any) {
                if (err.message === "No organization found." || 
                    err.message === "Nie jesteś członkiem żadnej organizacji.") {
                    setNotInOrganization(true);
                } else {
                    setError(err.message || "Failed to fetch team members");
                }
            } finally {
                setLoading(false);
            }
        };

        if (mounted) {
            fetchMembers();
        }
    }, [mounted]);

    const handleRoleChange = (memberId: string, newRole: string) => {
        setPendingChanges((prev) => ({
            ...prev,
            [memberId]: newRole,
        }));
    };

    const handleSaveRole = async (memberId: string) => {
        if (!pendingChanges[memberId]) return;
        
        try {
            await updateMemberRole(memberId, pendingChanges[memberId]);
            toast({
                title: t('invite_success'),
                description: t('role_updated'),
            });
            
            setMembers((prev) => prev.map(member => 
                member.id === memberId 
                    ? { ...member, role: pendingChanges[memberId] } 
                    : member
            ));
            
            setPendingChanges((prev) => {
                const { [memberId]: _, ...rest } = prev;
                return rest;
            });
        } catch (err: any) {
            toast({
                variant: "destructive",
                title: t('invite_error'),
                description: err.message || t('role_update_error'),
            });
        }
    };

    const handleRemoveMember = async (memberId: string) => {
        if (!confirm(t('remove_confirmation'))) return;
        
        try {
            await removeMember(memberId);
            toast({
                title: t('invite_success'),
                description: t('member_removed'),
            });
            
            setMembers((prev) => prev.filter(member => member.id !== memberId));
        } catch (err: any) {
            toast({
                variant: "destructive",
                title: t('invite_error'),
                description: err.message || t('member_remove_error'),
            });
        }
    };

    const handleLeaveOrganization = async () => {
        if (!confirm(t('leave_confirmation'))) return;
        
        try {
            await leaveOrganization();
            toast({
                title: t('invite_success'),
                description: t('left_organization'),
            });
            
            window.location.reload();
        } catch (err: any) {
            toast({
                variant: "destructive",
                title: t('invite_error'),
                description: err.message || t('leave_error'),
            });
        }
    };

    if (!mounted) {
        return (
            <div className="bg-card rounded-lg border p-6">
                <h3 className="text-lg font-medium mb-4">{t('team_members')}</h3>
                <div className="text-sm text-muted-foreground">{t('loading')}</div>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="flex justify-center items-center p-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (notInOrganization) {
        return (
            <div className="bg-card rounded-lg border p-6">
                <h3 className="text-lg font-medium mb-4">{t('team_members')}</h3>
                <p className="text-muted-foreground">{t('not_in_organization')}</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-destructive/10 p-4 rounded-md flex items-center gap-2 text-destructive">
                <AlertCircle className="h-5 w-5" />
                <p>{error}</p>
            </div>
        );
    }

    return (
        <div className="bg-card rounded-lg border p-6">
            <h3 className="text-lg font-medium mb-4">{t('team_members')}</h3>
            
            {members.length === 0 ? (
                <p className="text-muted-foreground">{t('no_members')}</p>
            ) : (
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>{t('user')}</TableHead>
                            <TableHead>{t('email')}</TableHead>
                            <TableHead>{t('role')}</TableHead>
                            <TableHead className="text-right">{t('actions')}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {members.map((member) => (
                            <TableRow key={member.id}>
                                <TableCell className="font-medium">{member.name}</TableCell>
                                <TableCell>{member.email}</TableCell>
                                <TableCell>
                                    <Select
                                        value={pendingChanges[member.id] || member.role}
                                        onValueChange={(value) => handleRoleChange(member.id, value)}
                                        disabled={member.isCurrentUser || !isCurrentUserAdmin}
                                    >
                                        <SelectTrigger className="w-[180px]">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="admin">{t('roles.admin')}</SelectItem>
                                            <SelectItem value="member">{t('roles.member')}</SelectItem>
                                            <SelectItem value="guest">{t('roles.guest')}</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </TableCell>
                                <TableCell className="text-right space-x-2">
                                    {pendingChanges[member.id] && isCurrentUserAdmin && (
                                        <Button 
                                            variant="outline" 
                                            size="sm"
                                            onClick={() => handleSaveRole(member.id)}
                                        >
                                            {t('save')}
                                        </Button>
                                    )}
                                    
                                    {member.isCurrentUser ? (
                                        <Button 
                                            variant="destructive" 
                                            size="sm"
                                            className="w-20"
                                            onClick={handleLeaveOrganization}
                                        >
                                            {t('leave')}
                                        </Button>
                                    ) : (
                                        isCurrentUserAdmin && (
                                            <Button 
                                                variant="destructive" 
                                                size="sm"
                                                className="w-20"
                                                onClick={() => handleRemoveMember(member.id)}
                                            >
                                                {t('remove')}
                                            </Button>
                                        )
                                    )}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            )}
        </div>
    );
}