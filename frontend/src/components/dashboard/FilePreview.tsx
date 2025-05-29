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
    background-color: rgba(255, 255, 0, 0.3); /* Light yellow, less prominent */
    border-radius: 2px;
  }
  /* Active citation highlight style */
  .pdf-highlight.active-citation {
    background-color: yellow !important; /* Bright yellow, prominent */
    box-shadow: 0 0 3px 1px rgba(255, 215, 0, 0.7); /* Optional glow */
  }
  /* Style for the specific element scrolled to (useful for search) */
  .active-match {
     outline: 1px solid red; /* Or different background */
  }
`;

export function buildGapRegex(phrase: string): RegExp {
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const words = phrase.trim().split(/\s+/).map(esc);
  const GAP   = "[\\s\\p{P}\\p{S}\\d]*";
  return new RegExp(words.join(GAP), "giu");
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

async function highlightCitationFragments(
  citation: string,
  markInstance: any,
  excludeSelectors: string[]
): Promise<HTMLElement[]> {
  
  if (!citation?.trim()) return [];

  console.log(`[Citation] Processing: "${citation.substring(0, 80)}..."`);
  
  // Use EXACTLY the same approach as user search - no normalization, no complexity
  const regex = buildGapRegex(citation.trim());
  console.log(`[Citation] Using regex:`, regex);
  
  const collectedElements: HTMLElement[] = [];
  
  return new Promise((resolve) => {
    markInstance.markRegExp(regex, {
      className: "pdf-highlight",
      exclude: excludeSelectors,
      acrossElements: true,
      each: (el: Element) => {
        collectedElements.push(el as HTMLElement);
      },
      done: () => {
        console.log(`[Citation] Found ${collectedElements.length} elements`);
        resolve(collectedElements);
      },
      noMatch: () => {
        console.log(`[Citation] No match found`);
        resolve(collectedElements);
      },
    });
  });
}

export function FilePreview({ file, onClose, loading: propLoading = false }: FilePreviewProps) {
  const [fileUrl, setFileUrl] = useState<string>("");
  const [rawText, setRawText] = useState<string>("");
  const [numPages, setNumPages] = useState<number>(0);
  const [pagesRendered, setPagesRendered] = useState<number>(0);
  const [internalIsLoading, setInternalIsLoading] = useState<boolean>(true);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileContentRef = useRef<Blob | null>(null);
  // const pdfDocumentRef = useRef<any>(null); // Keep if needed for direct PDF manipulation

  const isLoading = propLoading || internalIsLoading;

  // Search & Citation State
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showSearchBar, setShowSearchBar] = useState<boolean>(true); // Keep visible

  // State for User Search Results
  const [userSearchMatches, setUserSearchMatches] = useState<HTMLElement[]>([]);
  const [currentUserSearchMatchIndex, setCurrentUserSearchMatchIndex] = useState<number>(-1);

  // State for Citation Highlighting & Navigation
  const [citationToElementsMap, setCitationToElementsMap] = useState<Map<string, { fragments: string[], elements: HTMLElement[] }>>(new Map());
  const [citationList, setCitationList] = useState<string[]>([]); // Ordered list of unique citations
  const [currentCitationIndex, setCurrentCitationIndex] = useState<number>(-1); // Index in citationList
  const [isProcessingHighlights, setIsProcessingHighlights] = useState<boolean>(false); // Combined loading for search/citations
  
  // Add loading state phases for better user feedback
  const [loadingPhase, setLoadingPhase] = useState<'initial' | 'rendering' | 'highlighting' | 'complete'>('initial');
  const [highlightProgress, setHighlightProgress] = useState<number>(0);
  const [totalCitationsToProcess, setTotalCitationsToProcess] = useState<number>(0);

  // Container & layout
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(800);
  const EXCLUDE_SELECTORS = [".citation-overlay"]; // Example if you add popups

  // Apply custom styles
  useEffect(() => {
    const styleEl = document.createElement('style');
    styleEl.innerHTML = customStyles;
    document.head.appendChild(styleEl);
    return () => {
      document.head.removeChild(styleEl);
    };
  }, []);

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
        setFileError(`Error processing file: ${err instanceof Error ? err.message : String(err)}`);
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


  // --- Highlighting Logic ---

  // Function to clear all highlights and reset related state
  function clearAllHighlightsAndState() {
    if (containerRef.current) {
      const markInstance = new Mark(containerRef.current);
      markInstance.unmark();
    }
    setUserSearchMatches([]);
    setCurrentUserSearchMatchIndex(-1);
    setCitationToElementsMap(new Map());
    setCitationList([]);
    setCurrentCitationIndex(-1);
    // Don't clear searchQuery here, it's user input
  }

function applyHighlights() {
  if (!containerRef.current || isLoading) return;

  console.log(`[Highlighting] Starting - Search: "${searchQuery}", Citations: ${file.citations?.length || 0}`);
  
  setIsProcessingHighlights(true);
  setLoadingPhase("highlighting");
  const markInstance = new Mark(containerRef.current);

  // Always start with a clean slate
  markInstance.unmark({
    done: () => requestAnimationFrame(() => {
      if (!containerRef.current) {
        setIsProcessingHighlights(false);
        setLoadingPhase("complete");
        return;
      }

      /* ────────────────────────────────────────────────
         USER SEARCH BRANCH (unchanged - this works well)
         ──────────────────────────────────────────────── */
      if (searchQuery.trim()) {
        console.log(`[User Search] Processing: "${searchQuery}"`);
        const regex = buildGapRegex(searchQuery);

        const reps: HTMLElement[] = [];
        const seenIds = new Set<string>();

        markInstance.markRegExp(regex, {
          className: "pdf-highlight",
          exclude: EXCLUDE_SELECTORS,
          acrossElements: true,
          each: (el) => {
            const id = (el as HTMLElement).getAttribute("data-markjs");
            if (id && !seenIds.has(id)) {
              reps.push(el as HTMLElement);
              seenIds.add(id);
            }
          },
          done: () => {
            console.log(`[User Search] Found ${reps.length} matches`);
            setUserSearchMatches(reps);
            const first = reps.length ? 0 : -1;
            setCurrentUserSearchMatchIndex(first);

            // clear citation mode
            setCitationToElementsMap(new Map());
            setCitationList([]);
            setCurrentCitationIndex(-1);

            if (first !== -1) scrollToElement(reps[first], true);

            setIsProcessingHighlights(false);
            setLoadingPhase("complete");
          },
          noMatch: () => {
            console.log(`[User Search] No matches found`);
            setUserSearchMatches([]);
            setCurrentUserSearchMatchIndex(-1);
            setIsProcessingHighlights(false);
            setLoadingPhase("complete");
          },
        });
        return;
      }

      /* ────────────────────────────────────────────────
         CITATION HIGHLIGHTING BRANCH (simplified)
         ──────────────────────────────────────────────── */
      if (file.citations && file.citations.length > 0 && citationList.length === 0) {
        console.log(`[Citations] Processing ${file.citations.length} citations ONE BY ONE`);
        
        const newMap: Map<string, { fragments: string[]; elements: HTMLElement[] }> = new Map();
        const unique = Array.from(new Set(file.citations.filter(Boolean)));
        setTotalCitationsToProcess(unique.length);
        setHighlightProgress(0);

        const processCitationSequentially = async (index: number) => {
          if (index >= unique.length) {
            // All done
            console.log(`[Citations] Final: ${newMap.size}/${unique.length} citations highlighted`);
            
            setCitationToElementsMap(newMap);
            const list = Array.from(newMap.keys());
            setCitationList(list);

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
          
          // Add a small delay to ensure DOM is stable (like user typing delay)
          await new Promise(resolve => setTimeout(resolve, 10));
          
          try {
            const els = await highlightCitationFragments(cit, markInstance, EXCLUDE_SELECTORS);
            
            if (els.length > 0) {
              newMap.set(cit, {
                fragments: splitCitationToFragments(cit),
                elements: els,
              });
              console.log(`[Citations] ✅ Success: ${els.length} elements`);
            } else {
              console.log(`[Citations] ❌ No matches found`);
              
              // Debug comparison with user search approach
              console.log(`[Debug] Test this in user search: "${cit.substring(0, 100)}..."`);
              
              // Try to help debug by checking if text exists in DOM at all
              if (containerRef.current) {
                const pdfText = containerRef.current.textContent || '';
                const firstFewWords = cit.split(' ').slice(0, 3).join(' ');
                if (pdfText.includes(firstFewWords)) {
                  console.log(`[Debug] ⚠️  First few words "${firstFewWords}" found in PDF - might be encoding issue`);
                } else {
                  console.log(`[Debug] ❌ First few words "${firstFewWords}" NOT found in PDF`);
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
      }
      
    }) // <- This closes the requestAnimationFrame callback
  }); // <- This closes the markInstance.unmark call
} // <- This closes the applyHighlights function


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
        scrollToElement(citationData.elements[0], false);
      }

      setIsProcessingHighlights(false);
      setLoadingPhase('complete');
  }


  // Trigger highlighting logic when relevant dependencies change
  useEffect(() => {
    // Determine if content is ready
    const isPdfReady = (file.type === "pdf" || fileUrl) && pagesRendered >= numPages && numPages > 0;
    const isTextReady = file.type === "txt" && rawText;
    const isConvertedDocReady = (file.type === "docx" || file.type === "doc" || file.type === "odt") && fileUrl && pagesRendered >= numPages && numPages > 0;
    // Fallback for converted docs where only raw text is available
    const isConvertedDocTextOnlyReady = (file.type === "docx" || file.type === "doc" || file.type === "odt") && !fileUrl && rawText && fileError;

    const isContentReady = isPdfReady || isTextReady || isConvertedDocReady || isConvertedDocTextOnlyReady;

    if (isContentReady && !isLoading && containerRef.current) {
      console.log("Content ready, triggering applyHighlights. Search:", searchQuery, "Citations available:", !!file.citations?.length);
      // Use a short delay to ensure the text layer DOM is fully available after page render
      const highlightDelay = 50; // ms
      const timeoutId = setTimeout(() => {
          if (containerRef.current) { // Re-check containerRef inside timeout
             applyHighlights();
          }
      }, highlightDelay);
      // Cleanup function to clear timeout if dependencies change before it fires
      return () => clearTimeout(timeoutId);
    } else {
      // Clear highlights if content isn't ready
       clearAllHighlightsAndState();
       console.log("Content not ready or loading, clearing highlights. Ready states:", { isPdfReady, isTextReady, isConvertedDocReady, isConvertedDocTextOnlyReady, isLoading });
    }

    // Debounce or delay could be added here if performance is an issue on rapid changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
      searchQuery, // User input
      // file.citations, // Citations array (rely on file object change)
      file, // File object change detects new citations
      pagesRendered, // PDF page rendering progress
      numPages,      // PDF total pages
      fileUrl,       // Indicates PDF/converted DOCX is loaded
      rawText,       // Indicates text content is loaded (for TXT or fallback)
      isLoading,     // Overall loading state
      fileError      // Handle cases where only text fallback is available
      // Do NOT depend on citationList, currentCitationIndex etc. here - those are results, not triggers.
      // applyHighlights itself manages the state transitions based on searchQuery vs citations.
  ]);

  // Function to scroll to a specific element
  function scrollToElement(element: HTMLElement | null, markAsActiveSearchMatch: boolean) {
    if (!element) return;

    // Remove active class from previous search match if applicable
    if (currentUserSearchMatchIndex >= 0 && userSearchMatches[currentUserSearchMatchIndex]) {
        userSearchMatches[currentUserSearchMatchIndex].classList.remove("active-match");
    }

    element.scrollIntoView({ behavior: "smooth", block: "center" });

    // Add specific class for the currently focused *search* match
    if (markAsActiveSearchMatch) {
        element.classList.add("active-match");
    }
  }

  // --- Navigation ---

  function handleNext() {
    if (searchQuery.trim()) { // Navigate User Search Results
      if (userSearchMatches.length === 0) return;
      let nextIndex = currentUserSearchMatchIndex + 1;
      if (nextIndex >= userSearchMatches.length) {
        nextIndex = 0; // Wrap around
      }
      setCurrentUserSearchMatchIndex(nextIndex);
      scrollToElement(userSearchMatches[nextIndex], true);
    } else { // Navigate Citations
      if (citationList.length === 0) return;
      let nextIndex = currentCitationIndex + 1;
      if (nextIndex >= citationList.length) {
        nextIndex = 0; // Wrap around
      }
      setCurrentCitationIndex(nextIndex);
      // Trigger re-highlighting for the new citation index
      applyActiveCitationHighlight(nextIndex, citationList, citationToElementsMap);
    }
  }

  function handlePrev() {
    if (searchQuery.trim()) { // Navigate User Search Results
      if (userSearchMatches.length === 0) return;
      let prevIndex = currentUserSearchMatchIndex - 1;
      if (prevIndex < 0) {
        prevIndex = userSearchMatches.length - 1; // Wrap around
      }
      setCurrentUserSearchMatchIndex(prevIndex);
      scrollToElement(userSearchMatches[prevIndex], true);
    } else { // Navigate Citations
      if (citationList.length === 0) return;
      let prevIndex = currentCitationIndex - 1;
      if (prevIndex < 0) {
        prevIndex = citationList.length - 1; // Wrap around
      }
      setCurrentCitationIndex(prevIndex);
      // Trigger re-highlighting for the new citation index
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

const TextFileRenderer = ({ text }: { text: string }) => {
  const textContentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!textContentRef.current) return;

    const markInstance = new Mark(textContentRef.current);
    markInstance.unmark({
      done: () => {
        if (!searchQuery.trim()) return;

        const regex = buildGapRegex(searchQuery);

        markInstance.markRegExp(regex, {
          className: "pdf-highlight",
          exclude: EXCLUDE_SELECTORS,
          acrossElements: true, // spans can be split even in <pre>
        });
      },
    });
  }, [searchQuery, text]);

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


  // Fallback error component
  const ErrorDisplay = ({ message }: { message: string }) => ( /* ... as before ... */
     <div className="bg-white rounded-lg shadow-md p-8 max-w-[900px] mx-auto text-center">
      <div className="text-red-500 mb-4">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">File Preview Error</h3>
      <p className="text-gray-500 mb-4">{message}</p>
      {!rawText && ( // Only show download if text isn't available either
        <>
            <p className="text-sm text-gray-400 mb-6">
            You can still download the file to view it in its native application.
            </p>
            <Button onClick={handleDownload} className="mx-auto">
                <Download className="h-4 w-4 mr-2" />
                Download File
            </Button>
        </>
      )}
    </div>
  );

  // Determine current display mode and counts
  const isCitationMode = !searchQuery.trim() && citationList.length > 0;
  const isSearchMode = searchQuery.trim();
  const displayCount = isCitationMode ? citationList.length : userSearchMatches.length;
  const currentIndex = isCitationMode ? currentCitationIndex : currentUserSearchMatchIndex;
  const currentCitationText = isCitationMode && currentCitationIndex !== -1 ? citationList[currentCitationIndex] : null;
  
  // Helper function to get loading message based on the current phase
  const getLoadingMessage = () => {
    if (isLoading) return 'Wczytywanie pliku...';
    if (loadingPhase === 'rendering') return 'Renderowanie stron...';
    if (loadingPhase === 'highlighting') {
      if (totalCitationsToProcess > 0) {
        return `Przetwarzanie zaznaczeń... (${highlightProgress}/${totalCitationsToProcess})`;
      }
      return 'Przetwarzanie zaznaczeń...';
    }
    return 'Przetwarzanie...';
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
  
  // Consider we are still processing citations if we haven't built citationList yet
  const isProcessingCitations =
    !searchQuery.trim() &&
    !!file.citations &&
    file.citations.length > 0 &&
    citationList.length === 0;

  // Show overlay while any loading OR citation processing is active
  const showLoadingOverlay =
    isLoading ||
    isProcessingHighlights ||
    isProcessingCitations ||
    (loadingPhase !== 'complete' && pagesRendered < numPages);

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-background rounded-lg shadow-lg flex flex-col w-full max-w-6xl max-h-[97vh] overflow-hidden relative">
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
                  <span className="text-xs text-gray-500">{pagesRendered} z {numPages} stron</span>
                )}
            </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b z-10">
          <div className="flex items-center space-x-4 flex-shrink min-w-0">
            <h2 className="text-xl font-semibold truncate" title={file.name}>{file.name}</h2>
            <span className="text-sm text-gray-500 bg-secondary px-2 py-1 rounded-full uppercase flex-shrink-0">
              {file.type}
            </span>
          </div>
          <div className="flex space-x-2 flex-shrink-0">
            {/* Search toggle removed - keeping bar visible */}
             <Button
              variant="ghost"
              size="icon"
              onClick={handleDownload}
              title="Download File"
            >
              <Download className="h-5 w-5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              title="Close Preview (Esc)"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* Search bar */}
        {showSearchBar && (
          <div className="flex items-center p-2 px-4 md:px-6 border-b z-10 flex-wrap gap-y-2">
            {/* Input and Status */}
            <div className="flex flex-grow items-center space-x-2 min-w-[250px] mb-2 md:mb-0">
              <Search className="h-5 w-5 text-gray-400 flex-shrink-0" />
              <Input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={file.citations && file.citations.length > 0 && !searchQuery ? "Cytaty zaznaczone. Wpisz frazę aby ją wyszukać..." : "Wpisz frazę aby ją wyszukać..."}
                disabled={isProcessingHighlights}
                className="flex-1"
              />
            </div>

            {/* Citation/Search Info & Navigation */}
            <div className="flex flex-grow items-center justify-between md:justify-end space-x-2 w-full md:w-auto">
                {/* Match Count/Index */}
                 <span className="text-sm text-gray-600 min-w-[100px] text-center md:text-left">
                   {isProcessingHighlights || isProcessingCitations ? (
                      <span className="italic">Przetwarzanie...</span>
                   ) : displayCount > 0 ? (
                      `${currentIndex + 1} / ${displayCount} ${isCitationMode ? 'cytat' : 'fragment'}${displayCount !== 1 ? 'ów' : ''}`
                   ) : isSearchMode ? (
                      "No matches"
                   ) : file.citations && file.citations.length > 0 && citationList.length === 0 && !isProcessingCitations ? (
                      "Brak cytatów w pliku."
                   ) : (
                      "" // Nothing to show if no search/citations
                   )}
                 </span>

                 {/* Navigation Buttons */}
                <div className="flex space-x-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrev}
                    disabled={displayCount === 0 || isProcessingHighlights}
                    title="Previous"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleNext}
                    disabled={displayCount === 0 || isProcessingHighlights}
                    title="Next"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
            </div>

             {/* Current Citation Text Display */}
             {currentCitationText && (
                <div className="w-full text-xs bg-secondary p-2 mt-2 rounded border border-secondary-border text-primary overflow-hidden text-ellipsis whitespace-nowrap">
                  <span className="font-medium">Citation {currentCitationIndex + 1}: </span>
                  <span className="italic">{currentCitationText}</span>
                </div>
              )}
          </div>
        )}

        {/* Main content container */}
        <div
          ref={containerRef}
          // Use custom scrollbar class OR standard scrollbar based on preference
          className="flex-1 overflow-auto p-4 custom-scrollbar bg-secondary" // Added bg color for contrast
          onClick={(e) => e.stopPropagation()}
          // Style needed for Mark.js acrossElements with position:relative containers like react-pdf pages
          style={{ position: 'relative' }}
        >
          {fileError && !rawText && !fileUrl ? ( // Complete error, nothing to show
            <ErrorDisplay message={fileError} />
          ) : fileUrl && !fileError ? ( // PDF or Converted DOCX/ODT view
            <div className="relative w-full min-h-full flex justify-center"> {/* Center content */}
              {/* Added key to Document to force remount on fileUrl change */}
              <Document
                key={fileUrl}
                file={fileUrl}
                onLoadStart={onDocumentLoadStart}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                className="flex flex-col items-center" // Center pages
                error={<ErrorDisplay message="Could not load PDF document. It may be corrupted or unsupported." />}
                loading={null} // Handled by outer loading state
                noData={<ErrorDisplay message="No data found in the PDF file." />}
              >
                {Array.from(new Array(numPages), (_, idx) => (
                  <Page
                    key={`page_${idx + 1}`}
                    pageNumber={idx + 1}
                    width={containerWidth}
                    renderTextLayer // Essential for highlighting
                    renderAnnotationLayer={false} // Usually false for previews
                    onRenderSuccess={onPageRenderSuccess}
                    className="mb-4 shadow-lg" // Add shadow for page separation
                     error={<div className="p-4 border border-red-200 bg-red-50 rounded mb-4 text-red-500 text-sm">Error rendering page {idx + 1}</div>}
                     loading={<Skeleton className="w-full h-[11in]" style={{width: containerWidth, height: containerWidth * 11/8.5}} />} // Approximate page height
                  />
                ))}
              </Document>
            </div>
          ) : rawText ? ( // TXT file or Fallback text view
            <div className="relative">
              {/* Show warning if it's a fallback due to conversion error */}
              {fileError && (file.type === "docx" || file.type === "doc" || file.type === "odt") && (
                 <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 max-w-[900px] mx-auto text-sm">
                    <p className="text-amber-800 font-medium">
                      Visual preview failed: {fileError}
                    </p>
                    <p className="text-amber-700 mt-1">
                      Displaying extracted text content instead. Highlighting may be limited.
                    </p>
                 </div>
              )}
               {/* Render the text content */}
              <TextFileRenderer text={rawText} />
            </div>
          ) : !isLoading && !fileError ? ( // No preview available state (and not loading/error)
            <div className="flex items-center justify-center h-full">
              <div className="p-6 text-center">
                <p className="text-lg text-gray-700">No preview available.</p>
                <p className="text-sm text-gray-500 mt-2">
                  Try downloading the file.
                </p>
                 <Button onClick={handleDownload} className="mt-4">
                    <Download className="h-4 w-4 mr-2" />
                    Download File
                </Button>
              </div>
            </div>
          ) : null /* Loading state handled by overlay */ }
        </div>
      </div>
    </div>
  );
}