"use client";

import { Separator } from "@/components/ui/separator";
import { CreateInvitationForm } from "@/components/dashboard/settings/forms/CreateInvitationForm";
import { TeamMembersList } from "@/components/dashboard/settings/forms/TeamMembersList";
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

export default function OrganizationPage() {
  const [mounted, setMounted] = useState(false);
  const t = useTranslations('settings.pages.organization');

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="h-[calc(100vh-128px)] overflow-y-auto scrollbar-hide space-y-6">
      <div>
        <h3 className="text-lg font-medium">
          {mounted ? t('title') : 'Organizacja'}
        </h3>
        <p className="text-sm text-muted-foreground">
          {mounted ? t('description') : 'Zarządzaj swoim zespołem i zapraszaj nowych członków do współpracy.'}
        </p>
      </div>
      
      <Separator />
      
      <CreateInvitationForm />
      
      <TeamMembersList />
    </div>
  );
}