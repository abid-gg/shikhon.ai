"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import ExamCodeDisplay from "@/components/ExamCodeDisplay";
import { examAPI, documentAPI, questionAPI } from "@/lib/api";
import { Trash2, Loader } from "lucide-react";
import toast from "react-hot-toast";

const SUBJECTS = [
  "বাংলা",
  "English",
  "Physics",
  "Chemistry",
  "Biology",
  "Math",
  "History",
  "Geography",
  "ICT",
];

type StepType = "setup" | "questions" | "review";

interface Question {
  id: string;
  question_text: string;
  question_type: string;
  bloom_level: string;
  marks: number;
  expected_answer_points: string[];
}

export default function ExamCreatorPage() {
  const router = useRouter();
  const [step, setStep] = useState<StepType>("setup");
  const [examId, setExamId] = useState<string>("");
  const [examCode, setExamCode] = useState<string>("");
  const [documents, setDocuments] = useState<any[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);

  // Step 1: Setup
  const [setup, setSetup] = useState({
    title: "",
    subject: "বাংলা",
    grade_level: "SSC",
    duration_minutes: 60,
  });

  // Step 2: Generation
  const [generation, setGeneration] = useState({
    question_type: "short",
    num_questions: 10,
    marks_per_question: 5,
    chapter_filter: "",
  });

  const handleSetupChange = (field: string, value: any) => {
    setSetup({ ...setup, [field]: value });
  };

  const handleGenerationChange = (field: string, value: any) => {
    setGeneration({ ...generation, [field]: value });
  };

  const handleCreateExam = async () => {
    if (!setup.title) {
      toast.error("পরীক্ষার শিরোনাম প্রবেশ করুন");
      return;
    }

    setLoading(true);
    try {
      const response: any = await examAPI.create(setup);
      setExamId(response.id);
      setExamCode(response.exam_code);

      // Load documents for next step
      const docsRes: any = await documentAPI.list();
      setDocuments(docsRes || []);

      setStep("questions");
      toast.success("পরীক্ষা তৈরি হয়েছে!");
    } catch (error: any) {
      toast.error(error.message || "পরীক্ষা তৈরি ব্যর্থ");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateQuestions = async () => {
    setLoading(true);
    try {
      const docIds = documents
        .filter((d) => d.upload_status === "done")
        .map((d) => d.id);

      if (docIds.length === 0) {
        toast.error("প্রস্তুত দস্তাবেজ নেই");
        setLoading(false);
        return;
      }

      const payload = {
        ...generation,
        subject: setup.subject,
        grade_level: setup.grade_level,
        documents: docIds,
      };

      const response: any = await questionAPI.generate(payload);
      setQuestions(response.questions || []);
      setStep("review");
      toast.success("প্রশ্ন তৈরি হয়েছে!");
    } catch (error: any) {
      toast.error(error.message || "প্রশ্ন তৈরি ব্যর্থ");
    } finally {
      setLoading(false);
    }
  };

  const handlePublishExam = async () => {
    setLoading(true);
    try {
      await examAPI.activate(examId);
      toast.success(`পরীক্ষা প্রকাশিত! কোড: ${examCode}`);
      router.push(`/teacher/exam/${examId}`);
    } catch (error: any) {
      toast.error(error.message || "প্রকাশনা ব্যর্থ");
    } finally {
      setLoading(false);
    }
  };

  const removeQuestion = (index: number) => {
    setQuestions((prev) => prev.filter((_, i) => i !== index));
  };

  const updateQuestion = (index: number, field: string, value: any) => {
    setQuestions((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const bloomColors: { [key: string]: string } = {
    remember: "bg-blue-100 text-blue-800",
    understand: "bg-green-100 text-green-800",
    apply: "bg-yellow-100 text-yellow-800",
    analyze: "bg-orange-100 text-orange-800",
    evaluate: "bg-red-100 text-red-800",
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Steps Indicator */}
        <div className="flex justify-between mb-8">
          {(["setup", "questions", "review"] as const).map((s, i) => (
            <div key={s} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold bangla-text ${
                  (["setup", "questions", "review"].indexOf(step as any) >= i)
                    ? "bg-blue-600 text-white"
                    : "bg-gray-300 text-gray-600"
                }`}
              >
                {i + 1}
              </div>
              {i < 2 && <div className="flex-1 h-1 bg-gray-300 mx-2" />}
            </div>
          ))}
        </div>

        {/* Step 1: Setup */}
        {step === "setup" && (
          <Card>
            <CardHeader>
              <CardTitle className="bangla-text">পরীক্ষা সেটআপ</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="title" className="bangla-text">
                  পরীক্ষার শিরোনাম
                </Label>
                <Input
                  id="title"
                  value={setup.title}
                  onChange={(e) => handleSetupChange("title", e.target.value)}
                  placeholder="যেমন: বাংলা প্রথম অধ্যায় পরীক্ষা"
                  className="mt-1"
                />
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="subject" className="bangla-text">
                    বিষয়
                  </Label>
                  <Select value={setup.subject} onValueChange={(v) => handleSetupChange("subject", v)}>
                    <SelectTrigger id="subject" className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SUBJECTS.map((s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="grade" className="bangla-text">
                    শ্রেণী
                  </Label>
                  <Select value={setup.grade_level} onValueChange={(v) => handleSetupChange("grade_level", v)}>
                    <SelectTrigger id="grade" className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="SSC">SSC</SelectItem>
                      <SelectItem value="HSC">HSC</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label htmlFor="duration" className="bangla-text">
                  সময়কাল (মিনিট): {setup.duration_minutes}
                </Label>
                <Slider
                  id="duration"
                  min={15}
                  max={240}
                  step={15}
                  value={[setup.duration_minutes]}
                  onValueChange={(v) => handleSetupChange("duration_minutes", v[0])}
                  className="mt-2"
                />
              </div>

              <Button onClick={handleCreateExam} disabled={loading} className="w-full bangla-text">
                {loading ? "তৈরি হচ্ছে..." : "পরবর্তী"}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Generate Questions */}
        {step === "questions" && (
          <Card>
            <CardHeader>
              <CardTitle className="bangla-text">প্রশ্ন তৈরি করুন</CardTitle>
              <CardDescription className="bangla-text">
                AI ব্যবহার করে প্রশ্ন তৈরি করার জন্য পছন্দগুলি সেট করুন
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="qtype" className="bangla-text">
                    প্রশ্নের ধরন
                  </Label>
                  <Select value={generation.question_type} onValueChange={(v) => handleGenerationChange("question_type", v)}>
                    <SelectTrigger id="qtype" className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="mcq">MCQ</SelectItem>
                      <SelectItem value="short">Short Answer</SelectItem>
                      <SelectItem value="creative">Creative</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="marks" className="bangla-text">
                    প্রতি প্রশ্ন মার্ক
                  </Label>
                  <Input
                    id="marks"
                    type="number"
                    value={generation.marks_per_question}
                    onChange={(e) => handleGenerationChange("marks_per_question", parseInt(e.target.value))}
                    className="mt-1"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="numq" className="bangla-text">
                  প্রশ্ন সংখ্যা: {generation.num_questions}
                </Label>
                <Slider
                  id="numq"
                  min={5}
                  max={30}
                  step={1}
                  value={[generation.num_questions]}
                  onValueChange={(v) => handleGenerationChange("num_questions", v[0])}
                  className="mt-2"
                />
              </div>

              <div>
                <Label htmlFor="chapter" className="bangla-text">
                  অধ্যায় ফিল্টার (ঐচ্ছিক)
                </Label>
                <Input
                  id="chapter"
                  value={generation.chapter_filter}
                  onChange={(e) => handleGenerationChange("chapter_filter", e.target.value)}
                  placeholder="যেমন: অধ্যায় ১, কণা পদার্থবিজ্ঞান"
                  className="mt-1"
                />
              </div>

              <div className="flex gap-2">
                <Button onClick={() => setStep("setup")} variant="outline" className="flex-1 bangla-text">
                  পূর্ববর্তী
                </Button>
                <Button onClick={handleGenerateQuestions} disabled={loading} className="flex-1 bangla-text">
                  {loading ? (
                    <>
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
                      তৈরি হচ্ছে...
                    </>
                  ) : (
                    "প্রশ্ন তৈরি করুন"
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Review & Edit */}
        {step === "review" && (
          <>
            <div className="mb-8">
              <ExamCodeDisplay code={examCode} />
            </div>

            <Card className="mb-8">
              <CardHeader>
                <CardTitle className="bangla-text">প্রশ্ন পর্যালোচনা করুন</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {questions.map((q, i) => (
                  <div key={i} className="border rounded-lg p-4">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex-1">
                        <Textarea
                          value={q.question_text}
                          onChange={(e) => updateQuestion(i, "question_text", e.target.value)}
                          className="mb-2 bangla-text"
                        />
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => removeQuestion(i)}
                        className="text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>

                    <div className="flex gap-2 flex-wrap">
                      <Badge className={bloomColors[q.bloom_level] || "bg-gray-100"}>
                        {q.bloom_level}
                      </Badge>
                      <Badge variant="outline" className="bangla-text">
                        {q.marks} মার্ক
                      </Badge>
                      <Badge variant="outline" className="bangla-text">
                        {q.question_type}
                      </Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="flex gap-2">
              <Button onClick={() => setStep("questions")} variant="outline" className="flex-1 bangla-text">
                পূর্ববর্তী
              </Button>
              <Button onClick={handlePublishExam} disabled={loading} className="flex-1 bangla-text">
                {loading ? "প্রকাশ হচ্ছে..." : "পরীক্ষা প্রকাশ করুন"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
