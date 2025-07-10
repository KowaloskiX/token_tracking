import React, { useMemo, useState, useEffect } from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import { Message } from "@/types";
import { useDashboard } from '@/context/DashboardContext';
import { Bot, Paperclip } from "lucide-react";
import Thinking from '../../loaders/Thinking';
import { motion, Variants } from "framer-motion";
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import remarkBreaks from 'remark-breaks';
import { FilePreview } from '../FilePreview';
import { getFileById } from '@/utils/fileActions';
import { useTranslations } from 'next-intl';

interface Citation {
  filename?: string;
  file_id?: string;
  content?: string;
}

interface FileData {
    _id: string;
    filename: string;
    type: string;
    url?: string;
    blob_url?: string;
}

interface ChatMessageProps {
  message: Message;
  isThinking?: boolean;
  isFullCite?: boolean;
}

interface CodeProps extends React.HTMLAttributes<HTMLElement> {
  inline?: boolean;
  children?: React.ReactNode;
}

interface PreviewFile {
  _id: string;
  name: string;
  type: string;
  url: string;
  blob_url?: string;
  citations?: string[];
}

interface GroupedCitationDisplayData {
    fileData: FileData;
    citationContents: string[];
}

const ChatMessage = ({ message, isThinking }: ChatMessageProps) => {
  const { user } = useDashboard();
  const isAssistant = message.role === 'assistant';
  const isSystem = message.role === 'system';
  const userInitial = user?.name ? user.name.charAt(0).toUpperCase() : 'U';
  
  // Translation hooks
  const t = useTranslations('dashboard.chat');
  const tTenders = useTranslations('dashboard.tenders');
  
  const [citationFilesData, setCitationFilesData] = useState<FileData[]>([]);
  const [isLoadingCitationFiles, setIsLoadingCitationFiles] = useState(false);
  const [previewFile, setPreviewFile] = useState<PreviewFile | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  useEffect(() => {
    const uniqueFileIds = Array.from(
      new Set((message.citations || [])
        .map(c => c?.file_id)
        .filter((id): id is string => !!id))
    );

    if (uniqueFileIds.length > 0) {
      setIsLoadingCitationFiles(true);
      Promise.all(uniqueFileIds.map(id => getFileById(id)))
        .then((files: (FileData | null)[]) => {
          const validFiles = files.filter((file): file is FileData => file !== null);
          setCitationFilesData(validFiles);
        })
        .catch((error: Error) => {
          console.error("Failed to fetch citation file data:", error);
          setCitationFilesData([]);
        })
        .finally(() => {
          setIsLoadingCitationFiles(false);
        });
    } else {
      setCitationFilesData([]);
    }
  }, [message.citations]);

  const formatMessage = (text: string): string => {
    text = text.replace(/\\n/g, '\n');
    return text?.replace(/(\d+)\./g, "$1\\.") || '';
  };

  const truncateFilename = (filename: string): string => {
    return filename.length <= 25 ? filename : `${filename.slice(0, 25)}...`;
  };

  const formattedMessage = formatMessage(message.content || '');

  const containerVariants: Variants = {
    hidden: { opacity: 0, y: 7 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.3,
        when: "beforeChildren",
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: -7 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.2,
        ease: "easeOut",
      },
    },
  };

  const handleFileClick = (groupData: GroupedCitationDisplayData) => {
    setIsLoadingPreview(true);
    setPreviewFile(null);

    const fileType = getFileType(groupData.fileData.filename?.split('.').pop() || groupData.fileData.type || '');
    const previewUrl = groupData.fileData.blob_url || groupData.fileData.url;

    if (previewUrl) {
        setPreviewFile({
            _id: groupData.fileData._id,
            name: groupData.fileData.filename || 'Unnamed File',
            type: fileType,
            url: previewUrl,
            blob_url: groupData.fileData.blob_url,
            citations: groupData.citationContents.length > 0 ? groupData.citationContents : undefined,
        });
    } else {
        console.error("Cannot preview: File data from folder context is missing blob_url or url.", groupData.fileData);
        setPreviewFile({
            _id: groupData.fileData._id,
            name: groupData.fileData.filename || 'Preview Unavailable (Missing URL)',
            type: fileType,
            url: '',
            blob_url: undefined,
            citations: groupData.citationContents.length > 0 ? groupData.citationContents : undefined,
        });
    }

    setTimeout(() => {
         setIsLoadingPreview(false);
    }, 50);
  };

  const getFileType = (extension: string): string => {
    switch(extension.toLowerCase()) {
      case 'pdf': return 'pdf';
      case 'docx': return 'docx';
      case 'doc': return 'doc';
      case 'odt': return 'odt';
      case 'txt': return 'txt';
      default:
        return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(extension.toLowerCase())
          ? 'image'
          : (extension || 'unknown');
    }
  };

  const handleClosePreview = () => {
    setPreviewFile(null);
  };

  const groupCitationsForDisplay = (citations: Citation[], fetchedFiles: FileData[]): GroupedCitationDisplayData[] => {
    const map = new Map<string, GroupedCitationDisplayData>();
    const fetchedFileMap = new Map(fetchedFiles.map(f => [f._id, f]));

    if (!Array.isArray(citations)) {
      return [];
    }

    for (const c of citations) {
      if (!c || typeof c.file_id !== 'string' || !c.file_id) {
        continue;
      }

      const matchedFileData = fetchedFileMap.get(c.file_id);

      if (matchedFileData) {
        if (!map.has(c.file_id)) {
          map.set(c.file_id, { fileData: matchedFileData, citationContents: [] });
        }
        if (typeof c.content === 'string' && c.content.trim().length > 0) {
          map.get(c.file_id)!.citationContents.push(c.content.trim());
        }
      }
    }
    return Array.from(map.values());
  };

  const renderAttachments = () => {
    const citations = Array.isArray(message.citations) ? message.citations : [];
    const groupedForDisplay = groupCitationsForDisplay(citations, citationFilesData);

    if (groupedForDisplay.length === 0) return null;

    return (
      <motion.div
        className="mt-1 space-y-0.5 mb-1"
        initial="hidden"
        animate="visible"
        variants={containerVariants}
      >
        <motion.div
          className="text-xs text-body-text flex items-center gap-1 mb-2 mt-2"
          variants={itemVariants}
        >
          <span>{tTenders('sources')}:</span>
        </motion.div>
        <div className="flex flex-wrap gap-1.5 ">
          {groupedForDisplay.map(groupData => (
            <motion.div
              key={groupData.fileData._id}
              className="bg-secondary cursor-pointer hover:bg-secondary-hover border border-secondary-border shadow-sm rounded-md px-2 py-0.5 text-xs flex items-center gap-1 max-w-xs"
              variants={itemVariants}
              whileHover={{ scale: 1.02, transition: { duration: 0.2 } }}
              whileTap={{ scale: 0.98 }}
              onClick={() => handleFileClick(groupData)}
              title={`${groupData.fileData.filename}\n${tTenders('citations')}:\n${groupData.citationContents.map(c => `- ${c}`).join('\n')}`}
            >
              <Paperclip className="size-3 text-neutral-400 flex-shrink-0" />
              <div className="truncate">
                <span className="text-neutral-700">
                  {truncateFilename(groupData.fileData.filename)}
                </span>
                {groupData.citationContents.length > 0 &&
                  <div className="text-neutral-500 text-[11px] italic mt-0.5 leading-tight">
                    &quot;{truncateFilename(groupData.citationContents[0])}&quot;
                    {groupData.citationContents.length > 1 && (
                      <span className="ml-1 text-[10px] text-gray-400">
                        (+{groupData.citationContents.length - 1} more)
                      </span>
                    )}
                  </div>
                }
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    );
  };

  const components: Components = useMemo(() => ({
    p: ({ children }) => <p className="my-1 leading-relaxed whitespace-pre-line">{children}</p>,
    h1: ({ children }) => <h1 className="text-xl font-bold mt-2 mb-1">{children}</h1>,
    h2: ({ children }) => <h2 className="text-lg font-bold mt-2 mb-1">{children}</h2>,
    h3: ({ children }) => <h3 className="text-md font-bold mt-1.5 mb-0.5">{children}</h3>,
    h4: ({ children }) => <h4 className="text-base font-semibold mt-1 mb-0.5">{children}</h4>,
    strong: ({ children }) => <strong className="font-bold">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-secondary-border pl-2 my-1 italic bg-secondary/50 py-0.5 rounded-r">
        {children}
      </blockquote>
    ),
    ul: ({ children }) => (
      <ul className="list-disc pl-4 my-0.5 space-y-0 !leading-tight">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal pl-4 my-0.5 space-y-0 !leading-tight">
        {children}
      </ol>
    ),
    li: ({ children }) => (
      <li className="my-0 !leading-tight">
        {children}
      </li>
    ),
    a: ({ href, children, ...props }) => (
      <a
        href={href ?? '#'}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 underline hover:text-blue-800"
        {...props}
      >
        {children}
      </a>
    ),
    hr: () => <hr className="border-secondary-border my-2" />,
    code: ({ inline, children, ...props }: CodeProps) =>
      inline ? (
        <code className="bg-secondary-hover rounded px-1 py-0.5 font-mono text-sm" {...props}>
          {children}
        </code>
      ) : (
        <pre className="bg-secondary-hover p-2 rounded-lg my-1 overflow-x-auto">
          <code className="font-mono text-sm" {...props}>{children}</code>
        </pre>
      ),
  }), []);

  const renderMessageContent = () => {
    if (isSystem && isThinking) {
      return (
        <div className="h-full flex items-center">
          <Thinking text={message.content || t('processing')} />
        </div>
      );
    }
    if (isThinking) {
      return (
        <div className="h-full flex items-center">
          <Thinking text={t('thinking')} />
        </div>
      );
    }
    if (isSystem && message.content?.includes('processing your request')) {
      return (
        <div className="h-full flex items-center">
          <Thinking text={t('processing_files')} />
        </div>
      );
    }
    if (isSystem && message.content?.includes('failed to process')) {
      return (
        <div className="text-red-600 font-medium">
          {message.content}
        </div>
      );
    }
    return (
      <>
        {isSystem ? (
          <p className="text-neutral-500 text-sm whitespace-pre-line">{formattedMessage}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert whitespace-pre-line break-words" style={{ maxWidth: '100%' }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              rehypePlugins={[rehypeHighlight]}
              components={components}
            >
              {formattedMessage}
            </ReactMarkdown>
          </div>
        )}
        {message.functionCall && (
          <p className="text-xs text-gray-500 mt-0.5">{message.functionCall}</p>
        )}
        {renderAttachments()}
      </>
    );
  };

  return (
    <div className="flex items-start px-2 py-2 font-medium">
      {isAssistant ? (
        <div className="rounded-md bg-secondary-hover text-sm w-7 h-7 min-w-7 min-h-7 flex items-center justify-center mr-3 text-stone-600 shadow-sm">
          <Bot className="size-4" />
        </div>
      ) : isSystem ? (
        <div className="rounded-md bg-secondary-hover text-sm w-7 h-7 min-w-7 min-h-7 flex items-center justify-center mr-3 text-stone-600 shadow-sm">
          <Bot className="size-4" />
        </div>
      ) : (
        <div className="rounded-md bg-secondary-hover text-sm w-7 h-7 min-w-7 min-h-7 flex items-center justify-center mr-3 text-stone-600 shadow-sm">
          {userInitial}
        </div>
      )}
      <div className="h-full flex-1">
        {renderMessageContent()}
      </div>

      {previewFile && (
        <FilePreview
          file={previewFile}
          onClose={handleClosePreview}
          loading={isLoadingPreview}
        />
      )}
    </div>
  );
};

export default ChatMessage;