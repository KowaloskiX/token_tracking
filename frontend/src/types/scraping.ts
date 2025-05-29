export interface ScrapedLink {
    url: string;
    text: string;
  }
  
  export interface ScrapedResult {
    url: string;
    title: string;
    favicon: string;
    links: ScrapedLink[];
    text: string;
  }