"use client"; // This directive indicates that the component is a client-side React component.

import { Separator } from "@/components/ui/separator"; // Importing a UI separator component.
import { CreateInvitationForm } from "@/components/dashboard/settings/forms/CreateInvitationForm"; // Importing the CreateInvitationForm component for inviting new team members.
import { TeamMembersList } from "@/components/dashboard/settings/forms/TeamMembersList"; // Importing the TeamMembersList component to display the list of team members.

export default function OrganizationPage() {
  return (
    <div className="h-[calc(100vh-128px)] overflow-y-auto scrollbar-hide space-y-6">
      {/* Header section with title and description */}
      <div>
        <h3 className="text-lg font-medium">Organizacja</h3> {/* Page title */}
        <p className="text-sm text-muted-foreground">
          Zarządzaj swoim zespołem i zapraszaj nowych członków do współpracy. {/* Page description */}
        </p>
      </div>
      
      <Separator /> {/* Visual separator between the header and the content sections */}
      
      {/* Include the invitation form component for adding new team members */}
      <CreateInvitationForm />
      
      {/* Include the team members list component to display existing team members */}
      <TeamMembersList />
    </div>
  );
}