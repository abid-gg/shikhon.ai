import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type PlaceholderPageProps = {
  title: string;
  description?: string;
};

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/40 p-6 md:p-10">
      <div className="mx-auto flex max-w-xl flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm font-medium text-muted-foreground">ShikhonAI</p>
          <Link
            href="/"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Home
          </Link>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            {description ? (
              <CardDescription>{description}</CardDescription>
            ) : null}
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Placeholder route — wire Supabase Auth, API calls, and UI here.
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
