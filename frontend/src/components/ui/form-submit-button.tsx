import { useFormStatus } from "react-dom";
import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/primitives";

export function FormSubmitButton({
  children,
  pendingLabel = "Saving…",
  className,
  disabled,
  variant = "primary",
  pending: pendingOverride,
}: {
  children: React.ReactNode;
  pendingLabel?: string;
  className?: string;
  disabled?: boolean;
  variant?: Parameters<typeof Button>[0]["variant"];
  /** Override for forms using onSubmit instead of a React form action. */
  pending?: boolean;
}) {
  const status = useFormStatus();
  const pending = pendingOverride ?? status.pending;
  return (
    <Button
      type="submit"
      variant={variant}
      className={className}
      disabled={disabled ? true : pending}
    >
      {pending ? (
        <>
          <LoaderCircle size={13} className="animate-spin" /> {pendingLabel}
        </>
      ) : (
        children
      )}
    </Button>
  );
}
