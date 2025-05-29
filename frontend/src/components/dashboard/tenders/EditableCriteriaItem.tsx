import React, { useEffect, useRef, useState } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from '@/components/ui/textarea';
import { Pencil } from 'lucide-react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

interface EditableCriteriaItemProps {
    resultId: string;
    criteriaItem: any; 
    onUpdate?: (newSummary: string) => void;
    markdownComponents?: Components;
}

const EditableCriteriaItem: React.FC<EditableCriteriaItemProps> = ({ 
    resultId, 
    criteriaItem, 
    onUpdate,
    markdownComponents 
}) => {
    const [isEditing, setIsEditing] = useState(false);
    const [summaryText, setSummaryText] = useState(criteriaItem.analysis.summary);
    const [isSaving, setIsSaving] = useState(false);

    const textAreaRef = useRef<HTMLTextAreaElement | null>(null);

    useEffect(() => {
        setSummaryText(criteriaItem.analysis.summary);
    }, [criteriaItem.analysis.summary]);

    useEffect(() => {
        if (isEditing && textAreaRef.current) {
        textAreaRef.current.style.height = "auto"
        textAreaRef.current.style.height = `${textAreaRef.current.scrollHeight}px`
        }
    }, [summaryText, isEditing])

    const handleSave = async () => {
        setIsSaving(true);
        try {
            const token = localStorage.getItem("token");
            if (!token) {
                throw new Error("Authentication token not found.");
            }
            const response = await fetch(
                `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/tender-results/${resultId}/edit-criteria/${encodeURIComponent(criteriaItem.criteria)}`,
                {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify({ summary: summaryText })
                }
            );
            
            if (!response.ok) {
                throw new Error("Failed to update criteria");
            }
            
            setIsEditing(false);
            if (onUpdate) {
                onUpdate(summaryText);
            }
        } catch (error) {
            console.error("Error updating criteria:", error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleCancel = () => {
        setSummaryText(criteriaItem.analysis.summary);
        setIsEditing(false);
    };

    // Default markdown components if none provided
    const defaultComponents: Components = {
        p: ({ children }) => <p className="text-sm text-gray-600 w-full my-1 leading-normal">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-4 my-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-4 my-1">{children}</ol>,
        li: ({ children }) => <li className="mb-2 relative">{children}</li>,
    };

    return (
        <div className="flex flex-col w-full">
          {isEditing ? (
            <>
              <Textarea
                    ref={textAreaRef}
                    className="border w-full p-2 rounded focus:outline-none resize-none overflow-hidden"
                    value={summaryText}
                    onChange={(e) => setSummaryText(e.target.value)}
                    rows={1}
                />
              <div className="mt-2 flex gap-2 justify-end">
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Zapisywanie..." : "Zapisz"}
                </Button>
                <Button variant="outline" onClick={handleCancel}>
                  Anuluj
                </Button>
              </div>
            </>
          ) : (
            <div className="flex flex-wrap items-end justify-end">
              <div className="w-full flex-grow markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={markdownComponents || defaultComponents}
                >
                  {summaryText}
                </ReactMarkdown>
              </div>
              <Button className='bg-transparent border-none p-0 hover:bg-transparent hover:text-primary/50' variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                <Pencil />
              </Button>
            </div>
          )}
        </div>
    );
      
      
}; export default EditableCriteriaItem;