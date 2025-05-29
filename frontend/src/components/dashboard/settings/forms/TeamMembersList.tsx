"use client";

import { useState, useEffect } from "react";
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
import { useRouter } from "next/navigation"; // Import router for navigation after leaving

// Type for team member
interface TeamMember {
    id: string;
    name: string;
    email: string;
    role: string;
    isCurrentUser: boolean;
}

export function TeamMembersList() {
    const router = useRouter(); // Initialize router
    // Add an additional state for organization membership
    const [members, setMembers] = useState<TeamMember[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notInOrganization, setNotInOrganization] = useState(false);  // Add this state
    const [pendingChanges, setPendingChanges] = useState<Record<string, string>>({});
    const { toast } = useToast();
    const [isCurrentUserAdmin, setIsCurrentUserAdmin] = useState(false);

    // Fetch team members when the component mounts
    useEffect(() => {
        const fetchMembers = async () => {
            try {
                const data = await getOrganizationMembers();
                setMembers(data);
                
                // Determine if the current user is an admin
                const currentUser = data.find((member: { isCurrentUser: any; }) => member.isCurrentUser);
                setIsCurrentUserAdmin(currentUser?.role === "admin");
                
                setNotInOrganization(false);
            } catch (err: any) {
                // Check if this is the specific "not in organization" error
                if (err.message === "No organization found." || 
                    err.message === "Nie jesteś członkiem żadnej organizacji.") {
                    setNotInOrganization(true);
                } else {
                    // Handle other errors
                    setError(err.message || "Nie udało się pobrać listy członków zespołu");
                }
            } finally {
                setLoading(false);
            }
        };

        fetchMembers();
    }, []);

    // Handle role change for a specific member
    const handleRoleChange = (memberId: string, newRole: string) => {
        setPendingChanges((prev) => ({
            ...prev,
            [memberId]: newRole,
        }));
    };

    // Save the updated role for a specific member
    const handleSaveRole = async (memberId: string) => {
        if (!pendingChanges[memberId]) return;
        
        try {
            // Update the member's role via API
            await updateMemberRole(memberId, pendingChanges[memberId]);
            toast({
                title: "Sukces",
                description: "Rola użytkownika została zaktualizowana",
            });
            
            // Update the local state with the new role
            setMembers((prev) => prev.map(member => 
                member.id === memberId 
                    ? { ...member, role: pendingChanges[memberId] } 
                    : member
            ));
            
            // Remove the pending change for the member
            setPendingChanges((prev) => {
                const { [memberId]: _, ...rest } = prev;
                return rest;
            });
        } catch (err: any) {
            // Handle errors during role update
            toast({
                variant: "destructive",
                title: "Błąd",
                description: err.message || "Nie udało się zaktualizować roli",
            });
        }
    };

    // Remove a member from the organization
    const handleRemoveMember = async (memberId: string) => {
        if (!confirm("Czy na pewno chcesz usunąć tego użytkownika z organizacji?")) return;
        
        try {
            // Remove the member via API
            await removeMember(memberId);
            toast({
                title: "Sukces",
                description: "Użytkownik został usunięty z organizacji",
            });
            
            // Update the local state to remove the member
            setMembers((prev) => prev.filter(member => member.id !== memberId));
        } catch (err: any) {
            // Handle errors during member removal
            toast({
                variant: "destructive",
                title: "Błąd",
                description: err.message || "Nie udało się usunąć użytkownika",
            });
        }
    };

    // Add handler for leaving the organization
    const handleLeaveOrganization = async () => {
        if (!confirm("Czy na pewno chcesz opuścić organizację? Nie będziesz mieć dostępu do zasobów organizacji.")) return;
        
        try {
            await leaveOrganization();
            toast({
                title: "Sukces",
                description: "Opuściłeś organizację.",
            });
            
            // Refresh the page to clear org_id and reload the state
            // router.refresh(); // For Next.js
            // Alternatively, use window.location.reload() if router.refresh() doesn't work
            window.location.reload();
        } catch (err: any) {
            toast({
                variant: "destructive",
                title: "Błąd",
                description: err.message || "Nie udało się opuścić organizacji",
            });
        }
    };

    // Show a loading spinner while data is being fetched
    if (loading) {
        return (
            <div className="flex justify-center items-center p-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Show the "not in organization" message with normal styling
    if (notInOrganization) {
        return (
            <div className="bg-card rounded-lg border p-6">
                <h3 className="text-lg font-medium mb-4">Członkowie zespołu</h3>
                <p className="text-muted-foreground">Nie jesteś członkiem żadnej organizacji.</p>
            </div>
        );
    }

    // Show an error message if fetching data failed for other reasons
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
            <h3 className="text-lg font-medium mb-4">Członkowie zespołu</h3>
            
            {/* Show a message if there are no team members */}
            {members.length === 0 ? (
                <p className="text-muted-foreground">Brak członków zespołu.</p>
            ) : (
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Użytkownik</TableHead>
                            <TableHead>Email</TableHead>
                            <TableHead>Rola</TableHead>
                            <TableHead className="text-right">Akcje</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {members.map((member) => (
                            <TableRow key={member.id}>
                                <TableCell className="font-medium">{member.name}</TableCell>
                                <TableCell>{member.email}</TableCell>
                                <TableCell>
                                    {/* Dropdown to select a role for the member */}
                                    <Select
                                        value={pendingChanges[member.id] || member.role}
                                        onValueChange={(value) => handleRoleChange(member.id, value)}
                                        disabled={member.isCurrentUser || !isCurrentUserAdmin} // Disable for current user OR if current user isn't admin
                                    >
                                        <SelectTrigger className="w-[180px]">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="admin">Administrator</SelectItem>
                                            <SelectItem value="member">Członek zespołu</SelectItem>
                                            <SelectItem value="guest">Gość</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </TableCell>
                                <TableCell className="text-right space-x-2">
                                    {/* Show save button if there are pending changes */}
                                    {pendingChanges[member.id] && isCurrentUserAdmin && (
                                        <Button 
                                            variant="outline" 
                                            size="sm"
                                            onClick={() => handleSaveRole(member.id)}
                                        >
                                            Zapisz
                                        </Button>
                                    )}
                                    
                                    {/* Show "Opuść" button for current user, "Usuń" button for others */}
                                    {member.isCurrentUser ? (
                                        <Button 
                                            variant="destructive" 
                                            size="sm"
                                            className="w-20" // Fixed width of 5rem (80px)
                                            onClick={handleLeaveOrganization}
                                        >
                                            Opuść
                                        </Button>
                                    ) : (
                                        // Only show "Usuń" button if current user is admin
                                        isCurrentUserAdmin && (
                                            <Button 
                                                variant="destructive" 
                                                size="sm"
                                                className="w-20" // Same fixed width
                                                onClick={() => handleRemoveMember(member.id)}
                                            >
                                                Usuń
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