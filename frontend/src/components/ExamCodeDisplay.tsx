"use client";

import { useState } from "react";
import QRCode from "qrcode.react";
import { Button } from "@/components/ui/button";
import { Copy, Download } from "lucide-react";
import toast from "react-hot-toast";

interface ExamCodeDisplayProps {
  code: string;
  examUrl?: string;
}

export default function ExamCodeDisplay({ code, examUrl }: ExamCodeDisplayProps) {
  const [showQR, setShowQR] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    toast.success("কোড কপি হয়েছে!");
  };

  const downloadQR = () => {
    const canvas = document.querySelector("canvas");
    if (!canvas) return;
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `exam-code-${code}.png`;
    link.click();
  };

  return (
    <div className="flex flex-col items-center gap-4 p-6 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border-2 border-blue-200">
      <div className="text-center">
        <p className="text-sm text-gray-600 mb-2 bangla-text">পরীক্ষার কোড</p>
        <div className="bg-white px-6 py-4 rounded-lg border-2 border-blue-300 font-mono text-3xl font-bold text-blue-600 tracking-widest">
          {code}
        </div>
      </div>

      <div className="flex gap-2">
        <Button
          onClick={copyToClipboard}
          variant="outline"
          size="sm"
          className="bangla-text"
        >
          <Copy className="w-4 h-4 mr-2" />
          কপি করুন
        </Button>

        <Button
          onClick={() => setShowQR(!showQR)}
          variant="outline"
          size="sm"
          className="bangla-text"
        >
          {showQR ? "QR লুকান" : "QR দেখান"}
        </Button>
      </div>

      {showQR && (
        <div className="flex flex-col items-center gap-2 p-4 bg-white rounded-lg">
          <QRCode value={examUrl || code} size={256} level="H" includeMargin={true} />
          <Button
            onClick={downloadQR}
            size="sm"
            variant="ghost"
            className="bangla-text"
          >
            <Download className="w-4 h-4 mr-2" />
            ডাউনলোড করুন
          </Button>
        </div>
      )}
    </div>
  );
}
