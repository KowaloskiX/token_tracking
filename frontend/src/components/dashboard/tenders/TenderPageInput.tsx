"use client";

import { useState } from "react";

interface TenderPageInputProps {
  totalPages: number;
  onPageJump: (page: number) => void;
  className?: string;
}

const TenderPageInput: React.FC<TenderPageInputProps> = ({ 
  totalPages, 
  onPageJump, 
  className = "" 
}) => {
  const [inputValue, setInputValue] = useState("");
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const pageNum = parseInt(inputValue);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      onPageJump(pageNum);
      setInputValue("");
      setIsFocused(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setInputValue("");
      setIsFocused(false);
      (e.target as HTMLInputElement).blur();
    }
  };

  const handleBlur = () => {
    if (!inputValue) {
      setIsFocused(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={`inline-flex ${className}`}>
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        placeholder="..."
        className={`text-center text-sm border rounded-md transition-all duration-200 ${
          isFocused || inputValue
            ? 'w-12 border-primary focus:outline-none focus:ring-2 focus:ring-primary/20'
            : 'w-8 border-transparent bg-transparent cursor-pointer hover:bg-muted'
        } h-8`}
        style={{
          appearance: 'textfield',
        }}
        title={`Jump to page (1-${totalPages})`}
      />
    </form>
  );
};

export default TenderPageInput;