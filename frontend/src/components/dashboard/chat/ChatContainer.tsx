"use client";

import { ArrowUp, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRef, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import ChatMessages from "./ChatMessages";
import { useDashboard } from "@/context/DashboardContext";
import { useStreamingChat } from "@/hooks/useStreamingChat";
import styled from "styled-components";
import FileComponent from "../FileComponent";
import { SUPPORTED_EXTENSIONS } from "@/app/constants";
import { checkOrCreateConversation } from "@/utils/conversationActions";
import TokenLimitDialog from "../popup/TokenLimitPopup";
import { useTranslations } from 'next-intl';

const EmptyChat = () => {
  const t = useTranslations('dashboard.chat');
  
  return (
    <div className="flex-1 flex items-center text-center justify-center text-neutral-400">
      {t('start_conversation')}
    </div>
  );
};

const LoadingSpinner = ({ text }: { text: string }) => (
  <div className="flex flex-col items-center justify-center gap-3">
    <div className="w-8 h-8 border-4 border-neutral-100 border-t-black rounded-full animate-spin"></div>
    <p className="text-neutral-400">{text}</p>
  </div>
);

const InputContainer = styled.div`
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  padding: 1rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: transparent;
  z-index: 10;
`;

const GradientBackground = styled.div<{ $height: number }>`
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: ${props => props.$height + 16}px;
  background: rgba(245, 239, 228, 0.5);
  backdrop-filter: blur(8px);
  z-index: 5;
  
  mask-image: linear-gradient(
    to bottom,
    transparent,
    black 40%,
    black 100%,
    transparent
  );
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent,
    black 40%,
    black 100%,
    transparent
  );
`;

const StyledTextarea = styled.textarea`
  flex: 1;
  height: 40px;
  max-height: 120px;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  
  border: 1px solid var(--input-border, #e2e8f0);
  background-color: var(--secondary, #f8fafc);
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
  color: inherit;
  font-size: 1rem;
  
  outline: none;
  &:focus-visible {
    outline: none;
    ring: 2px;
    ring-color: var(--ring, #3b82f6);
    ring-offset: 2px;
  }
  
  resize: none;
  overflow-y: auto;
  font-family: inherit;
  line-height: 1.5;
  transition: height 0.1s ease-out;
  
  &::placeholder {
    color: var(--muted-foreground, #64748b);
  }
  
  &:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
`;

const ChatContainer = () => {
    const chatContainerRef = useRef<HTMLDivElement | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const inputContainerRef = useRef<HTMLDivElement | null>(null);
    
    const { 
      user, 
      currentAssistant, 
      currentConversation, 
      setCurrentConversation,
      conversationLoading,
      setConversationLoading
    } = useDashboard();
    
    const router = useRouter();
    const [isInitializing, setIsInitializing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [isAtBottom, setIsAtBottom] = useState(true);
    const [inputValue, setInputValue] = useState('');
    const [inputContainerHeight, setInputContainerHeight] = useState(0);
    const [textareaHeight, setTextareaHeight] = useState(40);

    // Translation hooks
    const t = useTranslations('dashboard.chat');
    const tCommon = useTranslations('common');
    const tErrors = useTranslations('errors.general');

    const {
        messages,
        isLoading,
        sendMessage,
        setMessages,
        tokenLimitError,
        setTokenLimitError
    } = useStreamingChat({
        assistantId: currentAssistant?._id || '',
        conversationId: currentConversation?._id || '',
    });

    useEffect(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = '40px';
        
        if (inputValue.trim()) {
          const scrollHeight = textareaRef.current.scrollHeight;
          const newHeight = Math.min(scrollHeight, 120);
          textareaRef.current.style.height = `${newHeight}px`;
          setTextareaHeight(newHeight);
        } else {
          textareaRef.current.style.height = '40px';
          setTextareaHeight(40);
        }
      }
    }, [inputValue]);

    const isFileSupported = (file: File) => {
        const extension = file.name.split('.').pop()?.toLowerCase();
        if (!extension) return false;
        return extension in SUPPORTED_EXTENSIONS;
    };

    const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files || []);
        const supportedFiles = files.filter(file => isFileSupported(file));
        const unsupportedFiles = files.filter(file => !isFileSupported(file));
        
        if (unsupportedFiles.length > 0) {
            const extensions = Object.keys(SUPPORTED_EXTENSIONS).join(', ');
            setError(`Unsupported file type(s). Supported extensions: ${extensions}`);
            setTimeout(() => setError(null), 5000);
        }

        setSelectedFiles(prevFiles => [...prevFiles, ...supportedFiles]);
    };

    useEffect(() => {
        const updateHeight = () => {
            if (inputContainerRef.current) {
                const height = inputContainerRef.current.offsetHeight;
                setInputContainerHeight(height);
            }
        };

        updateHeight();
        
        const resizeObserver = new ResizeObserver(() => {
            window.requestAnimationFrame(updateHeight);
        });
        
        if (inputContainerRef.current) {
            resizeObserver.observe(inputContainerRef.current);
        }

        const timeoutId = setTimeout(updateHeight, 100);

        return () => {
            resizeObserver.disconnect();
            clearTimeout(timeoutId);
        };
    }, [textareaHeight]);

    useEffect(() => {
        if (inputContainerRef.current) {
            const height = inputContainerRef.current.offsetHeight;
            setInputContainerHeight(height);
        }
    }, [selectedFiles]);

    useEffect(() => {
        let isActive = true;

        const initializeConversation = async () => {
            if (!currentAssistant?._id || !user?._id) return;
            if (currentConversation && currentConversation.assistant_id === currentAssistant._id) {
                setConversationLoading(false);
                return;
            }
            
            setIsInitializing(true);
            setConversationLoading(true);
            setError(null);
            
            try {
                const newConversation = await checkOrCreateConversation(
                    user._id,
                    currentAssistant._id
                );
                
                if (isActive && currentAssistant._id === newConversation.assistant_id) {
                    setCurrentConversation(newConversation);
                    setMessages([]);
                }
            } catch (err) {
                if (isActive) {
                    console.error('Failed to create conversation:', err);
                    setError(t('conversation_initialization_failed'));
                }
            } finally {
                if (isActive) {
                    setIsInitializing(false);
                    setConversationLoading(false);
                }
            }
        };

        initializeConversation();

        return () => {
            isActive = false;
        };
    }, [currentAssistant?._id, user?._id, t]);

    useEffect(() => {
        if (currentConversation?.messages) {
            const conversationMessages = [...currentConversation.messages].reverse();
            setMessages(conversationMessages);
        }
    }, [currentConversation?.messages, setMessages]);

    useEffect(() => {
        if (currentConversation?._id) {
            router.push(`/dashboard/tenders/chat/${currentConversation._id}`, { scroll: false });
        }
    }, [currentConversation?._id, router]);

    useEffect(() => {
        if (isAtBottom && chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [messages, isAtBottom]);

    const handleRemoveFile = (index: number) => {
        setSelectedFiles(prevFiles => prevFiles.filter((_, i) => i !== index));
    };

    const handleClickUpload = () => {
        fileInputRef.current?.click();
    };

    const handleSendMessage = async () => {
        const trimmedMessage = inputValue.trim();
        
        if (!trimmedMessage || !currentAssistant || !currentConversation) {
            return;
        }
        
        const message = trimmedMessage;
        const filesToSend = [...selectedFiles];
        
        setInputValue('');
        setSelectedFiles([]);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }

        if (textareaRef.current) {
            textareaRef.current.style.height = '40px';
            setTextareaHeight(40);
        }

        await sendMessage(message, { files: filesToSend });

        if (isAtBottom && chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (inputValue.trim()) {
                handleSendMessage();
            }
        }
    };

    const handleScroll = () => {
        if (!chatContainerRef.current) return;
        const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
        const isUserAtBottom = scrollHeight - scrollTop <= clientHeight + 100;
        setIsAtBottom(isUserAtBottom);
    };

    if (!currentAssistant || !user) {
        return (
            <div className="flex-1 h-full w-full flex items-center justify-center">
                <p className="text-neutral-400">{t('select_project_to_start')}</p>
            </div>
        );
    }

    if (isInitializing) {
        return (
            <div className="flex-1 h-full w-full flex items-center justify-center">
                <LoadingSpinner text={t('initializing_conversation')} />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex-1 h-full w-full flex flex-col items-center justify-center gap-4">
                <p className="text-red-500">{error}</p>
                <Button 
                    variant="outline" 
                    onClick={() => window.location.reload()}
                >
                    {tCommon('try_again')}
                </Button>
            </div>
        );
    }

    return (
        <div className="flex-1 h-full flex flex-col overflow-hidden">
            <TokenLimitDialog setTokenLimitError={setTokenLimitError} tokenLimitError={tokenLimitError} />
            <div className="flex-1 w-full h-full flex flex-col items-center">
                <div className="w-full max-w-3xl h-full flex-1 flex flex-col px-6 relative">
                    <div 
                        className="flex-1 flex flex-col overflow-y-auto h-[100svh]"
                        ref={chatContainerRef}
                        onScroll={handleScroll}
                    >
                        {conversationLoading ? (
                            <div className="flex-1 flex items-center justify-center">
                                <LoadingSpinner text={t('loading_conversation')} />
                            </div>
                        ) : messages.length === 0 ? (
                            <EmptyChat />
                        ) : (
                            <ChatMessages 
                                messages={messages} 
                                loading={isLoading} 
                            />
                        )}
                    </div>
                    <GradientBackground $height={inputContainerHeight} />
                    <InputContainer ref={inputContainerRef}>
                        {selectedFiles.length > 0 && (
                            <div className="flex flex-wrap gap-2 w-full rounded-lg">
                                {selectedFiles.map((file, index) => (
                                    <FileComponent
                                        key={index}
                                        file={file}
                                        onRemove={() => handleRemoveFile(index)}
                                    />
                                ))}
                            </div>
                        )}
                        <div className="flex items-end gap-4 w-full">
                            <input
                                type="file"
                                ref={fileInputRef}
                                className="hidden"
                                onChange={handleFileUpload}
                                multiple
                                accept={Object.entries(SUPPORTED_EXTENSIONS)
                                    .map(([ext]) => `.${ext}`)
                                    .join(',')}
                            />
                            <Button
                                variant="outline"
                                size="icon"
                                className="w-10 h-10 border-2 border-secondary-border rounded-md"
                                onClick={handleClickUpload}
                            >
                                <Paperclip className="w-5 h-5" />
                            </Button>
                            <StyledTextarea
                                ref={textareaRef}
                                placeholder={selectedFiles.length > 0 ? t('type_message_to_send_file') : t('type_message')}
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={handleKeyPress}
                                disabled={isLoading}
                                style={{ height: `${textareaHeight}px` }}
                            />
                            <Button 
                                size="icon" 
                                className="w-10 h-10 rounded-md"
                                onClick={handleSendMessage}
                                disabled={isLoading || !inputValue.trim()}
                            >
                                <ArrowUp className="w-5 h-5" />
                            </Button>
                        </div>
                    </InputContainer>
                </div>
            </div>
        </div>
    );
};

export default ChatContainer;