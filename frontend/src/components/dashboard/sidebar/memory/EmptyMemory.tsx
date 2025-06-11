import { Button } from "@/components/ui/button";
import { CloudUpload } from "lucide-react";
import UploadMemoryPopup from "../../popup/UploadMemoryPopup";
import { useState } from "react";
import { useTranslations } from 'next-intl';

interface EmptyMemoryProps {
  setOpenPopup: any;
}

export function EmptyMemory({ setOpenPopup }: EmptyMemoryProps) {
  const t = useTranslations('common');

  return (
    <div className="w-full flex py-20 sm:py-36 shrink-0 items-center justify-center rounded-md mt-6">
      <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
        <CloudUpload className="h-10 w-10 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">{t('upload_first_materials')}</h3>
        <p className="mb-4 mt-2 text-sm text-muted-foreground">
          {t('no_resources_yet')}
        </p>
        <Button onClick={setOpenPopup} className="px-7">
          <CloudUpload className="mr-2" />{t('upload')}
        </Button>
      </div>
    </div>
  );
}