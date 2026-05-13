import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

export const Route = createFileRoute("/auth/register")({
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();
  const { register, isLoading, error, clearError } = useAuthStore();
  const [formData, setFormData] = useState({
    company_name: "",
    domain: "",
    org_size: "",
    admin_name: "",
    admin_email: "",
    password: "",
    confirmPassword: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    clearError();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (formData.password !== formData.confirmPassword) {
      // Note: We could set this as an error, but for now just show an alert
      alert("Passwords do not match");
      return;
    }

    try {
      await register(
        formData.company_name,
        formData.admin_name,
        formData.admin_email,
        formData.password,
        formData.domain,
        formData.org_size
      );
      navigate({ to: "/" });
    } catch {
      // Error is already set in store and displayed below
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted px-4 py-8">
      <div className="w-full max-w-md">
        <div className="rounded-lg border border-border bg-card p-8 shadow-lg">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-bold text-foreground">Axis Operate</h1>
            <p className="mt-1 text-sm text-muted-foreground">Create your account</p>
          </div>

          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <Label htmlFor="company_name" className="text-xs font-medium">
                Company Name
              </Label>
              <Input
                id="company_name"
                name="company_name"
                placeholder="Acme Corporation"
                value={formData.company_name}
                onChange={handleChange}
                disabled={isLoading}
                className="mt-1"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="domain" className="text-xs font-medium">
                  Domain (optional)
                </Label>
                <Input
                  id="domain"
                  name="domain"
                  placeholder="acme.com"
                  value={formData.domain}
                  onChange={handleChange}
                  disabled={isLoading}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="org_size" className="text-xs font-medium">
                  Organization Size (optional)
                </Label>
                <select
                  id="org_size"
                  name="org_size"
                  value={formData.org_size}
                  onChange={handleChange}
                  disabled={isLoading}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select...</option>
                  <option value="1-50">1-50</option>
                  <option value="51-200">51-200</option>
                  <option value="201-500">201-500</option>
                  <option value="500+">500+</option>
                </select>
              </div>
            </div>

            <div className="border-t border-border pt-3">
              <p className="mb-3 text-xs font-semibold text-foreground">Admin Account</p>

              <div>
                <Label htmlFor="admin_name" className="text-xs font-medium">
                  Admin Name
                </Label>
                <Input
                  id="admin_name"
                  name="admin_name"
                  placeholder="John Doe"
                  value={formData.admin_name}
                  onChange={handleChange}
                  disabled={isLoading}
                  className="mt-1"
                  required
                />
              </div>

              <div>
                <Label htmlFor="admin_email" className="mt-3 text-xs font-medium">
                  Admin Email
                </Label>
                <Input
                  id="admin_email"
                  name="admin_email"
                  type="email"
                  placeholder="admin@acme.com"
                  value={formData.admin_email}
                  onChange={handleChange}
                  disabled={isLoading}
                  className="mt-1"
                  required
                />
              </div>

              <div>
                <Label htmlFor="password" className="mt-3 text-xs font-medium">
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

              <div>
                <Label htmlFor="confirmPassword" className="mt-3 text-xs font-medium">
                  Confirm Password
                </Label>
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  placeholder="••••••••"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  disabled={isLoading}
                  className="mt-1"
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="mt-4 w-full"
              size="lg"
            >
              {isLoading ? "Creating account..." : "Create Account"}
            </Button>
          </form>

          <div className="mt-6 border-t border-border pt-6">
            <p className="text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <button
                onClick={() => navigate({ to: "/auth/login" })}
                className="font-medium text-primary hover:underline"
                type="button"
              >
                Sign in
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
