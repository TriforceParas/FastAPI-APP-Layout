import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";

import { ResetPasswordScreen } from "@/features/auth/components/auth-flows";
import { AuthScreen } from "@/features/auth/components/auth-screen";
import { AppShell } from "@/components/layout/app-shell";
import { AppShellSkeleton, ErrorState, ToastProvider } from "@/components/ui";
import { AuthProvider, useAuth } from "@/features/auth/auth-context";
import { AuditLogPage } from "@/features/audit/audit-log-page";
import { ComponentsGalleryPage } from "@/features/dev/components-gallery-page";
import { DashboardPage } from "@/features/dashboard/dashboard-page";
import { RolesPage } from "@/features/roles/roles-page";
import { SettingsPage } from "@/features/settings/settings-page";
import { ForbiddenPage, NotFoundPage } from "@/app/status-pages";
import { UsersPage } from "@/features/users/users-page";

/**
 * Decides what to render before any route:
 *   /reset-password       -> choose a new password (link from the email)
 *   no users yet          -> initial registration
 *   not signed in         -> login
 *   temporary password    -> forced password change
 *   otherwise             -> the app
 */
function AuthGate({ children }: { children: ReactNode }) {
  const { status, loading, error, refresh } = useAuth();
  const { pathname } = useLocation();
  if (loading) return <AppShellSkeleton />;
  if (!status) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#171717] p-6">
        <ErrorState
          className="w-full max-w-md"
          title="Cannot reach the server"
          description={error ?? "Check that the backend is running."}
          onRetry={() => void refresh()}
        />
      </div>
    );
  }
  // The emailed reset link works whether or not someone is signed in on this browser.
  if (pathname === "/reset-password") return <ResetPasswordScreen />;
  if (status.setup_required && !status.auth_bypass) return <AuthScreen mode="setup" />;
  if (!status.user) return <AuthScreen mode="login" />;
  if (status.user.must_change_password) return <AuthScreen mode="change-password" />;
  return <>{children}</>;
}

/** Client-side page guard (Read on `screen`). The API enforces the same rule server-side. */
function RequireScreen({ screen, children }: { screen: string; children: ReactNode }) {
  const { can } = useAuth();
  return can(screen) ? <>{children}</> : <ForbiddenPage />;
}

/** "/" goes to the landing page of the user's first role (Settings if they can open no page). */
function LandingRedirect() {
  const { status } = useAuth();
  return <Navigate to={status?.landing_path ?? "/settings"} replace />;
}

/** Hides developer-only screens when the server runs in production. */
function DevOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  return status?.environment === "production" ? <NotFoundPage /> : <>{children}</>;
}

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <AuthGate>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<LandingRedirect />} />
                <Route
                  path="dashboard"
                  element={
                    <RequireScreen screen="dashboard">
                      <DashboardPage />
                    </RequireScreen>
                  }
                />
                <Route
                  path="users"
                  element={
                    <RequireScreen screen="users">
                      <UsersPage />
                    </RequireScreen>
                  }
                />
                <Route
                  path="roles"
                  element={
                    <RequireScreen screen="roles">
                      <RolesPage />
                    </RequireScreen>
                  }
                />
                <Route
                  path="audit"
                  element={
                    <RequireScreen screen="audit">
                      <AuditLogPage />
                    </RequireScreen>
                  }
                />
                <Route path="settings" element={<SettingsPage />} />
                <Route
                  path="components"
                  element={
                    <DevOnly>
                      <ComponentsGalleryPage />
                    </DevOnly>
                  }
                />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </AuthGate>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
