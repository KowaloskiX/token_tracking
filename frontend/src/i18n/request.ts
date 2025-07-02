import {getRequestConfig} from 'next-intl/server';
import {cookies} from 'next/headers';

async function loadMessages(locale: string) {
  const messageFiles = [
    'common',
    'navigation', 
    'settings',
    'dashboard',
    'auth',
    'errors',
    'tenders',
    'api',
    'notifications'
  ];

  const messages: Record<string, any> = {};

  for (const file of messageFiles) {
    try {
      const fileMessages = (await import(`../../messages/${locale}/${file}.json`)).default;
      messages[file] = fileMessages;
    } catch (error) {
      console.warn(`Could not load translation file: ${locale}/${file}.json`);
      messages[file] = {};
    }
  }

  return messages;
}

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const locale = cookieStore.get('locale')?.value || 'pl';

  return {
    locale,
    messages: await loadMessages(locale),
    timeZone: 'Europe/Warsaw',
    now: new Date()
  };
});