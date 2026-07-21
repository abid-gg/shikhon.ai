import { PlaceholderPage } from "@/components/placeholder-page";

type PageProps = {
  params: { code: string };
};

export default function StudentExamPage({ params }: PageProps) {
  return (
    <PlaceholderPage
      title={`Exam · code ${params.code}`}
      description="Timed attempt UI, autosave answers, submit flow."
    />
  );
}
