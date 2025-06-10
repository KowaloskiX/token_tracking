"use client";

import { ProfileForm } from "@/components/dashboard/settings/forms/ProfileForm";
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

export default function SettingsProfilePage() {
  const [mounted, setMounted] = useState(false);
  const t = useTranslations('settings.pages.account');

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="h-[calc(100vh-128px)] overflow-y-auto scrollbar-hide">
        <div className="text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-128px)] overflow-y-auto scrollbar-hide">
      <ProfileForm />
    </div>
  )
}