import { ScrapedResult } from "@/types/scraping";
import { handleResponse } from "./api";

const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

export interface ScrapeUrlRequest {
  urls: string[];
  timeout?: number;
  wait_for_dynamic?: boolean;
}



export interface ScrapeResponse {
  results: ScrapedResult[];
}

export const scrapeSite = async (request: ScrapeUrlRequest): Promise<ScrapeResponse> => {
  const response = await fetch(`${serverUrl}/scrape-site`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  return handleResponse<ScrapeResponse>(response);
};