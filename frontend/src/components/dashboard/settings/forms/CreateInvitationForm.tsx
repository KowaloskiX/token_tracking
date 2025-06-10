"use client";

import { useState, useEffect } from "react";
import { useTranslations } from 'next-intl';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { createInvitation } from "@/utils/userActions";
import { useToast } from "@/hooks/use-toast";

export function CreateInvitationForm() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { toast } = useToast();
  const t = useTranslations('settings.organization');

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await createInvitation(email, role);
      
      const inviteUrl = `${window.location.origin}/accept-invitation?token=${response.invitation.token}`;
      
      await navigator.clipboard.writeText(inviteUrl);
      
      toast({
        title: t('invite_success'),
        description: t('invite_success_description'),
      });
      
      setEmail("");
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: t('invite_error'),
        description: err.message || t('invite_error_description'),
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!mounted) {
    return (
      <div className="bg-card rounded-lg border p-6">
        <div className="text-sm text-muted-foreground">{t('loading')}</div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border p-6">
      <h3 className="text-lg font-medium mb-4">{t('invite_users')}</h3>
      <form onSubmit={handleInvite} className="flex flex-col sm:flex-row gap-3 items-end">
        <div className="flex-1">
          <label htmlFor="email" className="text-sm font-medium mb-1 block">
            {t('email')}
          </label>
          <Input
            id="email"
            type="email"
            placeholder={t('email_placeholder')}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="w-full sm:w-40">
          <label htmlFor="role" className="text-sm font-medium mb-1 block">
            {t('role')}
          </label>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger id="role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="admin">{t('roles.admin')}</SelectItem>
              <SelectItem value="member">{t('roles.member')}</SelectItem>
              <SelectItem value="guest">{t('roles.guest')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? t('inviting') : t('invite')}
        </Button>
      </form>
    </div>
  );
}