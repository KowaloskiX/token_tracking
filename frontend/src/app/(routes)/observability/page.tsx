"use client"
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function ObservabilityPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/observability/search');
  }, [router]);

  return null;
}