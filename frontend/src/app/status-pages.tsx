import { Link } from "react-router";

import { buttonClass, Card, ForbiddenState } from "@/components/ui";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card className="w-full max-w-lg p-8 text-center">
        <p className="text-xs font-medium tracking-[0.18em] text-emerald-300 uppercase">404</p>
        <h1 className="mt-3 text-xl font-medium">Page not found</h1>
        <p className="mt-2 text-sm leading-6 text-[#888]">
          The address may be incorrect, or the page may no longer be available.
        </p>
        <Link to="/" className={buttonClass({ size: "lg", className: "mt-5" })}>
          Return to workspace
        </Link>
      </Card>
    </div>
  );
}

export function ForbiddenPage() {
  return <ForbiddenState />;
}
