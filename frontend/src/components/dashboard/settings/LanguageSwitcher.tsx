"use client";

import { useState, useEffect } from "react";
import { useTranslations } from 'next-intl';
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useToast } from "@/hooks/use-toast";
import { Globe } from "lucide-react";

interface Language {
  code: string;
  name: string;
  nativeName: string;
}

const languages: Language[] = [
  { code: 'pl', name: 'Polish', nativeName: 'Polski' },
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'de', name: 'German', nativeName: 'Deutsch' }
];

export function LanguageSwitcher() {
  const t = useTranslations('settings.language_selection');
  const [currentLocale, setCurrentLocale] = useState('pl');
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setMounted(true);
    // Get current locale from cookie on client side
    if (typeof window !== 'undefined') {
      const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('locale='))
        ?.split('=')[1];
      setCurrentLocale(cookieValue || 'de'); // Changed default to German
    }
  }, []);

  const handleLanguageChange = async (newLocale: string) => {
    if (newLocale === currentLocale) return;

    setIsLoading(true);
    try {
      // Set the locale cookie
      document.cookie = `locale=${newLocale}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
      
      setCurrentLocale(newLocale);
      
      const selectedLanguage = languages.find(l => l.code === newLocale);
      
      toast({
        title: t('success'),
        description: t('success') + `: ${selectedLanguage?.nativeName}`,
      });

      // Reload the page to apply the new locale
      setTimeout(() => {
        window.location.reload();
      }, 500);
      
    } catch (error) {
      console.error('Error changing language:', error);
      toast({
        variant: "destructive",
        title: t('error'),
        description: t('error'),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const getLanguageDisplayName = (language: Language) => {
    // Use translations for language names when available
    switch (language.code) {
      case 'pl':
        return t('polish');
      case 'en':
        return t('english');
      case 'de':
        return t('german');
      default:
        return language.nativeName;
    }
  };

  if (!mounted) {
    return (
      <div className="bg-card rounded-lg border p-6">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4" />
            <h3 className="font-medium text-sm">Anwendungssprache</h3>
          </div>
          <div className="text-sm text-muted-foreground">Lädt...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border p-6">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4" />
          <h3 className="font-medium text-sm">{t('title')}</h3>
        </div>
        
        <p className="text-sm text-muted-foreground">
          {t('description')}
        </p>

        <RadioGroup
          value={currentLocale}
          onValueChange={handleLanguageChange}
          disabled={isLoading}
          className="space-y-3"
        >
          {languages.map((language) => (
            <div key={language.code} className="flex items-center space-x-2">
              <RadioGroupItem 
                value={language.code} 
                id={language.code}
                disabled={isLoading}
              />
              <Label 
                htmlFor={language.code} 
                className={`cursor-pointer ${isLoading ? 'opacity-50' : ''}`}
              >
                <span className="font-medium">{getLanguageDisplayName(language)}</span>
                <span className="text-muted-foreground ml-2">({language.name})</span>
              </Label>
            </div>
          ))}
        </RadioGroup>

        {isLoading && (
          <div className="text-sm text-muted-foreground">
            {currentLocale === 'de' ? 'Sprachänderungen werden angewendet...' : 
             currentLocale === 'en' ? 'Applying language changes...' : 
             'Zastosowywanie zmian języka...'}
          </div>
        )}
      </div>
    </div>
  );
}