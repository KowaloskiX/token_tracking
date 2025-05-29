import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { AlertCircle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background p-4">
      <Card className="max-w-md w-full border-none shadow-none text-center">
        <CardHeader>
          <div >
            <AlertCircle className="h-10 w-10 text-body-text mx-auto mb-4" />
            <CardTitle>404 Nie znaleziono strony </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
          Ooops... ta strona nie istnieje
          </p>
        </CardContent>
        <CardFooter>
          <Link href="/" className="w-full mt-10">
            <Button className="w-full">
              Wróć na stronę główną
            </Button>
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}