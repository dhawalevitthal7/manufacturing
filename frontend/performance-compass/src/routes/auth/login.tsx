import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

export const Route = createFileRoute("/auth/login")({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { login, isLoading, error, clearError } = useAuthStore();
  const [formData, setFormData] = useState({ email: "", password: "" });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    clearError();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(formData.email, formData.password);
      navigate({ to: "/" });
    } catch {
      // Error is already set in store and displayed below
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted px-4">
      <div className="w-full max-w-md">
        <div className="rounded-lg border border-border bg-card p-8 shadow-lg">
          <div className="mb-8 text-center">
            <h1 className="text-2xl font-bold text-foreground">Axis Operate</h1>
            <p className="mt-2 text-sm text-muted-foreground">Manufacturing OKR OS</p>
          </div>

          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="email" className="text-sm font-medium">
                Email Address
              </Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="admin@company.com"
                value={formData.email}
                onChange={handleChange}
                disabled={isLoading}
                className="mt-1"
                required
              />
            </div>

            <div>
              <Label htmlFor="password" className="text-sm font-medium">
                Password
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                value={formData.password}
                onChange={handleChange}
                disabled={isLoading}
                className="mt-1"
                required
              />
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full"
              size="lg"
            >
              {isLoading ? "Signing in..." : "Sign In"}
            </Button>
          </form>

          <div className="mt-6 border-t border-border pt-6">
            <p className="text-center text-sm text-muted-foreground">
              Don't have an account?{" "}
              <button
                onClick={() => navigate({ to: "/auth/register" })}
                className="font-medium text-primary hover:underline"
                type="button"
              >
                Register here
              </button>
            </p>
          </div>
        </div>

        <div className="mt-8 space-y-3 text-center text-xs text-muted-foreground">
          <p>Birla demo (after seed):</p>
          <code className="block rounded bg-muted p-2 text-left">
            CEO: ceo@birlacement.test<br />
            Password: Test@1234<br />
            <span className="text-muted-foreground/80">(all Birla users use this password)</span>
          </code>
        </div>
      </div>
    </div>
  );
}
