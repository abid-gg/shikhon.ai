"use client";

import { useState, useEffect } from "react";
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
import { documentAPI, examAPI } from "@/lib/api";
import { FileText, Plus, Upload } from "lucide-react";
import toast from "react-hot-toast";

export default function TeacherDashboard() {
  const [documents, setDocuments] = useState([]);
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [docsRes, examsRes]: any[] = await Promise.all([
        documentAPI.list(),
        Promise.resolve([]), // Will implement exams endpoint
      ]);
      setDocuments(docsRes || []);
      setExams(examsRes || []);
    } catch (error: any) {
      toast.error("ডেটা লোড করতে ব্যর্থ হয়েছে");
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "done":
        return "bg-green-100 text-green-800";
      case "processing":
        return "bg-yellow-100 text-yellow-800";
      case "pending":
        return "bg-blue-100 text-blue-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "done":
        return "প্রস্তুত";
      case "processing":
        return "প্রক্রিয়াধীন";
      case "pending":
        return "অপেক্ষমাণ";
      case "failed":
        return "ব্যর্থ";
      default:
        return status;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold bangla-text">শিক্ষক ড্যাশবোর্ড</h1>
            <div className="flex gap-4">
              <Link href="/teacher/exam/create">
                <Button className="bangla-text">
                  <Plus className="w-4 h-4 mr-2" />
                  নতুন পরীক্ষা তৈরি করুন
                </Button>
              </Link>
              <Link href="/teacher/upload">
                <Button variant="outline" className="bangla-text">
                  <Upload className="w-4 h-4 mr-2" />
                  PDF আপলোড করুন
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Stats Cards */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium bangla-text">
                মোট দস্তাবেজ
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{documents.length}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium bangla-text">
                মোট পরীক্ষা
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{exams.length}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium bangla-text">
                সক্রিয় পরীক্ষা
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {exams.filter((e: any) => e.status === "active").length}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Documents Table */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="bangla-text">সম্প্রতি আপলোড করা দস্তাবেজ</CardTitle>
          </CardHeader>
          <CardContent>
            {documents.length === 0 ? (
              <p className="text-gray-500 bangla-text">কোনো দস্তাবেজ আপলোড করা হয়নি</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="bangla-text">ফাইলনাম</TableHead>
                    <TableHead className="bangla-text">বিষয়</TableHead>
                    <TableHead className="bangla-text">স্ট্যাটাস</TableHead>
                    <TableHead className="bangla-text">আপলোড তারিখ</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc: any) => (
                    <TableRow key={doc.id}>
                      <TableCell className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-blue-600" />
                        {doc.filename}
                      </TableCell>
                      <TableCell className="bangla-text">{doc.subject}</TableCell>
                      <TableCell>
                        <Badge className={getStatusColor(doc.upload_status) + " bangla-text"}>
                          {getStatusText(doc.upload_status)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {new Date(doc.created_at).toLocaleDateString("bn-BD")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Exams Table */}
        <Card>
          <CardHeader>
            <CardTitle className="bangla-text">সম্প্রতির পরীক্ষা</CardTitle>
          </CardHeader>
          <CardContent>
            {exams.length === 0 ? (
              <p className="text-gray-500 bangla-text">কোনো পরীক্ষা তৈরি করা হয়নি</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="bangla-text">শিরোনাম</TableHead>
                    <TableHead className="bangla-text">বিষয়</TableHead>
                    <TableHead className="bangla-text">কোড</TableHead>
                    <TableHead className="bangla-text">স্ট্যাটাস</TableHead>
                    <TableHead className="bangla-text">অ্যাকশন</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exams.map((exam: any) => (
                    <TableRow key={exam.id}>
                      <TableCell className="bangla-text">{exam.title}</TableCell>
                      <TableCell className="bangla-text">{exam.subject}</TableCell>
                      <TableCell>
                        <code className="bg-gray-100 px-2 py-1 rounded font-mono">
                          {exam.exam_code}
                        </code>
                      </TableCell>
                      <TableCell>
                        <Badge className="bangla-text">
                          {exam.status === "active" ? "সক্রিয়" : "খসড়া"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Link href={`/teacher/exam/${exam.id}`}>
                          <Button size="sm" variant="ghost" className="bangla-text">
                            দেখুন
                          </Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
