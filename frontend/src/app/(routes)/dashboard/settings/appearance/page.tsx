"use client";

import { AppearanceForm } from "@/components/dashboard/settings/forms/AppearanceForm"
import { Separator } from "@/components/ui/separator"
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

export default function SettingsAppearancePage() {
  const [mounted, setMounted] = useState(false);
  const t = useTranslations('settings.pages.appearance');

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">
          {mounted ? t('title') : 'Appearance'}
        </h3>
        <p className="text-sm text-muted-foreground">
          {mounted ? t('description') : 'Customize the appearance of the app. Automatically switch between day and night themes.'}
        </p>
      </div>
      <Separator />
      <AppearanceForm />
    </div>
  )
}