"use client";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface TenderSearchProps {
  onSearch: (query: string) => void;
  placeholder?: string;
  which?: string;
}

export default function TenderSearch({ onSearch, placeholder, which="text" }: TenderSearchProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const handleSearchInput = (value: string) => {
    setSearchTerm(value);
    onSearch(value);
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-4">
      {/* Text input field */}
      <Input
        type={which}
        className="w-full mt-2 ml-2 sm:w-64 px-4 py-2 rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
        placeholder={placeholder}
        value={searchTerm}
        onChange={(e) => handleSearchInput(e.target.value)}
      />
    </div>
  );
}
