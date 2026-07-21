import Link from "next/link";
import { Button } from "@/components/ui/button";
import { BookOpen, Zap, BarChart3 } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Navbar */}
      <nav className="flex justify-between items-center px-6 py-4 max-w-6xl mx-auto">
        <div className="text-2xl font-bold bangla-text text-blue-600">
          ShikhonAI
        </div>
        <div className="flex gap-4">
          <Link href="/login">
            <Button variant="outline" className="bangla-text">
              লগইন করুন
            </Button>
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-6xl mx-auto px-6 py-20 text-center">
        <h1 className="text-5xl md:text-6xl font-bold mb-6 bangla-text text-gray-900">
          ShikhonAI — SSC/HSC পরীক্ষার স্মার্ট প্ল্যাটফর্ম
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto bangla-text">
          কারিকুলাম-সচেতন AI গ্রেডিং এবং বুম স্তরের প্রশ্ন তৈরি সহ লাইভ পরীক্ষা পরিচালনা করুন
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col md:flex-row gap-4 justify-center mb-12">
          <Link href="/register?role=teacher">
            <Button
              size="lg"
              className="bg-blue-600 hover:bg-blue-700 bangla-text text-lg"
            >
              শিক্ষক হিসেবে প্রবেশ করুন
            </Button>
          </Link>
          <Link href="/register?role=student">
            <Button
              size="lg"
              variant="outline"
              className="bangla-text text-lg"
            >
              শিক্ষার্থী হিসেবে যোগ দিন
            </Button>
          </Link>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-8 mt-16">
          <div className="bg-white p-6 rounded-lg shadow-md">
            <BookOpen className="w-12 h-12 mx-auto mb-4 text-blue-600" />
            <h3 className="text-lg font-semibold mb-2 bangla-text">
              বাংলা পাঠ্যক্রম-সচেতন RAG
            </h3>
            <p className="text-gray-600 bangla-text text-sm">
              বাংলা শিক্ষা উপাদান এবং SSC/HSC পাঠ্যক্রম বোঝার জন্য অপ্টিমাইজ করা
            </p>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-md">
            <Zap className="w-12 h-12 mx-auto mb-4 text-yellow-600" />
            <h3 className="text-lg font-semibold mb-2 bangla-text">
              বুম স্তর সংযুক্ত প্রশ্ন
            </h3>
            <p className="text-gray-600 bangla-text text-sm">
              স্মার্ট প্রশ্ন প্রজন্ম এবং বিভিন্ন জ্ঞানের স্তরের জন্য সামগ্রী
            </p>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-md">
            <BarChart3 className="w-12 h-12 mx-auto mb-4 text-green-600" />
            <h3 className="text-lg font-semibold mb-2 bangla-text">
              AI গ্রেডিং এবং বিশ্লেষণ
            </h3>
            <p className="text-gray-600 bangla-text text-sm">
              তাৎক্ষণিক AI স্বয়ংক্রিয় গ্রেডিং এবং বিস্তৃত পারফরম্যান্স বিশ্লেষণ
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
