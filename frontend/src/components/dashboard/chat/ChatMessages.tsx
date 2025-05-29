import React, { useEffect, useRef, useState } from 'react';
import ChatMessage from './ChatMessage';
import { Message } from '@/types';

interface ChatMessagesProps {
    messages: Message[];
    loading: boolean;
}

const ChatMessages: React.FC<ChatMessagesProps> = ({ messages, loading }) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [autoScroll, setAutoScroll] = useState(true);
    const prevMessagesLengthRef = useRef(messages.length);

    const scrollToBottom = () => {
        if (containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    };

    const handleScroll = () => {
        if (!containerRef.current) return;
        
        const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
        
        // Only consider it "at bottom" if we're within 50px of the bottom
        setAutoScroll(distanceFromBottom < 50);
    };

    useEffect(() => {
        // Only trigger auto-scroll in specific cases
        const shouldScrollToBottom = () => {
            // New message added
            const newMessageAdded = messages.length > prevMessagesLengthRef.current;
            // Last message is from user
            const lastMessageIsUser = messages.length > 0 && 
                messages[messages.length - 1].role === 'user';
            // Auto-scroll is enabled and there's a new message
            const autoScrollEnabled = autoScroll && newMessageAdded;
            
            return lastMessageIsUser || autoScrollEnabled;
        };

        if (shouldScrollToBottom()) {
            scrollToBottom();
        }

        prevMessagesLengthRef.current = messages.length;
    }, [messages, autoScroll]);

    // Remove duplicate messages
    const uniqueMessages = messages.filter((message, index, self) => 
        index === self.findIndex((m) => (
            m.content === message.content && 
            m.role === message.role &&
            m.created_at === message.created_at
        ))
    );

    return (
        <div 
            ref={containerRef}
            onScroll={handleScroll}
            className="flex flex-col gap-4 py-4 overflow-y-auto scrollbar-hide"
            style={{ 
                height: '100%',
                paddingBottom: '60px' // Add extra padding at bottom to ensure messages don't get hidden behind input
            }}
        >
            <div className="flex flex-col gap-4">
                {uniqueMessages.map((message, index) => (
                    <ChatMessage 
                        key={`${message.content}-${message.created_at}-${index}`} 
                        message={message} 
                    />
                ))}
                {loading && 
                    <ChatMessage 
                        message={{ content: '', role: 'assistant' }}
                        isThinking={true}
                    />
                }
            </div>
            <div ref={messagesEndRef} />
        </div>
    );
};

export default ChatMessages;