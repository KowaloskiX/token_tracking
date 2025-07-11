import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import { useState, useRef, useEffect, useMemo } from "react";
import { pdfjs } from "react-pdf";
import * as mammoth from "mammoth";
import Mark from "mark.js";
import { X, Download, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { convertToPdf } from "@/utils/convertDocxToPdf";
import JSZip from 'jszip';
import dynamic from 'next/dynamic';
import { useTranslations } from 'next-intl';

declare global {
  interface Window {
    textFileNavigation?: {
      next: () => void;
      prev: () => void;
      getMatchCount: () => number;
      getCurrentIndex: () => number;
    };
  }
}

// Add custom scrollbar styles and highlight styles
const customStyles = `
  .custom-scrollbar::-webkit-scrollbar {
    width: 4px;
  }
  .custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 10px;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background-color: rgba(0, 0, 0, 0.3);
  }
  /* Base highlight style (can be used for search or dimmed citations) */
  .pdf-highlight {
    background-color: rgb(214, 210, 136) !important;
    border-radius: 2px;
  }
  /* Active citation highlight style */
  .pdf-highlight.active-citation {
    background-color: yellow !important;
    box-shadow: 0 0 3px 1px rgba(255, 215, 0, 0.7) !important;
    border-radius: 3px !important;
  }
  /* Active search highlight style */
  .pdf-highlight.active-search {
    background-color: rgb(214, 210, 136) !important;
  }
    .pdf-footer { display:none !important; }
`;

export function buildGapRegex(phrase: string): RegExp {
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  /* ── 1.  deal with leading enumerators ──────────────────────────────
     Accept things like:
       "8)", "8.", "8-", "§ 8.", "(8)", "8 )"
     If the citation is *only* the enumerator, we allow the
     trailing punctuation but require a word-boundary after it so we
     don’t light up every naked “8” in the file.                         */
  const enumMatch = phrase.match(/^\s*[(§]?\s*(\d+)\s*[).-–—]?\s*(.*)$/u);
  if (enumMatch) {
    const [, num, rest] = enumMatch;

    // Only the number+punctuation?  e.g. "8)" or "8."
    if (!rest.trim()) {
      return new RegExp(`\\b${esc(num)}[).-–—]?\\b`, "giu");
    }

    // Normalise to “num + single-space + rest” so later tokenisation works
    phrase = `${num} ${rest}`;
  }

  /* ── 2. the original gap-regex (unchanged) ────────────────────────── */
  const tokens = phrase.match(/[\p{L}\p{N}]+/gu) || [];
  const GAP = "[\\s\\p{P}\\p{S}\\d]*";
  return new RegExp(tokens.map(esc).join(GAP), "giu");
}

export function buildVeryLooseRegex(phrase: string, maxChunk = 600): RegExp {
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const tokens = phrase.match(/[\p{L}\p{N}]+/gu) || [];
  const ANY   = `[\\s\\S]{0,${maxChunk}}?`;        // up to N chars of *anything*
  return new RegExp(tokens.map(esc).join(ANY), "giu");
}

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

// Dynamically import React-PDF components using a shared promise
const PDFComponentsPromise = import('react-pdf').then(mod => {
  mod.pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  return {
    Document: mod.Document,
    Page: mod.Page
  };
});

const Document = dynamic(
  () => PDFComponentsPromise.then(comps => comps.Document),
  {
    ssr: false,
    loading: () => <Skeleton className="w-full h-[80vh]" />
  }
);

const Page = dynamic(
  () => PDFComponentsPromise.then(comps => comps.Page),
  { ssr: false }
);

interface FilePreviewProps {
  file: {
    _id: string;
    name: string;
    type: string;
    url: string;
    blob_url?: string;
    citations?: string[]; // Array of citation strings (content) or undefined
  };
  onClose: () => void;
  loading?: boolean; // Optional loading state from parent
}

// Helper function to escape regex special characters
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Helper to split citation into fragments (sentences or microfragments)
function splitCitationToFragments(citation: string): string[] {
  // Normalize whitespace before splitting
  const normalizedCitation = citation.replace(/\s+/g, " ").trim();
  // Try splitting on sentences first (look behind for punctuation + space)
  let frags = normalizedCitation.split(/(?<=[.?!])\s+/).map(f => f.trim()).filter(Boolean);

  // If only one fragment and it's long, break into smaller chunks
  const MIN_WORDS_FOR_MICROFRAGMENT = 8; // Min words to consider a microfragment useful
  const MAX_WORDS_PER_MICROFRAGMENT = 12; // Target size

  if (frags.length === 1) {
    const words = frags[0].split(/\s+/);
    if (words.length > MAX_WORDS_PER_MICROFRAGMENT + 4) { // Add buffer before splitting
      const microFrags: string[] = [];
      for (let i = 0; i < words.length; i += MAX_WORDS_PER_MICROFRAGMENT) {
        const chunk = words.slice(i, i + MAX_WORDS_PER_MICROFRAGMENT).join(" ");
        if (chunk.split(/\s+/).length >= MIN_WORDS_FOR_MICROFRAGMENT) { // Only add if reasonably sized
          microFrags.push(chunk);
        } else if (microFrags.length > 0) {
          // Append small remainder to the previous fragment
          microFrags[microFrags.length - 1] += " " + chunk;
        } else {
          // First chunk is too small, just use it
          microFrags.push(chunk);
        }
      }
      // Filter out any potentially empty strings again after processing
      frags = microFrags.filter(Boolean);
    }
  } else {
    // If we split by sentence, ensure each resulting fragment isn't excessively long either
    frags = frags.flatMap(frag => {
      const words = frag.split(/\s+/);
      if (words.length > MAX_WORDS_PER_MICROFRAGMENT + 4) {
        const microFrags: string[] = [];
        for (let i = 0; i < words.length; i += MAX_WORDS_PER_MICROFRAGMENT) {
          const chunk = words.slice(i, i + MAX_WORDS_PER_MICROFRAGMENT).join(" ");
          if (chunk.split(/\s+/).length >= MIN_WORDS_FOR_MICROFRAGMENT) {
            microFrags.push(chunk);
          } else if (microFrags.length > 0) {
            microFrags[microFrags.length - 1] += " " + chunk;
          } else {
            microFrags.push(chunk);
          }
        }
        return microFrags.filter(Boolean);
      }
      return frag; // Keep original sentence fragment if not too long
    });
  }

  // Final filter for safety
  return frags.filter(f => f.length > 3); // Ensure fragments have some substance
}

// Helper to create a loose regex that tolerates punctuation / hyphens between words
const buildLooseRegex = (text: string) => buildGapRegex(text);

const normalizeCitationText = (text: string): string => {
  return text
    // Normalize different types of quotes
    .replace(/["""'']/g, '"')
    // Normalize different types of dashes and hyphens
    .replace(/[‐‑‒–—―]/g, "-")
    // Normalize whitespace
    .replace(/\s+/g, ' ')
    // Remove common PDF artifacts
    .replace(/\u00A0/g, ' ') // non-breaking space
    .replace(/\uFEFF/g, '') // byte order mark
    .trim()
    .toLowerCase();
};

async function highlightSearchQuery(
  searchQuery: string,
  containerElement: HTMLElement,
  excludeSelectors: string[]
): Promise<HTMLElement[]> {

  if (!searchQuery?.trim()) return [];

  console.log(`[Search] Processing: "${searchQuery}"`);

  // Create a FRESH Mark.js instance for search to avoid state issues
  const freshMarkInstance = new Mark(containerElement);
  const regex = buildGapRegex(searchQuery.trim());
  console.log(`[Search] Using regex:`, regex);

  const collectedElements: HTMLElement[] = [];

  return new Promise((resolve) => {
    // Add a small delay to let any previous Mark.js operations complete
    setTimeout(() => {
      freshMarkInstance.markRegExp(regex, {
        className: "pdf-highlight",
        exclude: excludeSelectors,
        acrossElements: true,
        each: (el: Element) => {
          collectedElements.push(el as HTMLElement);
        },
        done: () => {
          console.log(`[Search] Found ${collectedElements.length} elements`);
          resolve(collectedElements);
        },
        noMatch: () => {
          console.log(`[Search] No match found`);
          resolve(collectedElements);
        },
      });
    }, 25); // Small delay between operations
  });
}

async function highlightCitationFragments(
  citation: string,
  containerElement: HTMLElement,
  excludeSelectors: string[]
): Promise<HTMLElement[]> {

  if (!citation?.trim()) return [];

  // 0️⃣ prepare a *fresh* Mark.js instance
  const mark = new Mark(containerElement);
  const collected: HTMLElement[] = [];

  /** inner helper to run markRegExp and collect hits */
  const runMark = (regex: RegExp) => new Promise<HTMLElement[]>((resolve) => {
    mark.markRegExp(regex, {
      className: "pdf-highlight",
      exclude: excludeSelectors,
      acrossElements: true,
      each: el => collected.push(el as HTMLElement),
      done: () => resolve([...collected]),
      noMatch: () => resolve([]),
    });
  });

  /* 1️⃣ first shot – your existing *strict* gap regex */
  const strictHits = await runMark(buildGapRegex(citation.trim()));
  if (strictHits.length) return strictHits;   //  ✅ success

  /* 2️⃣ fallback – try the ultra-loose version */
  const looseHits  = await runMark(buildVeryLooseRegex(citation.trim()));
  return looseHits;                           //  ⬅️ may be [] if still no luck
}

export function FilePreview({ file, onClose, loading: propLoading = false }: FilePreviewProps) {
  const [forceUpdateCounter, setForceUpdateCounter] = useState(0);
  const [fileUrl, setFileUrl] = useState<string>("");
  const [rawText, setRawText] = useState<string>("");
  const [numPages, setNumPages] = useState<number>(0);
  const [pagesRendered, setPagesRendered] = useState<number>(0);
  const [internalIsLoading, setInternalIsLoading] = useState<boolean>(true);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileContentRef = useRef<Blob | null>(null);
  const t = useTranslations('dashboard.file_preview');
  const tCommon = useTranslations('common');
  // const pdfDocumentRef = useRef<any>(null); // Keep if needed for direct PDF manipulation

  const [textMode, setTextMode] = useState<"search" | "citation">("citation");
  const [textActiveIndex, setTextActiveIndex] = useState<number>(-1);
  const [textMatchCount, setTextMatchCount] = useState<number>(0);

  const isLoading = propLoading || internalIsLoading;

  // Search & Citation State
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showSearchBar, setShowSearchBar] = useState<boolean>(true); // Keep visible

  const textFileNavStateRef = useRef<{ count: number, index: number }>({ count: 0, index: -1 });

  // State for User Search Results
  const [userSearchMatches, setUserSearchMatches] = useState<HTMLElement[]>([]);
  const [currentUserSearchMatchIndex, setCurrentUserSearchMatchIndex] = useState<number>(-1);

  // State for Citation Highlighting & Navigation (PDF/DOCX)
  const [citationToElementsMap, setCitationToElementsMap] = useState<Map<string, { fragments: string[], elements: HTMLElement[] }>>(new Map());
  const [citationList, setCitationList] = useState<string[]>([]); // Ordered list of unique citations
  const [currentCitationIndex, setCurrentCitationIndex] = useState<number>(-1); // Index in citationList
  const [isProcessingHighlights, setIsProcessingHighlights] = useState<boolean>(false); // Combined loading for search/citations

  // NEW STATES FOR CITATION PROCESSING
  const [citationProcessingCompleted, setCitationProcessingCompleted] = useState<boolean>(false);
  const [notFoundCitations, setNotFoundCitations] = useState<string[]>([]); // Track citations that weren't found

  // Add loading state phases for better user feedback
  const [loadingPhase, setLoadingPhase] = useState<'initial' | 'rendering' | 'highlighting' | 'complete'>('initial');
  const [highlightProgress, setHighlightProgress] = useState<number>(0);
  const [totalCitationsToProcess, setTotalCitationsToProcess] = useState<number>(0);

  // Container & layout
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(800);
const EXCLUDE_SELECTORS = [".citation-overlay", ".pdf-footer"];

  function detectNumericFooters(root: HTMLElement) {
  const spans = root.querySelectorAll<HTMLSpanElement>('[class*="textLayer"] span');
  spans.forEach(span => {
    const t = span.textContent?.trim() || "";
    if (
      /^[IVXLCDM]{1,4}$/i.test(t)                // roman numeral
      || /^\d{1,4}$/.test(t)                     // bare number
      || /^strona\s+\d+/i.test(t)                // “Strona 3”
    ) {
      span.classList.add('pdf-footer');          // mark & (optionally) hide
    }
  });
}

  // Apply custom styles
  useEffect(() => {
    const styleEl = document.createElement('style');
    styleEl.innerHTML = customStyles;
    document.head.appendChild(styleEl);
    return () => {
      document.head.removeChild(styleEl);
    };
  }, []);

  useEffect(() => {
    if (file.type === "txt") {
      if (searchQuery.trim()) {
        setTextMode("search");
        setTextActiveIndex(0);
      } else if (file.citations && file.citations.length > 0) {
        setTextMode("citation");
        setTextActiveIndex(0);
      } else {
        setTextActiveIndex(-1);
      }
    }
  }, [searchQuery, file.citations, file.type]);


  // Close popup on escape key
  useEffect(() => {
    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEscapeKey);
    return () => window.removeEventListener("keydown", handleEscapeKey);
  }, [onClose]);

  // --- File Loading & Processing --- (Mostly unchanged, keeping relevant parts)

  const isPdfValid = async (blob: Blob): Promise<boolean> => { /* ... as before ... */
    try {
      const arrayBuffer = await blob.arrayBuffer();
      const loadingTask = pdfjs.getDocument({ data: arrayBuffer });
      await loadingTask.promise; // Check if it loads
      return true;
    } catch (error) {
      console.error("PDF validation failed:", error);
      return false;
    }
  };
  const isDocxValid = async (blob: Blob): Promise<boolean> => { /* ... as before ... */
    try {
      const arrayBuffer = await blob.arrayBuffer();
      await mammoth.extractRawText({ arrayBuffer });
      return true;
    } catch (error) {
      console.error("DOCX validation failed:", error);
      return false;
    }
  };

  const handleTextIndexChange = (newIndex: number) => {
    setTextActiveIndex(newIndex);
  };

  const handleTextCountChange = (newCount: number) => {
    setTextMatchCount(newCount);
  };

  useEffect(() => {
    if (!file?._id) return;

    // Reset state for new file
    setFileUrl("");
    setRawText("");
    setNumPages(0);
    setPagesRendered(0);
    setFileError(null);
    fileContentRef.current = null;
    setSearchQuery(""); // Clear search on file change
    clearAllHighlightsAndState(); // Clear highlights and related state

    // RESET NEW CITATION PROCESSING STATES
    setCitationProcessingCompleted(false);
    setNotFoundCitations([]);

    console.log(`[File Load] Processing new file: ${file.name} (${file.type}), Citations: ${file.citations?.length || 0}`);

    (async () => {
      try {
        setInternalIsLoading(true);
        setLoadingPhase('initial');
        const sourceUrl = file.blob_url || file.url;
        if (!sourceUrl) throw new Error("No file URL or blob_url provided");

        // Simplified fetch logic (assuming fetchWithTimeout exists or is standard fetch)
        const response = await fetch(sourceUrl);
        if (!response.ok) throw new Error(`Failed to fetch file: ${response.status} ${response.statusText}`);
        const blob = await response.blob();
        fileContentRef.current = blob;

        // Process based on type
        if (file.type === "pdf") {
          const isPdfOk = await isPdfValid(blob);
          if (!isPdfOk) throw new Error("Invalid or corrupted PDF file");
          setFileUrl(URL.createObjectURL(blob));
          const pdfText = await extractPdfText(blob); // Extract text immediately
          setRawText(pdfText);
        } else if (file.type === "docx" || file.type === "doc" || file.type === "odt") {
          let docText = "";
          if (file.type === "docx") {
            const isDocxOk = await isDocxValid(blob);
            if (!isDocxOk) throw new Error("Invalid or corrupted DOCX file");
            docText = await extractDocxRawText(blob);
          } else if (file.type === "odt") {
            docText = await extractOdtRawText(blob);
          } else { // .doc
            docText = "Text extraction not supported for .doc files, attempting conversion.";
          }
          setRawText(docText); // Set raw text even if conversion fails

          try {
            const pdfBlob = await convertToPdf(blob, file.type);
            if (pdfBlob) {
              const isConvertedPdfValid = await isPdfValid(pdfBlob);
              if (isConvertedPdfValid) {
                setFileUrl(URL.createObjectURL(pdfBlob));
                // Re-extract text from the *converted* PDF for better accuracy if needed
                // const convertedPdfText = await extractPdfText(pdfBlob);
                // setRawText(convertedPdfText); // Optional: overwrite initial extraction
              } else {
                throw new Error("PDF conversion produced an invalid file");
              }
            } else {
              throw new Error("PDF conversion failed");
            }
          } catch (conversionError) {
            console.error("PDF conversion error:", conversionError);
            setFileError("Could not convert document for preview. Text content (if available) is shown.");
            // Keep fileUrl empty, rely on rawText + TextFileRenderer fallback
          }
        } else if (file.type === "txt") {
          const text = await blob.text();
          setRawText(text);
          // No fileUrl needed for text, will use TextFileRenderer
        } else {
          console.warn(`Preview not fully supported for type: ${file.type}`);
          try {
            const text = await blob.text();
            if (text.length > 0 && !text.slice(0, 100).includes('\0')) {
              setRawText(text);
              setFileError(`Visual preview not available for ${file.type}. Showing text content.`);
            } else {
              setFileError(`Preview not available for file type: ${file.type}`);
            }
          } catch {
            setFileError(`Preview not available for file type: ${file.type}`);
          }
        }

      } catch (err) {
        console.error("File processing error:", err);
        setFileUrl("");
        setRawText("");
        setFileError(t('error_processing_file') + `: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setInternalIsLoading(false);
        setLoadingPhase('complete');
      }
    })();
  }, [file]); // Depend only on file object

  // Recalculate container width
  useEffect(() => {
    function updateWidth() {
      if (containerRef.current) {
        const newWidth = Math.min(window.innerWidth - 64, 1000); // Adjust max width as needed
        setContainerWidth(Math.max(newWidth, 300)); // Min width
      }
    }
    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  // PDF events
  const onDocumentLoadStart = () => {
    setInternalIsLoading(true);
    setLoadingPhase('initial');
  };
  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPagesRendered(0); // Reset pages rendered count on new doc load
    setLoadingPhase('rendering');
    // Note: Loading state is tricky here. PDF might be loaded, but pages aren't rendered.
    // Highlighting depends on rendered pages.
  };
  const onDocumentLoadError = (error: Error) => {
    console.error("PDF loading error:", error);
    setInternalIsLoading(false);
    setLoadingPhase('complete');
    setFileError(`Error loading PDF: ${error.message}`);
  };
  const onPageRenderSuccess = () => {
    setPagesRendered((prev) => {
      const newCount = prev + 1;
      // Once all pages are rendered, we can consider the document "ready" for highlighting
      if (newCount === numPages) {
        console.log("All PDF pages rendered.");
        // Potentially trigger highlighting logic here if it depends strictly on all pages being ready
        // Or let the useEffect handle it based on pagesRendered >= numPages condition
        setInternalIsLoading(false); // Mark loading as false *after* rendering
      }
      return newCount;
    });
  };

  useEffect(() => {
  if (pagesRendered === numPages && containerRef.current) {
    detectNumericFooters(containerRef.current);
  }
}, [pagesRendered, numPages]);

  // Suppress specific console errors (if needed)
  useEffect(() => { /* ... as before ... */
    const originalConsoleError = console.error;
    console.error = (...args) => {
      if (args[0] && typeof args[0] === 'string' &&
        (args[0].includes('TextLayer') || args[0].includes('AbortException') || args[0].includes('InvalidPDFException'))) {
        return;
      }
      originalConsoleError(...args);
    };
    return () => { console.error = originalConsoleError; };
  }, []);


  // --- Text Extraction Functions --- (Unchanged)
  async function extractPdfText(pdfBlob: Blob): Promise<string> { /* ... as before ... */
    try {
      const arrayBuffer = await pdfBlob.arrayBuffer();
      const loadingTask = pdfjs.getDocument({ data: arrayBuffer });
      const MAX_PAGES_FOR_FULL_EXTRACTION = 100;
      const pdfDoc = await loadingTask.promise;
      const totalPages = pdfDoc.numPages;
      const pagesToExtract = Math.min(totalPages, MAX_PAGES_FOR_FULL_EXTRACTION);
      if (totalPages > MAX_PAGES_FOR_FULL_EXTRACTION) {
        console.log(`PDF has ${totalPages} pages, extracting text from first ${pagesToExtract} pages only.`);
      }
      const extractionPromises = [];
      for (let pageNum = 1; pageNum <= pagesToExtract; pageNum++) {
        extractionPromises.push(extractTextFromPage(pdfDoc, pageNum));
      }
      const pageTexts = await Promise.all(extractionPromises);
      return pageTexts.join(" ").trim();
    } catch (error) {
      console.error("Error extracting PDF text:", error);
      return "Error extracting text from PDF";
    }
  }
  async function extractTextFromPage(pdfDoc: any, pageNum: number): Promise<string> { /* ... as before ... */
    try {
      const page = await pdfDoc.getPage(pageNum);
      const content = await page.getTextContent();
      let lastY = null;
      let text = "";
      const TOLERANCE = 1; // Adjust as needed

      // Sort items primarily by Y, then X for reading order
      const sortedItems = content.items.slice().sort((a: any, b: any) => {
        if (Math.abs(a.transform[5] - b.transform[5]) > TOLERANCE) {
          return b.transform[5] - a.transform[5]; // Higher Y first (top of page)
        }
        return a.transform[4] - b.transform[4]; // Then lower X first (left to right)
      });

      for (const item of sortedItems) {
        if (!('str' in item)) continue;
        const str = item.str;
        const y = item.transform[5];

        if (lastY !== null && Math.abs(y - lastY) > TOLERANCE) {
          text += " "; // Use space for line breaks within PDF rendering
        } else if (str.trim() !== "" && text.length > 0 && !text.endsWith(" ") && !text.endsWith("\n")) {
          // Add space between words on the same visual line if needed
          // Check the last character of the previous item and first of current
          // This basic check might not perfectly handle hyphenation across spans
          text += " ";
        }
        text += str;
        lastY = y;
      }
      return text.replace(/\s+/g, ' ').trim(); // Normalize whitespace at the end
    } catch (error) {
      console.error(`Error extracting text from page ${pageNum}:`, error);
      return "";
    }
  }
  async function extractDocxRawText(docxBlob: Blob): Promise<string> { /* ... as before ... */
    try {
      const arrayBuffer = await docxBlob.arrayBuffer();
      const { value } = await mammoth.extractRawText({ arrayBuffer });
      return value || "No text content found in document";
    } catch (error) {
      console.error("Error extracting DOCX text:", error);
      return "Error extracting text from DOCX file";
    }
  }
  async function extractOdtRawText(odtBlob: Blob): Promise<string> { /* ... as before ... */
    try {
      const jszip = new JSZip();
      let zip;
      try {
        zip = await jszip.loadAsync(odtBlob);
      } catch (zipError) {
        console.error("Error loading ODT as zip:", zipError);
        throw new Error("Could not read ODT file format");
      }
      const contentXmlFile = zip.file("content.xml");
      if (!contentXmlFile) throw new Error("Could not find content.xml in ODT file");
      const contentXml = await contentXmlFile.async("string");
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(contentXml, "text/xml");

      // Simple text extraction: Get all text content within the body
      const body = xmlDoc.querySelector("body");
      let textContent = body ? body.textContent : "";

      // Basic cleanup: replace multiple whitespace/newlines with single space
      textContent = textContent?.replace(/\s+/g, ' ').trim() ?? "";

      return textContent || "No text content found";
    } catch (error) {
      console.error("Error extracting ODT text:", error);
      return "Error extracting text from ODT file";
    }
  }

  // Function to clear all highlights and reset related state
  function clearAllHighlightsAndState() {
    // Never touch text file highlighting - it's completely isolated
    if (file.type === "txt") {
      return;
    }

    if (containerRef.current) {
      const markInstance = new Mark(containerRef.current);
      markInstance.unmark();
      // Also clear active highlight classes
      const activeElements = containerRef.current.querySelectorAll('.pdf-highlight.active-citation, .pdf-highlight.active-search');
      activeElements.forEach((el) => {
        el.classList.remove('active-citation', 'active-search');
      });
    }

    // Clear state only for non-text files
    setUserSearchMatches([]);
    setCurrentUserSearchMatchIndex(-1);
    setCitationToElementsMap(new Map());
    setCitationList([]);
    setCurrentCitationIndex(-1);

    // CLEAR NEW CITATION PROCESSING STATES
    setCitationProcessingCompleted(false);
    setNotFoundCitations([]);
  }

  function groupNearbyElements(elements: HTMLElement[]): HTMLElement[] {
    if (elements.length === 0) return [];

    // Sort elements by their position (top to bottom, left to right)
    const sortedElements = elements.slice().sort((a, b) => {
      const rectA = a.getBoundingClientRect();
      const rectB = b.getBoundingClientRect();

      const yDiff = rectA.top - rectB.top;
      if (Math.abs(yDiff) > 2) { // Smaller threshold for same-line detection
        return yDiff;
      }
      return rectA.left - rectB.left; // Same line, sort left to right
    });

    const groups: HTMLElement[][] = [];
    let currentGroup: HTMLElement[] = [sortedElements[0]];

    for (let i = 1; i < sortedElements.length; i++) {
      const current = sortedElements[i];
      const previous = sortedElements[i - 1];

      const currentRect = current.getBoundingClientRect();
      const previousRect = previous.getBoundingClientRect();

      // Calculate distances
      const verticalDistance = Math.abs(currentRect.top - previousRect.top);
      const horizontalDistance = Math.abs(currentRect.left - previousRect.right);

      // Different conditions for same line vs. multi-line matches
      let shouldGroup = false;

      if (verticalDistance <= 5) {
        // Same line: elements should be close horizontally
        shouldGroup = horizontalDistance <= 50;
      } else if (verticalDistance <= 40) {
        // Potentially next line: check if it's a line wrap scenario
        const isNextLine = currentRect.top > previousRect.top; // Current is below previous
        const isReasonableLineHeight = verticalDistance >= 10 && verticalDistance <= 40; // Reasonable line height

        // For line wrapping, the new line element should be to the left of or close to the previous element
        // OR if the previous element was near the end of its line, the new element can start from the left
        const couldBeLineWrap = isNextLine && isReasonableLineHeight &&
          (currentRect.left <= previousRect.left + 100); // Allow some flexibility for line wrapping

        shouldGroup = couldBeLineWrap;
      }

      if (shouldGroup) {
        // Same logical match, add to current group
        currentGroup.push(current);
      } else {
        // Different match, start a new group
        groups.push(currentGroup);
        currentGroup = [current];
      }
    }

    // Add the last group
    groups.push(currentGroup);

    // Return the first element from each group (representing the match)
    return groups.map(group => group[0]);
  }

  function applyHighlights() {
    if (!containerRef.current || isLoading) return;

    console.log(`[Highlighting] Starting - Search: "${searchQuery}", Citations: ${file.citations?.length || 0}`);

    setIsProcessingHighlights(true);
    setLoadingPhase("highlighting");
    const markInstance = new Mark(containerRef.current);

    // Always start with a clean slate
    markInstance.unmark({
      done: () => requestAnimationFrame(async () => {
        if (!containerRef.current) {
          setIsProcessingHighlights(false);
          setLoadingPhase("complete");
          return;
        }

        /* ────────────────────────────────────────────────
           USER SEARCH BRANCH (IMPROVED - same as citations)
           ──────────────────────────────────────────────── */
        if (searchQuery.trim()) {
          console.log(`[User Search] Processing: "${searchQuery}"`);

          // WAIT FOR DOM TO BE FULLY READY (same as citations)
          const isDomReady = await waitForTextLayerReady(3000);
          if (!isDomReady) {
            console.warn(`[User Search] DOM not ready, but proceeding anyway`);
          }

          try {
            // Use the improved search function with fresh Mark instance
            const allElements = await highlightSearchQuery(searchQuery, containerRef.current, EXCLUDE_SELECTORS);

            if (allElements.length > 0) {
              // Group elements that are close together (same logical match)
              const groupedMatches = groupNearbyElements(allElements);

              console.log(`[User Search] Found ${groupedMatches.length} unique matches (from ${allElements.length} elements)`);
              setUserSearchMatches(groupedMatches);
              const first = groupedMatches.length ? 0 : -1;
              setCurrentUserSearchMatchIndex(first);

              // Clear citation mode
              setCitationToElementsMap(new Map());
              setCitationList([]);
              setCurrentCitationIndex(-1);

              if (first !== -1) {
                applyActiveSearchHighlight(first, groupedMatches);
              } else {
                setIsProcessingHighlights(false);
                setLoadingPhase("complete");
              }
            } else {
              console.log(`[User Search] No matches found`);
              setUserSearchMatches([]);
              setCurrentUserSearchMatchIndex(-1);
              setIsProcessingHighlights(false);
              setLoadingPhase("complete");
            }
          } catch (error) {
            console.error(`[User Search] Error processing search:`, error);
            setUserSearchMatches([]);
            setCurrentUserSearchMatchIndex(-1);
            setIsProcessingHighlights(false);
            setLoadingPhase("complete");
          }
          return;
        }

        /* ────────────────────────────────────────────────
           CITATION HIGHLIGHTING BRANCH (IMPROVED)
           ──────────────────────────────────────────────── */
        if (file.citations && file.citations.length > 0 && citationList.length === 0 && !citationProcessingCompleted) {
          console.log(`[Citations] Processing ${file.citations.length} citations with improved DOM readiness`);

          // WAIT FOR DOM TO BE FULLY READY
          const isDomReady = await waitForTextLayerReady(3000);
          if (!isDomReady) {
            console.warn(`[Citations] DOM not ready, but proceeding anyway`);
          }

          const newMap: Map<string, { fragments: string[]; elements: HTMLElement[] }> = new Map();
          const unique = Array.from(new Set(file.citations.filter(Boolean)));
          setTotalCitationsToProcess(unique.length);
          setHighlightProgress(0);

          const processCitationSequentially = async (index: number) => {
            if (index >= unique.length) {
              // All done - process results
              console.log(`[Citations] Final: ${newMap.size}/${unique.length} citations highlighted`);

              setCitationToElementsMap(newMap);
              const list = Array.from(newMap.keys());
              setCitationList(list);

              // Track which citations weren't found
              const foundCitations = new Set(list);
              const notFound = unique.filter(citation => !foundCitations.has(citation));
              setNotFoundCitations(notFound);

              // MARK PROCESSING AS COMPLETED
              setCitationProcessingCompleted(true);

              const start = list.length ? 0 : -1;
              setCurrentCitationIndex(start);

              setUserSearchMatches([]);
              setCurrentUserSearchMatchIndex(-1);

              if (start !== -1) {
                applyActiveCitationHighlight(start, list, newMap);
              } else {
                setIsProcessingHighlights(false);
                setLoadingPhase("complete");
              }
              return;
            }

            const cit = unique[index];
            console.log(`[Citations] Processing ${index + 1}/${unique.length}: "${cit.substring(0, 50)}..."`);

            // LONGER delay and DOM check before each citation
            await new Promise(resolve => setTimeout(resolve, 100)); // Increased from 10ms to 100ms

            // Double-check container is still available
            if (!containerRef.current) {
              console.error(`[Citations] Container lost during processing`);
              setIsProcessingHighlights(false);
              setLoadingPhase("complete");
              return;
            }

            try {
              // Use the improved function with fresh Mark instance
              const els = await highlightCitationFragments(cit, containerRef.current, EXCLUDE_SELECTORS);

              if (els.length > 0) {
                newMap.set(cit, {
                  fragments: splitCitationToFragments(cit),
                  elements: els,
                });
                console.log(`[Citations] ✅ Success: ${els.length} elements`);
              } else {
                console.log(`[Citations] ❌ No matches found - trying debug`);

                // ENHANCED DEBUGGING
                if (containerRef.current) {
                  const pdfText = containerRef.current.textContent || '';
                  const firstTenWords = cit.split(' ').slice(0, 10).join(' ');
                  const firstFiveWords = cit.split(' ').slice(0, 5).join(' ');
                  const firstThreeWords = cit.split(' ').slice(0, 3).join(' ');

                  console.log(`[Debug] Citation: "${cit}"`);
                  console.log(`[Debug] First 10 words: "${firstTenWords}"`);
                  console.log(`[Debug] First 5 words: "${firstFiveWords}"`);
                  console.log(`[Debug] First 3 words: "${firstThreeWords}"`);
                  console.log(`[Debug] PDF contains first 10 words:`, pdfText.includes(firstTenWords));
                  console.log(`[Debug] PDF contains first 5 words:`, pdfText.includes(firstFiveWords));
                  console.log(`[Debug] PDF contains first 3 words:`, pdfText.includes(firstThreeWords));

                  // Try searching with shorter fragments
                  if (!pdfText.includes(firstTenWords) && pdfText.includes(firstFiveWords)) {
                    console.log(`[Debug] 🔄 Retrying with first 5 words only`);
                    const retryEls = await highlightCitationFragments(firstFiveWords, containerRef.current, EXCLUDE_SELECTORS);
                    if (retryEls.length > 0) {
                      newMap.set(cit, {
                        fragments: splitCitationToFragments(firstFiveWords),
                        elements: retryEls,
                      });
                      console.log(`[Debug] ✅ Retry success with shorter text: ${retryEls.length} elements`);
                    }
                  }
                }
              }
            } catch (error) {
              console.error(`[Citations] Error processing citation ${index + 1}:`, error);
            }

            setHighlightProgress(index + 1);

            // Process next citation
            processCitationSequentially(index + 1);
          };

          // Start processing from first citation
          processCitationSequentially(0);
          return; // Important: return here to avoid the fallback below
        }

        /* ────────────────────────────────────────────────
           🚨 FIX: FALLBACK FOR NO SEARCH AND NO CITATIONS
           ──────────────────────────────────────────────── */
        // If we reach here, there's nothing to highlight
        console.log(`[Highlighting] No search query or citations to process - finishing immediately`);

        // Clear any existing state
        setUserSearchMatches([]);
        setCurrentUserSearchMatchIndex(-1);
        setCitationToElementsMap(new Map());
        setCitationList([]);
        setCurrentCitationIndex(-1);

        // Mark as complete
        setIsProcessingHighlights(false);
        setLoadingPhase("complete");

      }) // <- This closes the requestAnimationFrame callback
    }); // <- This closes the markInstance.unmark call
  }

  const waitForTextLayerReady = async (maxWaitMs: number = 2000): Promise<boolean> => {
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitMs) {
      if (!containerRef.current) return false;

      // Check if text layer has meaningful content
      const textContent = containerRef.current.textContent || '';
      const textNodes = containerRef.current.querySelectorAll('[class*="textLayer"] span');

      // Make sure we have both text content and rendered text spans
      if (textContent.trim().length > 100 && textNodes.length > 10) {
        console.log(`[DOM Ready] Text layer ready: ${textContent.length} chars, ${textNodes.length} spans`);
        return true;
      }

      // Wait a bit before checking again
      await new Promise(resolve => setTimeout(resolve, 50));
    }

    console.warn(`[DOM Ready] Timeout waiting for text layer (${maxWaitMs}ms)`);
    return false;
  };

  // Function to highlight *only* the currently selected search result
  function applyActiveSearchHighlight(
    searchIndex: number,
    currentSearchMatches: HTMLElement[]
  ) {
    if (!containerRef.current || searchIndex < 0 || searchIndex >= currentSearchMatches.length) {
      setIsProcessingHighlights(false);
      setLoadingPhase('complete');
      return;
    }

    console.log(`Applying active search highlight for result ${searchIndex + 1}/${currentSearchMatches.length}`);

    // 1️⃣ Remove previous active-search classes
    const prevActives = containerRef.current.querySelectorAll('.pdf-highlight.active-search');
    prevActives.forEach((el) => el.classList.remove('active-search'));

    // 2️⃣ Add active class to current search match
    const currentMatch = currentSearchMatches[searchIndex];
    currentMatch.classList.add('active-search');

    // 3️⃣ Scroll to the element
    scrollToElement(currentMatch);

    setIsProcessingHighlights(false);
    setLoadingPhase('complete');
  }

  // Function to highlight *only* the fragments of the currently selected citation
  function applyActiveCitationHighlight(
    citationIndex: number,
    currentCitations: string[],
    currentMap: Map<string, { fragments: string[], elements: HTMLElement[] }>
  ) {
    if (!containerRef.current || citationIndex < 0 || citationIndex >= currentCitations.length) {
      setIsProcessingHighlights(false);
      setLoadingPhase('complete');
      return;
    }

    const citation = currentCitations[citationIndex];
    const citationData = currentMap.get(citation);

    console.log(`Applying active highlight for citation ${citationIndex + 1}/${currentCitations.length}: "${citation}"`);

    if (!citationData) {
      setIsProcessingHighlights(false);
      setLoadingPhase('complete');
      return;
    }

    // 1️⃣ Remove previous active-citation classes
    const prevActives = containerRef.current.querySelectorAll('.pdf-highlight.active-citation');
    prevActives.forEach((el) => el.classList.remove('active-citation'));

    // 2️⃣ Add active class to cached elements
    citationData.elements.forEach((el) => {
      el.classList.add('active-citation');
    });

    // 3️⃣ Scroll to first element
    if (citationData.elements.length > 0) {
      scrollToElement(citationData.elements[0]);
    }

    setIsProcessingHighlights(false);
    setLoadingPhase('complete');
  }


  // Trigger highlighting logic when relevant dependencies change
  useEffect(() => {
    // COMPLETELY SKIP text files - they are handled in isolation
    if (file.type === "txt") {
      return;
    }

    // Rest of the logic for non-text files only
    const isPdfReady = (file.type === "pdf" || fileUrl) && pagesRendered >= numPages && numPages > 0;
    const isConvertedDocReady = (file.type === "docx" || file.type === "doc" || file.type === "odt") && fileUrl && pagesRendered >= numPages && numPages > 0;
    const isConvertedDocTextOnlyReady = (file.type === "docx" || file.type === "doc" || file.type === "odt") && !fileUrl && rawText && fileError;

    const isContentReady = isPdfReady || isConvertedDocReady || isConvertedDocTextOnlyReady;

    if (isContentReady && !isLoading && containerRef.current) {
      console.log("Content ready, triggering IMPROVED applyHighlights. Search:", searchQuery, "Citations available:", !!file.citations?.length);

      const highlightDelay = 500;
      const timeoutId = setTimeout(() => {
        if (containerRef.current) {
          applyHighlights();
        }
      }, highlightDelay);

      return () => clearTimeout(timeoutId);
    } else {
      clearAllHighlightsAndState();
      console.log("Content not ready or loading, clearing highlights. Ready states:", { isPdfReady, isConvertedDocReady, isConvertedDocTextOnlyReady, isLoading });
    }
  }, [
    searchQuery,
    file.type,
    pagesRendered,
    numPages,
    fileUrl,
    rawText,
    isLoading,
    fileError
    // Note: Removed file object from dependencies to avoid unnecessary re-runs
  ]);

  // Function to scroll to a specific element
  function scrollToElement(element: HTMLElement | null) {
    if (!element) return;
    element.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // --- Navigation ---

  function handleNext() {
    // Handle text files with isolated navigation
    if (file.type === "txt") {
      if (textMatchCount > 0) {
        const nextIndex = (textActiveIndex + 1) % textMatchCount;
        setTextActiveIndex(nextIndex);
      }
      return;
    }

    // Handle other file types
    if (searchQuery.trim()) { // Navigate User Search Results
      if (userSearchMatches.length === 0) return;
      let nextIndex = currentUserSearchMatchIndex + 1;
      if (nextIndex >= userSearchMatches.length) {
        nextIndex = 0; // Wrap around
      }
      setCurrentUserSearchMatchIndex(nextIndex);
      applyActiveSearchHighlight(nextIndex, userSearchMatches);
    } else { // Navigate Citations
      if (citationList.length === 0) return;
      let nextIndex = currentCitationIndex + 1;
      if (nextIndex >= citationList.length) {
        nextIndex = 0; // Wrap around
      }
      setCurrentCitationIndex(nextIndex);
      applyActiveCitationHighlight(nextIndex, citationList, citationToElementsMap);
    }
  }

  function handlePrev() {
    // Handle text files with isolated navigation
    if (file.type === "txt") {
      if (textMatchCount > 0) {
        const prevIndex = (textActiveIndex - 1 + textMatchCount) % textMatchCount;
        setTextActiveIndex(prevIndex);
      }
      return;
    }

    // Handle other file types
    if (searchQuery.trim()) { // Navigate User Search Results
      if (userSearchMatches.length === 0) return;
      let prevIndex = currentUserSearchMatchIndex - 1;
      if (prevIndex < 0) {
        prevIndex = userSearchMatches.length - 1; // Wrap around
      }
      setCurrentUserSearchMatchIndex(prevIndex);
      applyActiveSearchHighlight(prevIndex, userSearchMatches);
    } else { // Navigate Citations
      if (citationList.length === 0) return;
      let prevIndex = currentCitationIndex - 1;
      if (prevIndex < 0) {
        prevIndex = citationList.length - 1; // Wrap around
      }
      setCurrentCitationIndex(prevIndex);
      applyActiveCitationHighlight(prevIndex, citationList, citationToElementsMap);
    }
  }

  // --- Download Handler --- (Unchanged)
  const handleDownload = async () => { /* ... as before ... */
    console.log(file)
    try {
      const downloadUrl = file.blob_url || file.url;
      if (!downloadUrl) throw new Error("No URL available for download");
      const response = await fetch(downloadUrl);
      if (!response.ok) throw new Error("Failed to fetch file for download");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download error:", error);
    }
  };

  // --- Rendering Components ---

  const TextFileRenderer = ({
    text,
    citations = [],
    searchQuery = "",
    textMode = "citation",
    activeIndex = -1,
    onIndexChange,
    onCountChange
  }: {
    text: string;
    citations?: string[];
    searchQuery?: string;
    textMode?: "search" | "citation";
    activeIndex?: number;
    onIndexChange?: (newIndex: number) => void;
    onCountChange?: (count: number) => void;
  }) => {
    const textContentRef = useRef<HTMLDivElement>(null);

    // Single useEffect that handles both search and citation highlighting
    useEffect(() => {
      const container = textContentRef.current;
      if (!container) return;

      console.log(`[TextFile] Mode: ${textMode}, Search: "${searchQuery}", Citations: ${citations.length}, ActiveIndex: ${activeIndex}`);

      const markInstance = new Mark(container);

      // Always start by clearing all highlights
      markInstance.unmark({
        done: () => {
          // Search mode - highlight search query
          if (textMode === "search" && searchQuery.trim()) {
            const regex = buildGapRegex(searchQuery.trim());
            console.log(`[TextFile] Highlighting search: "${searchQuery}"`);

            markInstance.markRegExp(regex, {
              className: "pdf-highlight",
              exclude: [".citation-overlay"],
              acrossElements: true,
              done: (totalMarks: number) => {
                const allMarks = Array.from(
                  container.querySelectorAll("mark.pdf-highlight")
                ) as HTMLElement[];

                const grouped = groupNearbyElements(allMarks);
                console.log(`[TextFile] Found ${grouped.length} search matches`);

                // Update count first
                if (onCountChange) onCountChange(grouped.length);

                if (grouped.length > 0) {
                  const safeIndex = Math.max(0, Math.min(activeIndex, grouped.length - 1));

                  // Remove any existing active classes
                  allMarks.forEach(el => el.classList.remove('active-search', 'active-citation'));

                  // Add active class to current match
                  grouped[safeIndex].classList.add('active-search');
                  grouped[safeIndex].scrollIntoView({ behavior: "smooth", block: "center" });

                  // Update index if needed
                  if (onIndexChange && safeIndex !== activeIndex) {
                    onIndexChange(safeIndex);
                  }
                } else {
                  if (onIndexChange) onIndexChange(-1);
                }
              },
              noMatch: () => {
                console.log(`[TextFile] No search matches found`);
                if (onCountChange) onCountChange(0);
                if (onIndexChange) onIndexChange(-1);
              }
            });
          }
          // Citation mode - highlight all citations, then make one active
          else if (textMode === "citation" && citations.length > 0) {
            console.log(`[TextFile] Citation mode - highlighting all citations, active: ${activeIndex + 1}/${citations.length}`);

            const uniqueCitations = Array.from(new Set(citations.filter(Boolean)));

            if (uniqueCitations.length === 0) {
              if (onCountChange) onCountChange(0);
              if (onIndexChange) onIndexChange(-1);
              return;
            }

            // Update count immediately
            if (onCountChange) onCountChange(uniqueCitations.length);

            // Step 1: Highlight ALL citations with base style
            let pendingCitations = uniqueCitations.length;
            const citationElementMap = new Map<number, HTMLElement[]>(); // Map citation index to its elements

            uniqueCitations.forEach((citation, citationIdx) => {
              const regex = buildGapRegex(citation.trim());

              console.log(`[TextFile] Highlighting citation ${citationIdx + 1}/${uniqueCitations.length}: "${citation.substring(0, 30)}..."`);

              markInstance.markRegExp(regex, {
                className: "pdf-highlight",
                exclude: [".citation-overlay"],
                acrossElements: true,
                each: (element: Element) => {
                  // Store which citation this element belongs to
                  const htmlElement = element as HTMLElement;
                  htmlElement.setAttribute('data-citation-index', citationIdx.toString());

                  // Keep track of elements for each citation
                  if (!citationElementMap.has(citationIdx)) {
                    citationElementMap.set(citationIdx, []);
                  }
                  citationElementMap.get(citationIdx)!.push(htmlElement);
                },
                done: () => {
                  pendingCitations--;
                  console.log(`[TextFile] Citation ${citationIdx + 1} highlighted, ${pendingCitations} remaining`);

                  if (pendingCitations === 0) {
                    // Step 2: All citations highlighted, now make one active
                    applyActiveCitationHighlight();
                  }
                },
                noMatch: () => {
                  pendingCitations--;
                  console.log(`[TextFile] Citation ${citationIdx + 1} not found, ${pendingCitations} remaining`);

                  // Try with shorter text for this citation
                  const words = citation.split(' ');
                  if (words.length > 5) {
                    const shorterText = words.slice(0, 5).join(' ');
                    const shorterRegex = buildGapRegex(shorterText);

                    console.log(`[TextFile] Retrying citation ${citationIdx + 1} with shorter text: "${shorterText}"`);

                    markInstance.markRegExp(shorterRegex, {
                      className: "pdf-highlight",
                      exclude: [".citation-overlay"],
                      acrossElements: true,
                      each: (element: Element) => {
                        const htmlElement = element as HTMLElement;
                        htmlElement.setAttribute('data-citation-index', citationIdx.toString());

                        if (!citationElementMap.has(citationIdx)) {
                          citationElementMap.set(citationIdx, []);
                        }
                        citationElementMap.get(citationIdx)!.push(htmlElement);
                      },
                      done: () => {
                        console.log(`[TextFile] Retry successful for citation ${citationIdx + 1}`);
                      },
                      noMatch: () => {
                        console.log(`[TextFile] Citation ${citationIdx + 1} still not found after retry`);
                      }
                    });
                  }

                  if (pendingCitations === 0) {
                    applyActiveCitationHighlight();
                  }
                }
              });
            });

            // Function to apply active highlighting to the current citation
            function applyActiveCitationHighlight() {
              console.log(`[TextFile] Applying active highlight to citation ${activeIndex + 1}`);

              // Add null check for container
              if (!container) return;

              // Remove all existing active-citation classes
              const allHighlights = container.querySelectorAll('.pdf-highlight.active-citation');
              allHighlights.forEach(el => el.classList.remove('active-citation'));

              // Determine safe index
              const safeIndex = Math.max(0, Math.min(activeIndex, uniqueCitations.length - 1));

              // Add active-citation class to elements belonging to the current citation
              const activeElements = citationElementMap.get(safeIndex) || [];

              if (activeElements.length > 0) {
                activeElements.forEach(el => {
                  el.classList.add('active-citation');
                });

                // Scroll to the first element of the active citation
                activeElements[0].scrollIntoView({ behavior: "smooth", block: "center" });
                console.log(`[TextFile] ✅ Applied active highlight to citation ${safeIndex + 1} with ${activeElements.length} elements`);
              } else {
                console.warn(`[TextFile] No elements found for citation ${safeIndex + 1}`);
              }

              // Update index if needed
              if (onIndexChange && safeIndex !== activeIndex) {
                onIndexChange(safeIndex);
              }
            }
          }
          // No highlighting mode
          else {
            console.log(`[TextFile] No highlighting needed`);
            if (onCountChange) onCountChange(0);
            if (onIndexChange) onIndexChange(-1);
          }
        }
      });
    }, [textMode, searchQuery, citations, activeIndex, text]);

    return (
      <div className="bg-white rounded-lg shadow-md p-6 max-w-[900px] mx-auto">
        <div ref={textContentRef}>
          <pre className="whitespace-pre-wrap font-mono text-sm overflow-x-auto max-w-full">
            {text}
          </pre>
        </div>
      </div>
    );
  };
  const ErrorDisplay = ({ message }: { message: string }) => (
    <div className="bg-white rounded-lg shadow-md p-8 max-w-[900px] mx-auto text-center">
      <div className="text-red-500 mb-4">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">{t('file_preview_error')}</h3>
      <p className="text-gray-500 mb-4">{message}</p>
      {!rawText && (
        <>
          <p className="text-sm text-gray-400 mb-6">
            {t('try_downloading')}
          </p>
          <Button onClick={handleDownload} className="mx-auto">
            <Download className="h-4 w-4 mr-2" />
            {t('download_file')}
          </Button>
        </>
      )}
    </div>
  );

  // Determine current display mode and counts
  const isTextFile = file.type === "txt";
  const isTextCitationMode = isTextFile && textMode === "citation";
  const isTextSearchMode = isTextFile && textMode === "search";
  const isCitationMode = !isTextFile && !searchQuery.trim() && citationList.length > 0;
  const isSearchMode = !isTextFile && searchQuery.trim();

  const displayCount = isTextFile ? textMatchCount :
    isCitationMode ? citationList.length :
      userSearchMatches.length;

  const currentIndex = isTextFile ? textActiveIndex :
    isCitationMode ? currentCitationIndex :
      currentUserSearchMatchIndex;

  // 7. UPDATE the citation text display logic:
  const currentCitationText = isCitationMode && currentCitationIndex !== -1 ? citationList[currentCitationIndex] :
    // For text files in citation mode, get the citation by index
    isTextCitationMode && textActiveIndex !== -1 && file.citations ? file.citations[textActiveIndex] :
      null;


  // Helper function to get loading message based on the current phase
  const getLoadingMessage = () => {
    if (isLoading) return t('loading_file');
    if (loadingPhase === 'rendering') return t('rendering_pages');
    if (loadingPhase === 'highlighting') {
      if (totalCitationsToProcess > 0) {
        return t('processing_highlights') + ` (${highlightProgress}/${totalCitationsToProcess})`;
      }
      return t('processing_highlights');
    }
    return t('processing');
  };

  // Calculate loading progress for the progress bar
  const getLoadingProgress = () => {
    if (isLoading) return 0;
    if (loadingPhase === 'rendering' && numPages > 0) {
      return (pagesRendered / numPages) * 100;
    }
    if (loadingPhase === 'highlighting' && totalCitationsToProcess > 0) {
      return (highlightProgress / totalCitationsToProcess) * 100;
    }
    return 0;
  };

  // UPDATED: Use the completion flag instead of citationList length
  const isProcessingCitations =
    !searchQuery.trim() &&
    !!file.citations &&
    file.citations.length > 0 &&
    file.type !== "txt" &&
    !citationProcessingCompleted; // Use the completion flag instead

  // Show overlay while any loading OR citation processing is active
  const showLoadingOverlay =
    isLoading ||
    isProcessingHighlights ||
    isProcessingCitations ||
    (loadingPhase !== 'complete' && pagesRendered < numPages);

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-background rounded-lg shadow-lg flex flex-col w-full max-w-6xl min-h-[97vh] max-h-[97vh] overflow-hidden relative">
        {/* Loading Overlay */}
        {showLoadingOverlay && (
          <div className="absolute inset-0 bg-background/80 flex flex-col items-center justify-center z-30">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4"></div>
            <span className="text-sm text-gray-600 mb-2">{getLoadingMessage()}</span>
            
            {/* Progress bar for rendering pages or processing citations */}
            {getLoadingProgress() > 0 && (
              <div className="w-48 bg-gray-200 rounded-full h-2 mb-1 overflow-hidden">
                <div 
                  className="bg-primary h-full transition-all duration-300 ease-in-out" 
                  style={{ width: `${getLoadingProgress()}%` }}
                ></div>
              </div>
            )}
            
            {/* Detailed status for pages or citations */}
            {loadingPhase === 'rendering' && numPages > 0 && (
              <span className="text-xs text-gray-500">{pagesRendered} {t('pages_from')} {numPages}</span>
            )}
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b z-40">
          <div className="flex items-center space-x-4 flex-shrink min-w-0">
            <h2 className="text-xl font-semibold truncate" title={file.name}>{file.name}</h2>
            <span className="text-sm text-gray-500 bg-secondary px-2 py-1 rounded-full uppercase flex-shrink-0">
              {file.type}
            </span>
          </div>
          <div className="flex space-x-2 flex-shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDownload}
              title={t('download_file')}
            >
              <Download className="h-5 w-5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              title={t('close_preview')}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* Search bar */}
        <div className="flex items-center p-2 px-4 md:px-6 border-b z-40 flex-wrap gap-y-2">
          <div className="flex flex-grow items-center space-x-2 min-w-[250px] mb-2 md:mb-0">
            <Search className="h-5 w-5 text-gray-400 flex-shrink-0" />
            <Input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={file.citations && file.citations.length > 0 && !searchQuery 
                ? t('citations_highlighted') 
                : t('type_phrase_to_search')
              }
              disabled={isProcessingHighlights}
              className="flex-1"
            />
          </div>

          <div className="flex flex-grow items-center justify-between md:justify-end space-x-2 w-full md:w-auto">
            <span className="text-sm text-gray-600 min-w-[100px] text-center md:text-left" data-text-file-counter>
              {isProcessingHighlights || isProcessingCitations ? (
                <span className="italic">{t('processing')}</span>
              ) : displayCount > 0 ? (
                `${currentIndex + 1} / ${displayCount} ${(isCitationMode || isTextCitationMode) ? t('citation') : t('fragment')}${displayCount !== 1 ? (tCommon('language') === 'pl' ? 'ów' : 's') : ''}`
              ) : (isSearchMode || isTextSearchMode) ? (
                t('no_matches')
              ) : file.citations && file.citations.length > 0 && 
                  citationProcessingCompleted && 
                  citationList.length === 0 ? (
                t('no_citations_found_in_document')
              ) : (
                ""
              )}
            </span>

            <div className="flex space-x-1">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrev}
                disabled={displayCount === 0 || isProcessingHighlights}
                title={t('previous')}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNext}
                disabled={displayCount === 0 || isProcessingHighlights}
                title={t('next')}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Current Citation Text Display */}
          {currentCitationText && (
            <div className="w-full text-xs bg-secondary p-2 mt-2 rounded border border-secondary-border text-primary overflow-hidden text-ellipsis whitespace-nowrap">
              <span className="font-medium">{t('citation')} {(isCitationMode ? currentCitationIndex : textActiveIndex) + 1}: </span>
              <span className="italic">{currentCitationText}</span>
            </div>
          )}

          {!searchQuery.trim() && file.citations && file.citations.length > 0 && citationProcessingCompleted && citationList.length === 0 && (
            <div className="w-full text-xs bg-amber-50 border border-secondary-200 p-2 mt-2 rounded text-primary-800">
              <span>
                {notFoundCitations.length > 0 ? (
                  <>
                    {t('could_not_locate')} {notFoundCitations.length} {t('citation')}
                    {notFoundCitations.length !== 1 ? (tCommon('language') === 'pl' ? 'ów' : 's') : ''}.
                    {notFoundCitations.length <= 3 ? (
                      <> : &quot;{notFoundCitations.slice(0, 3).map(c => c.substring(0, 40) + (c.length > 40 ? '...' : '')).join('&quot;, &quot;')}&quot;</>
                    ) : null}
                  </>
                ) : (
                  t('citations_exist_but_not_found')
                )}
              </span>
            </div>
          )}
        </div>

        {/* Main content container with updated error handling */}
        <div
          ref={containerRef}
          className="flex-1 overflow-auto p-4 custom-scrollbar bg-secondary"
          onClick={(e) => e.stopPropagation()}
          style={{ position: 'relative' }}
        >
          {fileError && !rawText && !fileUrl ? (
            <ErrorDisplay message={fileError} />
          ) : fileUrl && !fileError ? (
            <div className="relative w-full min-h-full flex justify-center">
              <Document
                key={fileUrl}
                file={fileUrl}
                onLoadStart={onDocumentLoadStart}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                className="flex flex-col items-center"
                error={<ErrorDisplay message={t('could_not_load_pdf')} />}
                loading={null}
                noData={<ErrorDisplay message={t('no_data_in_pdf')} />}
              >
                {Array.from(new Array(numPages), (_, idx) => (
                  <Page
                    key={`page_${idx + 1}`}
                    pageNumber={idx + 1}
                    width={containerWidth}
                    renderTextLayer
                    renderAnnotationLayer={false}
                    onRenderSuccess={onPageRenderSuccess}
                    className="mb-4 shadow-lg"
                    error={<div className="p-4 border border-red-200 bg-red-50 rounded mb-4 text-red-500 text-sm">{t('error_rendering_page')} {idx + 1}</div>}
                    loading={<Skeleton className="w-full h-[11in]" style={{width: containerWidth, height: containerWidth * 11/8.5}} />}
                  />
                ))}
              </Document>
            </div>
          ) : rawText ? (
            <div className="relative">
              {fileError && (file.type === "docx" || file.type === "doc" || file.type === "odt") && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 max-w-[900px] mx-auto text-sm">
                  <p className="text-amber-800 font-medium">
                    {t('visual_preview_failed')}: {fileError}
                  </p>
                  <p className="text-amber-700 mt-1">
                    {t('displaying_text_instead')}
                  </p>
                </div>
              )}
              <TextFileRenderer 
                text={rawText}
                citations={file.citations || []}
                searchQuery={searchQuery}
                textMode={textMode}
                activeIndex={textActiveIndex}
                onIndexChange={handleTextIndexChange}
                onCountChange={handleTextCountChange}
              />
            </div>
          ) : !isLoading && !fileError ? (
            <div className="flex items-center justify-center h-full">
              <div className="p-6 text-center">
                <p className="text-lg text-gray-700">{t('no_preview_available')}</p>
                <p className="text-sm text-gray-500 mt-2">
                  {t('try_downloading')}
                </p>
                <Button onClick={handleDownload} className="mt-4">
                  <Download className="h-4 w-4 mr-2" />
                  {t('download_file')}
                </Button>
              </div>
            </div>
          ) : null }
        </div>
      </div>
    </div>
  );
}