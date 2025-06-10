"use client";

import { Separator } from "@/components/ui/separator";
import { NotificationsForm } from "@/components/dashboard/settings/forms/NotificationsForm";
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

export default function SettingsNotificationsPage() {
  const [mounted, setMounted] = useState(false);
  const t = useTranslations('settings.pages.notifications');

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="h-[calc(100vh-128px)] overflow-y-auto scrollbar-hide space-y-6">
      <div>
        <h3 className="text-lg font-medium">
          {mounted ? t('title') : 'Powiadomienia'}
        </h3>
        <p className="text-sm text-muted-foreground">
          {mounted ? t('description') : 'Skonfiguruj swoje preferencje powiadomień.'}
        </p>
      </div>
      <Separator />
      <NotificationsForm />
    </div>
  )
}