"use client";

import { Separator } from "@/components/ui/separator";
import { LanguageSwitcher } from "@/components/dashboard/settings/LanguageSwitcher";
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

export default function SettingsLanguagePage() {
  const [mounted, setMounted] = useState(false);
  const t = useTranslations('settings.pages.language');

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">
          {mounted ? t('title') : 'Język aplikacji'}
        </h3>
        <p className="text-sm text-muted-foreground">
          {mounted ? t('description') : 'Zarządzaj językiem interfejsu aplikacji.'}
        </p>
      </div>
      <Separator />
      <LanguageSwitcher />
    </div>
  );
}