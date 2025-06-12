import { useTranslations as useNextIntlTranslations } from 'next-intl';

export function useTranslations(namespace?: string) {
  return useNextIntlTranslations(namespace);
}

export function useCommonTranslations() {
  return useNextIntlTranslations('common');
}

export function useNavigationTranslations() {
  return useNextIntlTranslations('navigation');
}

export function useSettingsTranslations() {
  return useNextIntlTranslations('settings');
}

export function useDashboardTranslations() {
  return useNextIntlTranslations('dashboard');
}

export function useAuthTranslations() {
  return useNextIntlTranslations('auth');
}

export function useSettingsProfileTranslations() {
  return useNextIntlTranslations('settings.profile');
}

export function useSettingsOrganizationTranslations() {
  return useNextIntlTranslations('settings.organization');
}

export function useSettingsNotificationsTranslations() {
  return useNextIntlTranslations('settings.notifications');
}

export function useTendersTranslations() {
  return useNextIntlTranslations('tenders');
}

export function useErrorsTranslations() {
  return useNextIntlTranslations('errors');
}

export function useApiTranslations() {
  return useNextIntlTranslations('api');
}