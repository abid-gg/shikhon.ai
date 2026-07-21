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

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/40 p-6 md:p-12">
      <div className="mx-auto flex max-w-3xl flex-col gap-10">
        <header className="space-y-3">
          <p className="text-sm font-medium uppercase tracking-wide text-primary">
            SSC / HSC · Bangla curriculum
          </p>
          <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
            ShikhonAI
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            A curriculum-aware RAG exam platform for Bangladesh — PDFs,
            pgvector retrieval, and AI-assisted grading on free-tier hosting.
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>Get started</CardTitle>
            <CardDescription>
              Auth and dashboards are scaffolded; connect Supabase and the
              FastAPI backend next.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Link href="/login" className={cn(buttonVariants())}>
              Login
            </Link>
            <Link
              href="/register"
              className={cn(buttonVariants({ variant: "secondary" }))}
            >
              Register
            </Link>
            <Link
              href="/teacher/dashboard"
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              Teacher dashboard
            </Link>
            <Link
              href="/student/dashboard"
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              Student dashboard
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
