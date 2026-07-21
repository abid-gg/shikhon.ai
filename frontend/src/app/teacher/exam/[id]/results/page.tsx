"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { analyticsAPI } from "@/lib/api";
import { Download, CheckCircle, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";

export default function AnalyticsDashboardPage() {
  const params = useParams();
  const examId = params.id as string;

  const [analytics, setAnalytics] = useState<any>(null);
  const [overrideValues, setOverrideValues] = useState<{ [key: string]: number }>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAnalytics();
  }, [examId]);

  const loadAnalytics = async () => {
    try {
      const res: any = await analyticsAPI.getExamAnalytics(examId);
      setAnalytics(res);
    } catch (error: any) {
      toast.error("বিশ্লেষণ লোড করতে ব্যর্থ হয়েছে");
    } finally {
      setLoading(false);
    }
  };

  const handleOverride = async (answerId: string) => {
    const score = overrideValues[answerId];
    if (score === undefined) {
      toast.error("স্কোর প্রবেশ করুন");
      return;
    }

    try {
      await analyticsAPI.overrideScore(answerId, score);
      toast.success("স্কোর আপডেট হয়েছে");
      setOverrideValues({ ...overrideValues, [answerId]: undefined });
      loadAnalytics();
    } catch (error: any) {
      toast.error(error.message || "স্কোর আপডেট ব্যর্থ");
    }
  };

  const exportCSV = () => {
    if (!analytics) return;

    const headers = [
      "শিক্ষার্থী নাম",
      "প্রশ্ন",
      "উত্তর",
      "AI স্কোর",
      "মন্তব্য",
    ];

    const rows = (analytics.flagged_answers || []).map((ans: any) => [
      ans.student_name,
      ans.question_text,
      ans.answer_text,
      ans.ai_score,
      ans.ai_justification || "",
    ]);

    const csv = [
      headers.join(","),
      ...rows.map((r: any[]) => r.map((v: any) => `"${v}"`).join(",")),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `exam-results-${examId}.csv`;
    link.click();

    toast.success("CSV ডাউনলোড হয়েছে");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bangla-text">
        লোড হচ্ছে...
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="flex items-center justify-center min-h-screen bangla-text">
        বিশ্লেষণ খুঁজে পাওয়া যায়নি
      </div>
    );
  }

  // Prepare chart data
  const chartData = analytics.score_distribution || [];

  // Score level colors
  const getScoreLevelColor = (percentage: number) => {
    if (percentage < 50) return "bg-red-50 hover:bg-red-100";
    if (percentage < 70) return "bg-yellow-50 hover:bg-yellow-100";
    return "bg-green-50 hover:bg-green-100";
  };

  const getScoreLevelBadge = (percentage: number) => {
    if (percentage < 50) return "bg-red-100 text-red-800";
    if (percentage < 70) return "bg-yellow-100 text-yellow-800";
    return "bg-green-100 text-green-800";
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold bangla-text">পরীক্ষার বিশ্লেষণ</h1>
          <Button onClick={exportCSV} className="bangla-text">
            <Download className="w-4 h-4 mr-2" />
            CSV ডাউনলোড করুন
          </Button>
        </div>

        {/* Stats */}
        <div className="grid md:grid-cols-3 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium bangla-text">মোট শিক্ষার্থী</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.total_students}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium bangla-text">জমা দেওয়া</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.submitted_count}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium bangla-text">গ্রেড করা</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.graded_count}</div>
            </CardContent>
          </Card>
        </div>

        {/* Score Distribution Chart */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="bangla-text">স্কোর বিতরণ</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="range" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Question Performance */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="bangla-text">প্রশ্নের পারফরম্যান্স</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="bangla-text">প্রশ্ন</TableHead>
                  <TableHead className="bangla-text">গড় স্কোর %</TableHead>
                  <TableHead className="bangla-text">ফ্ল্যাগ করা</TableHead>
                  <TableHead className="bangla-text">Bloom স্তর</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(analytics.question_analytics || []).map((q: any, i: number) => (
                  <TableRow
                    key={i}
                    className={getScoreLevelColor(q.avg_score_pct)}
                  >
                    <TableCell className="bangla-text">{q.question_text.substring(0, 50)}...</TableCell>
                    <TableCell className="bangla-text">{q.avg_score_pct.toFixed(1)}%</TableCell>
                    <TableCell>{q.flagged_count}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="bangla-text">
                        {q.bloom_level}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Weak Topics */}
        {(analytics.weak_topics || []).length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="bangla-text">দুর্বল বিষয়</CardTitle>
              <CardDescription className="bangla-text">
                এই প্রশ্নগুলিতে গড় স্কোর 50% এর নিচে
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {analytics.weak_topics.map((topic: string, i: number) => (
                  <li key={i} className="flex items-center gap-2 bangla-text">
                    <AlertCircle className="w-4 h-4 text-red-600" />
                    {topic}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Flagged Answers */}
        {(analytics.flagged_answers || []).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="bangla-text">ফ্ল্যাগ করা উত্তর</CardTitle>
              <CardDescription className="bangla-text">
                ম্যানুয়াল পর্যালোচনার জন্য চিহ্নিত উত্তর
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {analytics.flagged_answers.map((ans: any, i: number) => (
                <div key={i} className="border rounded-lg p-4">
                  <div className="mb-3">
                    <p className="font-semibold bangla-text">{ans.student_name}</p>
                    <p className="text-sm text-gray-600 bangla-text">{ans.question_text.substring(0, 100)}...</p>
                  </div>

                  <div className="bg-gray-50 p-3 rounded mb-3">
                    <p className="text-sm mb-1 bangla-text font-semibold">উত্তর:</p>
                    <p className="text-sm bangla-text">{ans.answer_text}</p>
                  </div>

                  <div className="flex items-center gap-4 mb-3">
                    <Badge className="bg-blue-100 text-blue-800 bangla-text">
                      স্কোর: {ans.ai_score}
                    </Badge>
                    <p className="text-sm text-gray-600 bangla-text">
                      {ans.ai_justification}
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <Input
                      type="number"
                      placeholder="নতুন স্কোর"
                      value={overrideValues[ans.answer_id] || ""}
                      onChange={(e) =>
                        setOverrideValues({
                          ...overrideValues,
                          [ans.answer_id]: parseFloat(e.target.value),
                        })
                      }
                      className="flex-1"
                    />
                    <Button
                      onClick={() => handleOverride(ans.answer_id)}
                      className="bangla-text"
                    >
                      সংরক্ষণ করুন
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
