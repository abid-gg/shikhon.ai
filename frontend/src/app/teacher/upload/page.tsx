"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { documentAPI } from "@/lib/api";
import { Upload, FileText, Check, AlertCircle } from "lucide-react";
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

interface UploadedFile {
  file: File;
  id: string | null;
  status: "pending" | "uploading" | "processing" | "done" | "failed";
  chunksCount: number | null;
}

export default function UploadPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [subject, setSubject] = useState("বাংলা");
  const [gradeLevel, setGradeLevel] = useState("SSC");

  const onDrop = (acceptedFiles: File[]) => {
    const pdfFiles = acceptedFiles.filter((file) => file.type === "application/pdf");
    if (pdfFiles.length !== acceptedFiles.length) {
      toast.error("শুধুমাত্র PDF ফাইল আপলোড করুন");
    }

    const newFiles: UploadedFile[] = pdfFiles.map((file) => ({
      file,
      id: null,
      status: "pending",
      chunksCount: null,
    }));

    setFiles([...files, ...newFiles]);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
  });

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error("কোনো ফাইল নির্বাচিত হয়নি");
      return;
    }

    if (!subject) {
      toast.error("বিষয় নির্বাচন করুন");
      return;
    }

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.status !== "pending") continue;

      updateFileStatus(i, "uploading");

      try {
        const formData = new FormData();
        formData.append("file", file.file);
        formData.append("subject", subject);
        formData.append("grade_level", gradeLevel);

        const response: any = await documentAPI.upload(formData);
        updateFileStatus(i, "processing", response.id);

        // Poll for status
        pollStatus(i, response.id);
      } catch (error: any) {
        updateFileStatus(i, "failed");
        toast.error(`${file.file.name} আপলোড ব্যর্থ`);
      }
    }
  };

  const pollStatus = async (fileIndex: number, docId: string) => {
    const maxAttempts = 100; // Max 5 minutes
    let attempts = 0;

    const interval = setInterval(async () => {
      attempts++;

      try {
        const status: any = await documentAPI.getStatus(docId);

        if (status.status === "done") {
          updateFileStatus(fileIndex, "done", docId, status.chunks_count);
          clearInterval(interval);
          toast.success(`${files[fileIndex].file.name} প্রস্তুত`);
        } else if (status.status === "failed") {
          updateFileStatus(fileIndex, "failed");
          clearInterval(interval);
          toast.error(`${files[fileIndex].file.name} প্রসেসিং ব্যর্থ`);
        }
      } catch (error) {
        // Continue polling on error
      }

      if (attempts >= maxAttempts) {
        clearInterval(interval);
      }
    }, 3000); // Poll every 3 seconds
  };

  const updateFileStatus = (
    index: number,
    status: UploadedFile["status"],
    id?: string | null,
    chunksCount?: number | null
  ) => {
    setFiles((prev) => {
      const updated = [...prev];
      updated[index] = {
        ...updated[index],
        status,
        ...(id !== undefined && { id }),
        ...(chunksCount !== undefined && { chunksCount }),
      };
      return updated;
    });
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const getStatusColor = (status: UploadedFile["status"]) => {
    switch (status) {
      case "done":
        return "text-green-600";
      case "failed":
        return "text-red-600";
      case "uploading":
      case "processing":
        return "text-yellow-600";
      default:
        return "text-gray-600";
    }
  };

  const getStatusText = (status: UploadedFile["status"]) => {
    switch (status) {
      case "done":
        return "✓ প্রস্তুত";
      case "failed":
        return "✗ ব্যর্থ";
      case "uploading":
        return "আপলোড হচ্ছে...";
      case "processing":
        return "প্রক্রিয়াধীন...";
      default:
        return "অপেক্ষমাণ";
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold bangla-text mb-2">PDF আপলোড করুন</h1>
          <p className="text-gray-600 bangla-text">শিক্ষা উপাদান PDF আপলোড করুন এবং স্বয়ংক্রিয়ভাবে পাঠ্যক্রম নির্মাণ করুন</p>
        </div>

        {/* Upload Zone */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="bangla-text">ফাইল আপলোড করুন</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition ${
                isDragActive
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-300 hover:border-gray-400"
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
              {isDragActive ? (
                <>
                  <p className="text-lg font-semibold text-blue-600 bangla-text">
                    ফাইল এখানে ড্রপ করুন...
                  </p>
                </>
              ) : (
                <>
                  <p className="text-lg font-semibold mb-1 bangla-text">
                    এখানে ফাইল ড্র্যাগ করুন অথবা ক্লিক করুন
                  </p>
                  <p className="text-sm text-gray-500 bangla-text">শুধুমাত্র PDF ফাইল সমর্থিত</p>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Options */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="bangla-text">বিকল্প</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="subject" className="bangla-text">
                  বিষয়
                </Label>
                <Select value={subject} onValueChange={setSubject}>
                  <SelectTrigger id="subject">
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

              <div className="space-y-2">
                <Label htmlFor="grade" className="bangla-text">
                  শ্রেণী
                </Label>
                <Select value={gradeLevel} onValueChange={setGradeLevel}>
                  <SelectTrigger id="grade">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="SSC">SSC</SelectItem>
                    <SelectItem value="HSC">HSC</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button
              onClick={handleUpload}
              className="w-full bangla-text"
              disabled={files.length === 0}
            >
              আপলোড করুন
            </Button>
          </CardContent>
        </Card>

        {/* Files List */}
        {files.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="bangla-text">আপলোড করা ফাইল</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {files.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <FileText className="w-5 h-5 text-blue-600 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{file.file.name}</p>
                        <p className="text-sm text-gray-500 bangla-text">
                          {(file.file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className={`text-sm font-medium bangla-text ${getStatusColor(file.status)}`}>
                        {getStatusText(file.status)}
                        {file.chunksCount && (
                          <span className="ml-1 text-gray-600">
                            ({file.chunksCount} চ্যাংক)
                          </span>
                        )}
                      </div>

                      {file.status === "pending" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => removeFile(index)}
                          className="text-red-600 hover:text-red-700"
                        >
                          মুছুন
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
