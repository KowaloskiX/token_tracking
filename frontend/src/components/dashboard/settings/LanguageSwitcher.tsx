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
  { code: 'en', name: 'English', nativeName: 'English' }
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
      setCurrentLocale(cookieValue || 'pl');
    }
  }, []);

  const handleLanguageChange = async (newLocale: string) => {
    if (newLocale === currentLocale) return;

    setIsLoading(true);
    try {
      // Set the locale cookie
      document.cookie = `locale=${newLocale}; path=/; max-age=${60 * 60 * 24 * 365}`;
      
      setCurrentLocale(newLocale);
      
      toast({
        title: "Język zmieniony",
        description: `Język zmieniony na ${languages.find(l => l.code === newLocale)?.nativeName}`,
      });

      // Reload the page to apply the new locale
      setTimeout(() => {
        window.location.reload();
      }, 500);
      
    } catch (error) {
      console.error('Error changing language:', error);
      toast({
        variant: "destructive",
        title: "Błąd",
        description: "Nie udało się zmienić języka. Spróbuj ponownie.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!mounted) {
    return (
      <div className="bg-card rounded-lg border p-6">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4" />
            <h3 className="font-medium text-sm">Język aplikacji</h3>
          </div>
          <div className="text-sm text-muted-foreground">Ładowanie...</div>
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
                <span className="font-medium">{language.nativeName}</span>
                <span className="text-muted-foreground ml-2">({language.name})</span>
              </Label>
            </div>
          ))}
        </RadioGroup>

        {isLoading && (
          <div className="text-sm text-muted-foreground">
            Zastosowywanie zmian języka...
          </div>
        )}
      </div>
    </div>
  );
}