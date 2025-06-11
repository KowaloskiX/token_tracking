import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { useTranslations } from 'next-intl';

export default function NotFound() {
  const t = useTranslations('errors.not_found');
  
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background p-4">
      <Card className="max-w-md w-full border-none shadow-none text-center">
        <CardHeader>
          <div >
            <AlertCircle className="h-10 w-10 text-body-text mx-auto mb-4" />
            <CardTitle>{t('title')}</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            {t('description')}
          </p>
        </CardContent>
        <CardFooter>
          <Link href="/" className="w-full mt-10">
            <Button className="w-full">
              {t('back_home')}
            </Button>
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}