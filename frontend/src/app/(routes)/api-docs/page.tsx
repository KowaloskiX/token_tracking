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
    BookOpen,
} from "lucide-react";
import Footer from "@/components/landing/Footer";
import { useToast } from "@/hooks/use-toast";
import { Toaster } from "@/components/ui/toaster";
import SyntaxHighlighter from "react-syntax-highlighter";
import { atomOneDark } from "react-syntax-highlighter/dist/cjs/styles/hljs";
import { useTranslations } from 'next-intl';

const ApiDocsPage = () => {
    const [selectedEndpoint, setSelectedEndpoint] = useState("results");
    const { toast } = useToast();
    
    // Get translations
    const t = useTranslations('api');
    const tPage = useTranslations('api.page');
    const tEndpoints = useTranslations('api.endpoints');
    const tTabs = useTranslations('api.tabs');
    const tOverview = useTranslations('api.overview');
    const tRequest = useTranslations('api.request');
    const tResponse = useTranslations('api.response');
    const tExamples = useTranslations('api.examples');

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        toast({
            title: tPage('copied'),
            description: tPage('copied_description'),
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
            title: tEndpoints('results.title'),
            description: tEndpoints('results.description'),
            detailedDescription: tEndpoints('results.detailed_description'),
            icon: <Search className="w-4 h-4" />,
            useCase: tEndpoints('results.use_case'),
            requestBodyExample: `{
  "analysis_id": "string",
  "date_from": "YYYY-MM-DD",
  "date_to": "YYYY-MM-DD",
  "limit": "number",
  "offset": "number",
  "include_historical": "boolean"
}`,
            response: {
                results: "Array<TenderResult>",
                total: "number",
                has_more: "boolean",
            },
            responseExample: `{
  "results": [
    {
      "_id": "60f5a8b9c1d2e3f4a5b6c7d8",
      "tender_name": "Dostawa sprzętu komputerowego dla szkół podstawowych",
      "organization": "Gmina Przykładowa",
      "tender_url": "https://ezamowienia.gov.pl/mp-client/search/list/ocds-123456",
      "tender_score": 0.85,
      "status": "active",
      "submission_deadline": "2025-07-15 14:00",
      "location": null,
      "created_at": "2025-06-01T10:30:00.427000",
      "opened_at": "2025-06-02T08:15:22.123000"
    }
  ],
  "total": 45,
  "has_more": true
}`,
        },
        {
            id: "criteria",
            method: "GET",
            path: "/api/results/{result_id}/criteria",
            title: tEndpoints('criteria.title'),
            description: tEndpoints('criteria.description'),
            detailedDescription: tEndpoints('criteria.detailed_description'),
            icon: <FileText className="w-4 h-4" />,
            useCase: tEndpoints('criteria.use_case'),
            response: {
                result_id: "string",
                criteria_analysis: "Array<CriteriaItem>",
                tender_score: "number",
                created_at: "string",
            },
            responseExample: `{
  "result_id": "60f5a8b9c1d2e3f4a5b6c7d8",
  "criteria_analysis": [
    {
      "criteria": "Czy wartość kontraktu przekracza 500000 zł?",
      "analysis": {
        "summary": "Wartość szacunkowa zamówienia wynosi 1200000 zł",
        "confidence": "HIGH",
        "criteria_met": true,
        "weight": 5
      },
      "exclude_from_score": false,
      "is_disqualifying": false
    },
    {
      "criteria": "Czy lokalizacja jest w promieniu 100km?",
      "analysis": {
        "summary": "Gdańsk - odległość około 80km od naszej siedziby",
        "confidence": "MEDIUM",
        "criteria_met": true,
        "weight": 4
      },
      "exclude_from_score": false,
      "is_disqualifying": false
    }
  ],
  "tender_score": 0.85,
  "created_at": "2025-06-01T10:30:00.427000"
}`,
        },
        {
            id: "files",
            method: "GET",
            path: "/api/results/{result_id}/files",
            title: tEndpoints('files.title'),
            description: tEndpoints('files.description'),
            detailedDescription: tEndpoints('files.detailed_description'),
            icon: <Download className="w-4 h-4" />,
            useCase: tEndpoints('files.use_case'),
            queryParams: {
                include_preview: "boolean (opcjonalne)",
            },
            response: {
                result_id: "string",
                files: "Array<FileInfo>",
                total_files: "number",
            },
            responseExample: `{
  "result_id": "60f5a8b9c1d2e3f4a5b6c7d8",
  "files": [
    {
      "filename": "SIWZ_dostawa_sprzetu.pdf",
      "blob_url": "https://blob.vercel-storage.com/example-file-abc123.pdf",
      "file_size": 1548320,
      "content_preview": "SPECYFIKACJA ISTOTNYCH WARUNKÓW ZAMÓWIENIA 1. Nazwa zamawiającego: Gmina Przykładowa 2. Przedmiot zamówienia: Dostawa sprzętu komputerowego..."
    },
    {
      "filename": "formularz_oferty.docx",
      "blob_url": "https://blob.vercel-storage.com/example-form-def456.docx", 
      "file_size": 245760,
      "content_preview": "FORMULARZ OFERTY 1. Identyfikacja wykonawcy: Nazwa firmy: ________________ NIP: ________________"
    }
  ],
  "total_files": 2
}`,
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
            {/* Hero */}
            <div className="pt-24 pb-12 bg-background/90 backdrop-blur-sm">
                <div className="mx-auto max-w-7xl px-6 lg:px-8">
                    <div className="mx-auto max-w-3xl text-center">
                        <div className="flex items-center justify-center mb-4">
                            <BookOpen className="w-8 h-8 text-primary mr-3" />
                            <h1 className="text-4xl tracking-tight text-foreground sm:text-5xl">
                                {tPage('title')}
                            </h1>
                        </div>
                        <p className="mt-6 text-lg text-body-text">
                            {tPage('description')}
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
                                <CardTitle className="text-lg">{tEndpoints('title')}</CardTitle>
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
                                    <CardTitle>{tPage('auth.title')}</CardTitle>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <p className="text-body-text">
                                    {tPage('auth.description')}{" "}
                                    <code className="bg-secondary px-2 py-1 rounded">
                                        X-API-Key
                                    </code>
                                    .
                                </p>

                                <div className="bg-secondary p-4 rounded-lg">
                                    <code className="text-sm">{tPage('auth.header_example')}</code>
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
                                                    <TabsTrigger value="overview">{tTabs('overview')}</TabsTrigger>
                                                    <TabsTrigger value="request">{tTabs('request')}</TabsTrigger>
                                                    <TabsTrigger value="response">{tTabs('response')}</TabsTrigger>
                                                    <TabsTrigger value="examples">{tTabs('examples')}</TabsTrigger>
                                                </TabsList>

                                                {/* ----------------------------- OVERVIEW */}
                                                <TabsContent value="overview" className="space-y-4">
                                                    <div>
                                                        <h4 className="font-medium mb-2">{tOverview('description')}</h4>
                                                        <p className="text-body-text">
                                                            {endpoint.detailedDescription}
                                                        </p>
                                                    </div>

                                                    <div>
                                                        <h4 className="font-medium mb-2">{tOverview('endpoint')}</h4>
                                                        <div className="flex items-center space-x-2">
                                                            <Badge variant="default">
                                                                {endpoint.method}
                                                            </Badge>
                                                            <code className="bg-secondary px-2 py-1 rounded">
                                                                {endpoint.path}
                                                            </code>
                                                        </div>
                                                    </div>

                                                    {endpoint.useCase && (
                                                        <div>
                                                            <h4 className="font-medium mb-2">{tOverview('when_to_use')}</h4>
                                                            <div className="bg-secondary border-l-4 border-accent p-3 rounded">
                                                                <p className="text-sm text-primary">
                                                                    {endpoint.useCase}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    )}

                                                    <div>
                                                        <h4 className="font-medium mb-2">{tOverview('quick_start')}</h4>
                                                        <div className="space-y-2">
                                                            <p className="text-sm text-body-text">
                                                                1. {tOverview('step1')}
                                                            </p>
                                                            <p className="text-sm text-body-text">
                                                                2. {endpoint.method === "POST" 
                                                                    ? tOverview('step2_post')
                                                                    : tOverview('step2_get')}
                                                            </p>
                                                            <p className="text-sm text-body-text">
                                                                3. {tOverview('step3')}
                                                            </p>
                                                        </div>
                                                    </div>
                                                </TabsContent>

                                                {/* ----------------------------- REQUEST */}
                                                <TabsContent value="request" className="space-y-4">
                                                    {endpoint.requestBodyExample && (
                                                        <div>
                                                            <h4 className="font-medium mb-3">{tRequest('body')}</h4>
                                                            <div className="bg-neutral-900 p-4 rounded-lg">
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
                                                                {tRequest('query_params')}
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
                                                        <h4 className="font-medium mb-3">{tRequest('headers')}</h4>
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
                                                            {tResponse('structure')}
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

                                                    {endpoint.responseExample && (
                                                        <div>
                                                            <h4 className="font-medium mb-3">
                                                                {tResponse('example')}
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
                                                                    {endpoint.responseExample}
                                                                </SyntaxHighlighter>
                                                            </div>
                                                        </div>
                                                    )}

                                                    <div>
                                                        <h4 className="font-medium mb-3">
                                                            {tResponse('status_codes')}
                                                        </h4>
                                                        <div className="space-y-2">
                                                            <div className="flex items-center space-x-2">
                                                                <Badge className="bg-green-600 text-white">
                                                                    200
                                                                </Badge>
                                                                <span className="text-sm">{tResponse('success')}</span>
                                                            </div>
                                                            <div className="flex items-center space-x-2">
                                                                <Badge variant="destructive">401</Badge>
                                                                <span className="text-sm">
                                                                    {tResponse('unauthorized')}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center space-x-2">
                                                                <Badge variant="destructive">404</Badge>
                                                                <span className="text-sm">
                                                                    {tResponse('not_found')}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center space-x-2">
                                                                <Badge variant="destructive">500</Badge>
                                                                <span className="text-sm">{tResponse('server_error')}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </TabsContent>

                                                {/* ----------------------------- EXAMPLES */}
                                                <TabsContent value="examples" className="space-y-6">
                                                    {/* JS / Node */}
                                                    <div>
                                                        <div className="flex items-center justify-between mb-3">
                                                            <h4 className="font-medium">{tExamples('javascript')}</h4>
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() =>
                                                                    copyToClipboard(generateCodeExample(endpoint))
                                                                }
                                                            >
                                                                <Copy className="w-4 h-4 mr-1" />
                                                                {tExamples('copy')}
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
                                                                {tExamples('copy')}
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
                    </div>
                </div>
            </div>

            <Footer />
            <Toaster />
        </div>
    );
};

export default ApiDocsPage;