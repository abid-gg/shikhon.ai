"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import ExamCodeDisplay from "@/components/ExamCodeDisplay";
import { examAPI, analyticsAPI } from "@/lib/api";
import { Clock, Users } from "lucide-react";
import toast from "react-hot-toast";

export default function ExamMonitorPage() {
  const params = useParams();
  const router = useRouter();
  const examId = params.id as string;

  const [exam, setExam] = useState<any>(null);
  const [analytics, setAnalytics] = useState<any>(null);
  const [students, setStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showEndDialog, setShowEndDialog] = useState(false);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, [examId]);

  const loadData = async () => {
    try {
      const [examRes, analyticsRes]: any[] = await Promise.all([
        examAPI.get(examId),
        analyticsAPI.getExamAnalytics(examId),
      ]);

      setExam(examRes);
      setAnalytics(analyticsRes);

      // Mock students from analytics
      if (analyticsRes?.flagged_answers) {
        setStudents(analyticsRes.flagged_answers);
      }
    } catch (error: any) {
      toast.error("ডেটা লোড করতে ব্যর্থ হয়েছে");
    } finally {
      setLoading(false);
    }
  };

  const handleEndExam = async () => {
    try {
      await examAPI.end(examId);
      toast.success("পরীক্ষা শেষ হয়েছে");
      setShowEndDialog(false);
      router.push(`/teacher/exam/${examId}/results`);
    } catch (error: any) {
      toast.error(error.message || "পরীক্ষা শেষ করতে ব্যর্থ");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bangla-text">
        লোড হচ্ছে...
      </div>
    );
  }

  if (!exam) {
    return (
      <div className="flex items-center justify-center min-h-screen bangla-text">
        পরীক্ষা খুঁজে পাওয়া যায়নি
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-3xl font-bold bangla-text mb-2">{exam.title}</h1>
            <p className="text-gray-600 bangla-text">{exam.subject} • {exam.grade_level}</p>
          </div>
          <Button
            onClick={() => setShowEndDialog(true)}
            variant="destructive"
            className="bangla-text"
            disabled={exam.status !== "active"}
          >
            পরীক্ষা শেষ করুন
          </Button>
        </div>

        {/* Exam Code Display */}
        <div className="mb-8">
          <ExamCodeDisplay code={exam.exam_code} />
        </div>

        {/* Stats */}
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium bangla-text">স্ট্যাটাস</CardTitle>
            </CardHeader>
            <CardContent>
              <Badge className={exam.status === "active" ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"}>
                {exam.status === "active" ? "সক্রিয়" : "শেষ"}
              </Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium bangla-text">সময়কাল</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600" />
              <span className="bangla-text">{exam.duration_minutes} মিনিট</span>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium bangla-text">অংশগ্রহণকারী</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-2">
              <Users className="w-4 h-4 text-green-600" />
              <span className="bangla-text">
                {analytics?.submitted_count || 0} / {analytics?.total_students || 0}
              </span>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium bangla-text">গ্রেড করা</CardTitle>
            </CardHeader>
            <CardContent>
              <span className="bangla-text">{analytics?.graded_count || 0}</span>
            </CardContent>
          </Card>
        </div>

        {/* Students Table */}
        <Card>
          <CardHeader>
            <CardTitle className="bangla-text">পরীক্ষার্থী</CardTitle>
          </CardHeader>
          <CardContent>
            {students.length === 0 ? (
              <p className="text-gray-500 bangla-text">কোনো পরীক্ষার্থী এখনও যোগ দেয়নি</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="bangla-text">নাম</TableHead>
                    <TableHead className="bangla-text">যোগ দেওয়ার সময়</TableHead>
                    <TableHead className="bangla-text">স্ট্যাটাস</TableHead>
                    <TableHead className="bangla-text">স্কোর</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {students.map((student, i) => (
                    <TableRow key={i}>
                      <TableCell className="bangla-text">{student.student_name}</TableCell>
                      <TableCell className="bangla-text">শীঘ্রই</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="bangla-text">
                          জমা দেওয়া
                        </Badge>
                      </TableCell>
                      <TableCell className="bangla-text">{student.ai_score} / 100</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* End Exam Dialog */}
        <AlertDialog open={showEndDialog} onOpenChange={setShowEndDialog}>
          <AlertDialogContent>
            <AlertDialogTitle className="bangla-text">পরীক্ষা শেষ করতে নিশ্চিত?</AlertDialogTitle>
            <AlertDialogDescription className="bangla-text">
              এটি সমস্ত শিক্ষার্থীর জন্য পরীক্ষা বন্ধ করবে এবং স্বয়ংক্রিয় গ্রেডিং শুরু করবে।
            </AlertDialogDescription>
            <div className="flex gap-2 justify-end">
              <AlertDialogCancel className="bangla-text">বাতিল</AlertDialogCancel>
              <AlertDialogAction onClick={handleEndExam} className="bangla-text">
                শেষ করুন
              </AlertDialogAction>
            </div>
          </AlertDialogContent>
        </AlertDialog>

        {/* Analytics Link */}
        <div className="mt-8">
          <Link href={`/teacher/exam/${examId}/results`}>
            <Button variant="outline" className="bangla-text">
              বিশ্লেষণ দেখুন
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
