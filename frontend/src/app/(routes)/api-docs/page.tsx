"use client";

import React, { useState } from "react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
    Copy,
    Key,
    FileText,
    Search,
    Download,
    BookOpen,        // NEW – nicer icon
} from "lucide-react";
// import Navbar from "@/components/landing/Navbar";  // REMOVED
import Footer from "@/components/landing/Footer";
import { useToast } from "@/hooks/use-toast";
import { Toaster } from "@/components/ui/toaster";
import SyntaxHighlighter from "react-syntax-highlighter";               // NEW – colour-coded code blocks
import { atomOneDark } from "react-syntax-highlighter/dist/cjs/styles/hljs"; // NEW

const ApiDocsPage = () => {
    const [selectedEndpoint, setSelectedEndpoint] = useState("results");
    const { toast } = useToast();

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        toast({
            title: "Skopiowano!",
            description: "Kod został skopiowany do schowka.",
        });
    };

    /* ------------------------------------------------------------------ */
    /* Endpoints metadata                                                 */
    /* ------------------------------------------------------------------ */

    const endpoints = [
        {
            id: "results",
            method: "POST",
            path: "/api/results",
            title: "Pobierz wyniki analizy",
            description:
                "Pobiera listę wyników analizy przetargów dla określonej analizy.",
            icon: <Search className="w-4 h-4" />,
            requestBodyExample: `{
  "analysis_id": "64f5a8b9c1d2e3f4a5b6c7d8",
  "date_from": "2025-01-01",
  "date_to": "2025-06-01",
  "limit": 100,
  "offset": 0,
  "include_historical": true
}`, // NEW – "example input to be placed in the body"
            response: {
                results: "Array<TenderResult>",
                total: "number",
                has_more: "boolean",
            },
        },
        {
            id: "criteria",
            method: "GET",
            path: "/api/results/{result_id}/criteria",
            title: "Pobierz kryteria wyniku",
            description:
                "Pobiera szczegółową analizę kryteriów dla konkretnego wyniku przetargu.",
            icon: <FileText className="w-4 h-4" />,
            response: {
                result_id: "string",
                criteria_analysis: "Array<CriteriaItem>",
                tender_score: "number",
                created_at: "string",
            },
        },
        {
            id: "files",
            method: "GET",
            path: "/api/results/{result_id}/files",
            title: "Pobierz pliki wyniku",
            description:
                "Pobiera informacje o plikach związanych z konkretnym wynikiem przetargu.",
            icon: <Download className="w-4 h-4" />,
            queryParams: {
                include_preview: "boolean (opcjonalne)",
            },
            response: {
                result_id: "string",
                files: "Array<FileInfo>",
                total_files: "number",
            },
        },
    ];

    /* ------------------------------------------------------------------ */
    /* Helpers to build code examples                                     */
    /* ------------------------------------------------------------------ */

    const baseUrl =
        process.env.NEXT_PUBLIC_BACKEND_API_URL || "https://api.asystent.ai";

    const generateCodeExample = (endpoint: any) => {
        if (endpoint.method === "POST") {
            return `const response = await fetch("${baseUrl}${endpoint.path}", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "ak_xxxxxxxxxxxxx"
  },
  body: JSON.stringify(${endpoint.requestBodyExample})
});

const data = await response.json();
console.log(data);`;
        } else {
            let url = endpoint.path.replace(
                "{result_id}",
                "64f5a8b9c1d2e3f4a5b6c7d8"
            );
            if (endpoint.queryParams) {
                url += "?include_preview=true";
            }
            return `const response = await fetch("${baseUrl}${url}", {
  method: "${endpoint.method}",
  headers: {
    "X-API-Key": "ak_xxxxxxxxxxxxx"
  }
});

const data = await response.json();
console.log(data);`;
        }
    };

    const generateCurlExample = (endpoint: any) => {
        if (endpoint.method === "POST") {
            return `curl -X POST "${baseUrl}${endpoint.path}" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ak_xxxxxxxxxxxxx" \\
  -d '${endpoint.requestBodyExample}'`;
        } else {
            let url = endpoint.path.replace(
                "{result_id}",
                "64f5a8b9c1d2e3f4a5b6c7d8"
            );
            if (endpoint.queryParams) {
                url += "?include_preview=true";
            }
            return `curl -X ${endpoint.method} "${baseUrl}${url}" \\
  -H "X-API-Key: ak_xxxxxxxxxxxxx"`;
        }
    };

    /* ------------------------------------------------------------------ */
    /* Render                                                             */
    /* ------------------------------------------------------------------ */

    return (
        <div className="min-h-screen bg-background">
            {/* <Navbar />   REMOVED */}

            {/* Hero */}
            <div className="pt-24 pb-12 bg-background/90 backdrop-blur-sm">
                <div className="mx-auto max-w-7xl px-6 lg:px-8">
                    <div className="mx-auto max-w-3xl text-center">
                        <div className="flex items-center justify-center mb-4">
                            <BookOpen className="w-8 h-8 text-primary mr-3" /> {/* NEW icon */}
                            <h1 className="text-4xl tracking-tight text-foreground sm:text-5xl">
                                Dokumentacja API
                            </h1>
                        </div>
                        <p className="mt-6 text-lg text-body-text">
                            Integruj Asystenta AI z Twoją aplikacją. Uzyskaj dostęp do wyników
                            analizy przetargów poprzez nasze REST API.
                        </p>
                    </div>
                </div>
            </div>

            {/* Main grid */}
            <div className="mx-auto max-w-7xl px-6 lg:px-8 pb-24">
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                    {/* Sidebar navigation */}
                    <div className="lg:col-span-1">
                        <Card className="sticky top-24">
                            <CardHeader>
                                <CardTitle className="text-lg">Endpoints</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {endpoints.map((endpoint) => (
                                    <Button
                                        key={endpoint.id}
                                        variant={
                                            selectedEndpoint === endpoint.id ? "default" : "ghost"
                                        }
                                        className="w-full justify-start"
                                        onClick={() => setSelectedEndpoint(endpoint.id)}
                                    >
                                        {endpoint.icon}
                                        <span className="ml-2 text-sm">{endpoint.title}</span>
                                    </Button>
                                ))}

                                {/* Twój klucz API section REMOVED */}

                                <Separator className="my-4" />
                            </CardContent>
                        </Card>
                    </div>

                    {/* Main content */}
                    <div className="lg:col-span-3 space-y-8">
                        {/* Authentication */}
                        <Card>
                            <CardHeader>
                                <div className="flex items-center">
                                    <Key className="w-5 h-5 text-primary mr-2" />
                                    <CardTitle>Autoryzacja</CardTitle>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <p className="text-body-text">
                                    Wszystkie zapytania do API wymagają klucza. Przekaż go w
                                    nagłówku{" "}
                                    <code className="bg-secondary px-2 py-1 rounded">
                                        X-API-Key
                                    </code>
                                    .
                                </p>

                                <div className="bg-secondary p-4 rounded-lg">
                                    <code className="text-sm">X-API-Key: ak_xxxxxxxxxxxxx</code>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Endpoint docs */}
                        {endpoints.map(
                            (endpoint) =>
                                selectedEndpoint === endpoint.id && (
                                    <Card key={endpoint.id}>
                                        <CardHeader>
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center">
                                                    {endpoint.icon}
                                                    <CardTitle className="ml-2">
                                                        {endpoint.title}
                                                    </CardTitle>
                                                </div>
                                                <div className="flex items-center space-x-2">
                                                    {/* all methods share same colour now -------------- NEW */}
                                                    <Badge variant="default">{endpoint.method}</Badge>
                                                    <code className="bg-secondary px-2 py-1 rounded text-sm">
                                                        {endpoint.path}
                                                    </code>
                                                </div>
                                            </div>
                                            <CardDescription>{endpoint.description}</CardDescription>
                                        </CardHeader>

                                        <CardContent>
                                            <Tabs defaultValue="overview" className="w-full">
                                                <TabsList className="grid w-full grid-cols-4">
                                                    <TabsTrigger value="overview">Przegląd</TabsTrigger>
                                                    <TabsTrigger value="request">Request</TabsTrigger>
                                                    <TabsTrigger value="response">Response</TabsTrigger>
                                                    <TabsTrigger value="examples">Przykłady</TabsTrigger>
                                                </TabsList>

                                                {/* ----------------------------- OVERVIEW */}
                                                <TabsContent value="overview" className="space-y-4">
                                                    <div>
                                                        <h4 className="font-medium mb-2">Opis</h4>
                                                        <p className="text-body-text">
                                                            {endpoint.description}
                                                        </p>
                                                    </div>

                                                    <div>
                                                        <h4 className="font-medium mb-2">Endpoint</h4>
                                                        <div className="flex items-center space-x-2">
                                                            <Badge variant="default">
                                                                {endpoint.method}
                                                            </Badge>
                                                            <code className="bg-secondary px-2 py-1 rounded">
                                                                {endpoint.path}
                                                            </code>
                                                        </div>
                                                    </div>
                                                </TabsContent>

                                                {/* ----------------------------- REQUEST */}
                                                <TabsContent value="request" className="space-y-4">
                                                    {endpoint.requestBodyExample && (
                                                        <div>
                                                            <h4 className="font-medium mb-3">Request Body</h4>
                                                            <div className="bg-neutral-900 p-4 rounded-lg">
                                                                {/* blackish background -------------------- NEW */}
                                                                <SyntaxHighlighter
                                                                    language="json"
                                                                    style={atomOneDark}
                                                                    customStyle={{
                                                                        background: "transparent",
                                                                        fontSize: "0.8rem",
                                                                    }}
                                                                >
                                                                    {endpoint.requestBodyExample}
                                                                </SyntaxHighlighter>
                                                            </div>
                                                        </div>
                                                    )}

                                                    {endpoint.queryParams && (
                                                        <div>
                                                            <h4 className="font-medium mb-3">
                                                                Query Parameters
                                                            </h4>
                                                            <div className="bg-neutral-900 p-4 rounded-lg">
                                                                <SyntaxHighlighter
                                                                    language="json"
                                                                    style={atomOneDark}
                                                                    customStyle={{
                                                                        background: "transparent",
                                                                        fontSize: "0.8rem",
                                                                    }}
                                                                >
                                                                    {JSON.stringify(
                                                                        endpoint.queryParams,
                                                                        null,
                                                                        2
                                                                    )}
                                                                </SyntaxHighlighter>
                                                            </div>
                                                        </div>
                                                    )}

                                                    <div>
                                                        <h4 className="font-medium mb-3">Headers</h4>
                                                        <div className="bg-neutral-900 p-4 rounded-lg">
                                                            <SyntaxHighlighter
                                                                language="json"
                                                                style={atomOneDark}
                                                                customStyle={{
                                                                    background: "transparent",
                                                                    fontSize: "0.8rem",
                                                                }}
                                                            >
                                                                {`{
  "Content-Type": "application/json",
  "X-API-Key": "ak_xxxxxxxxxxxxx"
}`}
                                                            </SyntaxHighlighter>
                                                        </div>
                                                    </div>
                                                </TabsContent>

                                                {/* ----------------------------- RESPONSE */}
                                                <TabsContent value="response" className="space-y-4">
                                                    <div>
                                                        <h4 className="font-medium mb-3">
                                                            Response Format
                                                        </h4>
                                                        <div className="bg-neutral-900 p-4 rounded-lg">
                                                            <SyntaxHighlighter
                                                                language="json"
                                                                style={atomOneDark}
                                                                customStyle={{
                                                                    background: "transparent",
                                                                    fontSize: "0.8rem",
                                                                }}
                                                            >
                                                                {JSON.stringify(endpoint.response, null, 2)}
                                                            </SyntaxHighlighter>
                                                        </div>
                                                    </div>

                                                    <div>
                                                        <h4 className="font-medium mb-3">
                                                            Status Codes
                                                        </h4>
                                                        <div className="space-y-2">
                                                            <div className="flex items-center space-x-2">
                                                                {/* Green 200 -------------------------------- NEW */}
                                                                <Badge className="bg-green-600 text-white">
                                                                    200
                                                                </Badge>
                                                                <span className="text-sm">Sukces</span>
                                                            </div>
                                                            <div className="flex items-center space-x-2">
                                                                <Badge variant="destructive">401</Badge>
                                                                <span className="text-sm">
                                                                    Nieautoryzowany – błędny klucz API
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center space-x-2">
                                                                <Badge variant="destructive">404</Badge>
                                                                <span className="text-sm">
                                                                    Nie znaleziono zasobu
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center space-x-2">
                                                                <Badge variant="destructive">500</Badge>
                                                                <span className="text-sm">Błąd serwera</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </TabsContent>

                                                {/* ----------------------------- EXAMPLES */}
                                                <TabsContent value="examples" className="space-y-6">
                                                    {/* JS / Node */}
                                                    <div>
                                                        <div className="flex items-center justify-between mb-3">
                                                            <h4 className="font-medium">JavaScript</h4>
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() =>
                                                                    copyToClipboard(generateCodeExample(endpoint))
                                                                }
                                                            >
                                                                <Copy className="w-4 h-4 mr-1" />
                                                                Kopiuj
                                                            </Button>
                                                        </div>
                                                        <div className="bg-neutral-900 p-0 rounded-lg overflow-x-auto">
                                                            <SyntaxHighlighter
                                                                language="javascript"
                                                                style={atomOneDark}
                                                                customStyle={{
                                                                    background: "transparent",
                                                                    padding: "1rem",
                                                                    fontSize: "0.8rem",
                                                                }}
                                                            >
                                                                {generateCodeExample(endpoint)}
                                                            </SyntaxHighlighter>
                                                        </div>
                                                    </div>

                                                    {/* cURL */}
                                                    <div>
                                                        <div className="flex items-center justify-between mb-3">
                                                            <h4 className="font-medium">cURL</h4>
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() =>
                                                                    copyToClipboard(generateCurlExample(endpoint))
                                                                }
                                                            >
                                                                <Copy className="w-4 h-4 mr-1" />
                                                                Kopiuj
                                                            </Button>
                                                        </div>
                                                        <div className="bg-neutral-900 p-0 rounded-lg overflow-x-auto">
                                                            <SyntaxHighlighter
                                                                language="bash"
                                                                style={atomOneDark}
                                                                customStyle={{
                                                                    background: "transparent",
                                                                    padding: "1rem",
                                                                    fontSize: "0.8rem",
                                                                }}
                                                            >
                                                                {generateCurlExample(endpoint)}
                                                            </SyntaxHighlighter>
                                                        </div>
                                                    </div>
                                                </TabsContent>
                                            </Tabs>
                                        </CardContent>
                                    </Card>
                                )
                        )}

                        {/* Rate-limiting card REMOVED */}
                    </div>
                </div>
            </div>

            <Footer />
            <Toaster />
        </div>
    );
};

export default ApiDocsPage;
