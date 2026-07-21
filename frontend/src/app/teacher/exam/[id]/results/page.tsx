import { PlaceholderPage } from "@/components/placeholder-page";

type PageProps = {
  params: { id: string };
};

export default function TeacherExamResultsPage({ params }: PageProps) {
  return (
    <PlaceholderPage
      title={`Exam results · ${params.id}`}
      description="Scores, AI justifications, and teacher overrides per student."
    />
  );
}
