"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { authAPI, setToken } from "@/lib/api";
import toast from "react-hot-toast";

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({ email: "", password: "" });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response: any = await authAPI.login(formData);
      setToken(response.access_token);
      
      // Redirect based on role
      const role = response.user.role;
      if (role === "teacher") {
        router.push("/teacher/dashboard");
      } else {
        router.push("/student/dashboard");
      }
      toast.success("লগইন সফল!");
    } catch (error: any) {
      toast.error(error.message || "লগইন ব্যর্থ হয়েছে");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="bangla-text">লগইন করুন</CardTitle>
          <CardDescription className="bangla-text">আপনার অ্যাকাউন্টে প্রবেশ করুন</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="bangla-text">ইমেইল</Label>
              <Input
                id="email"
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                placeholder="example@email.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="bangla-text">পাসওয়ার্ড</Label>
              <Input
                id="password"
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                required
                placeholder="••••••••"
              />
            </div>

            <Button
              type="submit"
              className="w-full bangla-text"
              disabled={loading}
            >
              {loading ? "লগইন হচ্ছে..." : "লগইন করুন"}
            </Button>
          </form>

          <p className="text-center text-sm text-gray-600 mt-4 bangla-text">
            এখনও অ্যাকাউন্ট নেই?{" "}
            <Link href="/register" className="text-blue-600 hover:underline">
              রেজিস্টার করুন
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
