import { useState, useCallback, useRef, useEffect } from 'react';
import { Message, Attachment } from '@/types';
const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

interface TokenLimitError {
  message: string;
  current_usage: number;
  limit: number;
  next_reset: string;
}

interface UseStreamingChatProps {
  assistantId: string;
  conversationId: string;
}

interface SendMessageOptions {
  files?: File[];
  onCompletionMetrics?: (metrics: {
    completion_tokens: number;
    prompt_tokens: number;
    total_tokens: number;
  }) => void;
}

export const useStreamingChat = ({ assistantId, conversationId }: UseStreamingChatProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [tokenLimitError, setTokenLimitError] = useState<TokenLimitError | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isFirstChunkRef = useRef(true);
  const filenameIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const accumulatedFilenamesRef = useRef<{ filename: string; file_id: string }[]>([]);
  const expectedFilenameCountRef = useRef<number>(0);

  useEffect(() => {
    return () => {
      if (filenameIntervalRef.current) {
        clearInterval(filenameIntervalRef.current);
        filenameIntervalRef.current = null;
        console.log("Cleaned up filename interval on unmount/re-render");
      }
    };
  }, []);

  const clearFilenameInterval = useCallback(() => {
    if (filenameIntervalRef.current) {
      clearInterval(filenameIntervalRef.current);
      filenameIntervalRef.current = null;
       console.log("Cleared filename interval manually");
    }
  }, []);

  const sendMessage = useCallback(
    async (prompt: string, options: SendMessageOptions = {}) => {
      clearFilenameInterval();
      accumulatedFilenamesRef.current = [];
      expectedFilenameCountRef.current = 0;
      setIsLoading(true);
      setTokenLimitError(null);
      isFirstChunkRef.current = true;

      setMessages(prev => prev.filter(msg => msg.role !== 'system'));

      const userMessage: Message = {
        content: prompt,
        role: 'user',
        attachments: options.files ? options.files.map(file => ({ name: file.name })) : undefined
      };

      setMessages(prev => [...prev, userMessage]);

      try {
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        const token = localStorage.getItem('token');

        const body = JSON.stringify(
          {
           conversation_id: conversationId,
           assistant_id: assistantId,
           query: prompt,
          } 
         )
         
        const response = await fetch(`${serverUrl}/send-project-message`, {
          method: 'POST',
          body: body,
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          signal: abortControllerRef.current.signal
        });

        if (!response.ok) {
          if (response.status === 429) {
            const errorData = await response.json();
            setTokenLimitError(errorData.detail);
            setIsLoading(false);
            return;
          }
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        setMessages(prev => [...prev, { content: '', role: 'assistant', attachments: [] }]);

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No reader available');

        if (isFirstChunkRef.current) {
          isFirstChunkRef.current = false;
          setIsLoading(false);
        }

        let was_deep_search = false; // used to control switching from system progress to assistant
        let incompleteLineBuffer = '';

        const processSSELine = (line: string) => {
          if (!line.startsWith('data: ')) return;
          try {
            const jsonText = line.slice(6).trim();
            const data = JSON.parse(jsonText);

            switch (data.type) {
              case 'file_citation':
                console.log('File citation received:', data);
                setMessages((prev: Message[]) => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    const newAttachments = data.citations.map((cite: any) => ({
                      name: cite.filename,
                      citation: cite.content,
                      file_id: cite.file_id
                    }));

                    const mergeByKey = (arr: any[], keyFn: (item: any) => string) => {
                      const map = new Map<string, any>();
                      arr.forEach(item => map.set(keyFn(item), item));
                      return Array.from(map.values());
                    };

                    const currentAttachments = lastMessage.attachments || [];
                    const currentCitations = lastMessage.citations || [];

                    lastMessage.attachments = mergeByKey([...currentAttachments, ...newAttachments], a => `${a.file_id ?? ''}-${a.citation ?? ''}`);
                    lastMessage.citations = mergeByKey([...currentCitations, ...data.citations], c => `${c.file_id ?? ''}-${c.content ?? ''}`);
                  }
                  return newMessages;
                });
                break;

              case 'text':
                if (was_deep_search) {
                  setMessages((prev: Message[]) => {
                    if (prev.length === 0) return prev;
                    const lastMessage = prev[prev.length - 1];
                    if (lastMessage.role === 'system') {
                      return prev.slice(0, -1);
                    }
                    return prev;
                  });
                  setMessages(prev => [...prev, { content: '', role: 'assistant' }]);
                  was_deep_search = false;
                }
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    lastMessage.content = (lastMessage.content || '') + data.content;
                    console.log(data.content);
                  }
                  return newMessages;
                });
                break;

              case 'status': {
                was_deep_search = true;
                const statusText: string = data.message ?? '';

                setMessages((prev: Message[]) => {
                  const newMessages = [...prev];

                  // Remove empty placeholder assistant message if present
                  if (newMessages.length > 0) {
                    const last = newMessages[newMessages.length - 1];
                    if (last.role === 'assistant' && last.content === '') {
                      newMessages.pop();
                    }
                  }

                  // If last message is already a system status, update it
                  if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'system') {
                    newMessages[newMessages.length - 1].content = statusText;
                  } else {
                    newMessages.push({ content: statusText, role: 'system' });
                  }
                  return newMessages;
                });

                break;
              }

              case 'function_call':
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    lastMessage.content = (lastMessage.content || '') + `\nFunction call: ${data.name}(${JSON.stringify(data.arguments)})`;
                  }
                  return newMessages;
                });
                break;

              case 'final_filenames_start':
                expectedFilenameCountRef.current = data.total_filenames || 0;
                accumulatedFilenamesRef.current = [];
                console.log(`Starting filename stream. Expecting ${expectedFilenameCountRef.current} filenames.`);
                break;

              case 'filename_item':
                if (data.filename && typeof data.filename === 'string') {
                  accumulatedFilenamesRef.current.push({ filename: data.filename, file_id: data.file_id });
                  console.debug(`Accumulated filename ${accumulatedFilenamesRef.current.length}/${expectedFilenameCountRef.current}: ${data.filename}`);
                } else {
                  console.warn('Received filename_item without valid filename data:', data);
                }
                break;

              case 'filename_item_error':
                console.error(`Server reported error processing filename index ${data.index} ('${data.filename}'): ${data.error}`);
                break;

              case 'final_filenames_end':
                console.log(`Filename stream ended. Received ${accumulatedFilenamesRef.current.length}/${expectedFilenameCountRef.current} filenames.`);
                if (accumulatedFilenamesRef.current.length !== expectedFilenameCountRef.current) {
                  console.warn('Mismatch in expected vs received filenames.');
                }
                if (accumulatedFilenamesRef.current.length > 0) {
                  setMessages(prev => {
                    const newMessages = [...prev];
                    let targetMessageIndex = -1;
                    for(let i = newMessages.length - 1; i >= 0; i--) {
                        if(newMessages[i].role === 'assistant') {
                            targetMessageIndex = i;
                            break;
                        }
                    }

                    if (targetMessageIndex !== -1) {
                      const attachments = accumulatedFilenamesRef.current.map(f => ({
                        name: f.filename,
                        file_id: f.file_id
                      }));
                      const citations = accumulatedFilenamesRef.current.map(f => ({
                        filename: f.filename,
                        file_id: f.file_id,
                      }));
                      newMessages[targetMessageIndex] = {
                        ...newMessages[targetMessageIndex],
                        attachments: [...(newMessages[targetMessageIndex].attachments || []), ...attachments],
                        citations: [...(newMessages[targetMessageIndex].citations || []), ...citations],
                      };
                      console.log(`Immediately added ${attachments.length} attachments/citations to state.`);
                    } else {
                        console.warn("Couldn't find assistant message for immediate attachment update.");
                    }
                    return newMessages;
                  });

                  clearFilenameInterval();
                  let filenameIndex = 0;
                  const filenamesToAnimate = [...accumulatedFilenamesRef.current];

                  filenameIntervalRef.current = setInterval(() => {
                      if (filenameIndex >= filenamesToAnimate.length) {
                          clearFilenameInterval();
                          return;
                      }

                      const nextFile = filenamesToAnimate[filenameIndex];
                      const attachment: Attachment = { name: nextFile.filename, file_id: nextFile.file_id };
                      const citation = { filename: nextFile.filename, file_id: nextFile.file_id, content: '' };

                      setMessages(prev => {
                          const newMessages = [...prev];
                          let targetMessageIndex = -1;
                          for(let i = newMessages.length - 1; i >= 0; i--) {
                              if(newMessages[i].role === 'assistant') {
                                  targetMessageIndex = i;
                                  break;
                              }
                          }

                          if (targetMessageIndex !== -1) {
                              const currentMessage = newMessages[targetMessageIndex];
                              const updatedMessage = {
                                ...currentMessage,
                              };
                              newMessages[targetMessageIndex] = updatedMessage;
                              console.log(`Animating filename (visual effect) ${filenameIndex + 1}/${filenamesToAnimate.length}: ${nextFile.filename}`);
                          } else {
                              console.warn("Couldn't find assistant message for filename animation step.");
                              clearFilenameInterval();
                          }
                          return newMessages;
                      });
                      filenameIndex++;
                  }, 150);
                }
                accumulatedFilenamesRef.current = [];
                expectedFilenameCountRef.current = 0;
                break;

              case 'message_id':
                setMessages(prev => {
                  const newMessages = [...prev];
                  for (let i = newMessages.length - 1; i >= 0; i--) {
                    if (newMessages[i].role === 'assistant' && !newMessages[i].id) {
                      console.log(`Assigning id ${data.id} to message at index ${i}`);
                      newMessages[i].id = data.id;
                      break;
                    }
                  }
                  return newMessages;
                });
                break;

              case 'error':
                console.error('Stream error from server:', data.message);
                setIsLoading(false);
                clearFilenameInterval();
                accumulatedFilenamesRef.current = [];
                expectedFilenameCountRef.current = 0;
                setMessages(prev => [...prev, { content: `Error: ${data.message}`, role: 'system' }]);
                break;

              default:
                console.warn('Unhandled stream event type:', data.type, data);
                break;
            }
          } catch (e) {
            console.error('Error processing stream line:', e, 'Line:', line);
            clearFilenameInterval();
            accumulatedFilenamesRef.current = [];
            expectedFilenameCountRef.current = 0;
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
              // Process any leftover buffered line when the stream ends
              if (incompleteLineBuffer.trim() !== '') {
                processSSELine(incompleteLineBuffer);
                incompleteLineBuffer = '';
              }

              if (expectedFilenameCountRef.current > 0 && accumulatedFilenamesRef.current.length !== expectedFilenameCountRef.current) {
                  console.warn(`Stream ended but received ${accumulatedFilenamesRef.current.length}/${expectedFilenameCountRef.current} filenames. Starting animation with received items.`);
                   if (accumulatedFilenamesRef.current.length > 0) {
                       clearFilenameInterval();
                       let filenameIndex = 0;
                       const filenamesToAnimate = [...accumulatedFilenamesRef.current];
                       filenameIntervalRef.current = setInterval(() => {
                           if (filenameIndex >= filenamesToAnimate.length) {
                               clearFilenameInterval(); return;
                           }
                           const nextFile = filenamesToAnimate[filenameIndex];
                           const attachment: Attachment = { name: nextFile.filename, file_id: nextFile.file_id };
                           const citation = { filename: nextFile.filename, file_id: nextFile.file_id, content: '' };
                           setMessages(prev => {
                               const newMessages = [...prev];
                               let targetMessageIndex = -1;
                               for(let i = newMessages.length - 1; i >= 0; i--) { if(newMessages[i].role === 'assistant') { targetMessageIndex = i; break; }}
                               if (targetMessageIndex !== -1) {
                                   const targetMessage = newMessages[targetMessageIndex];
                                   targetMessage.attachments = [...(targetMessage.attachments || []), attachment];
                                   targetMessage.citations = [...(targetMessage.citations || []), citation];
                               } else { clearFilenameInterval(); }
                               return newMessages;
                           });
                           filenameIndex++;
                       }, 150);
                   }
              }
              break;
          }

          const chunk = new TextDecoder().decode(value);
          incompleteLineBuffer += chunk;
          const lines = incompleteLineBuffer.split('\n');
          // Keep the last line (it might be incomplete) in the buffer for the next iteration
          incompleteLineBuffer = lines.pop() || '';

          for (const line of lines) {
            processSSELine(line);
          }
        }
      } catch (error) {
        console.error('Error sending message:', error);
        setIsLoading(false);
        setMessages(prev => [
          ...prev,
          { content: 'An error occurred while sending your message.', role: 'assistant' }
        ]);
      } finally {
        abortControllerRef.current = null;
        isFirstChunkRef.current = true;
      }
    },
    [assistantId, conversationId, clearFilenameInterval]
  );

  return {
    messages,
    isLoading,
    sendMessage,
    setMessages,
    tokenLimitError,
    setTokenLimitError
  };
};
