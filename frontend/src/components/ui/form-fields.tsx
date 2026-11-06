import { useId, useRef, useState, type InputHTMLAttributes } from "react";
import { CalendarDays, Eye, EyeOff } from "lucide-react";

import { cn, Input } from "@/components/ui/primitives";

type DateInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "defaultValue" | "onChange"
> & {
  value?: string;
  defaultValue?: string;
};

export function isoToDisplayDate(value?: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? "");
  return match ? `${match[3]}/${match[2]}/${match[1]}` : "";
}

export function displayDateToIso(value: string) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
  if (!match) return "";
  const iso = `${match[3]}-${match[2]}-${match[1]}`;
  const date = new Date(`${iso}T00:00:00Z`);
  return !Number.isNaN(date.valueOf()) &&
    date.toISOString().slice(0, 10) === iso
    ? iso
    : "";
}

export function normalizeDisplayDate(value: string) {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export function DateInput({
  name,
  id,
  value,
  defaultValue,
  required,
  disabled,
  ...props
}: DateInputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const pickerRef = useRef<HTMLInputElement>(null);
  const [displayValue, setDisplayValue] = useState(() =>
    isoToDisplayDate(value ?? defaultValue),
  );
  const isoValue = displayDateToIso(displayValue);

  return (
    <>
      <span className="relative block">
        <Input
          {...props}
          id={inputId}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          placeholder="DD/MM/YYYY"
          aria-label={props["aria-label"] ?? "Date in DD/MM/YYYY format"}
          value={displayValue}
          required={required}
          disabled={disabled}
          pattern="(0[1-9]|[12][0-9]|3[01])\/(0[1-9]|1[0-2])\/[0-9]{4}"
          title="Enter the date as DD/MM/YYYY"
          className={`${props.className ?? ""} pr-10`}
          onChange={(event) => {
            setDisplayValue(normalizeDisplayDate(event.target.value));
            event.target.setCustomValidity("");
          }}
          onBlur={(event) => {
            event.target.setCustomValidity(
              displayValue && !isoValue
                ? "Enter a valid date as DD/MM/YYYY"
                : "",
            );
          }}
        />
        <button
          type="button"
          aria-label="Open calendar"
          title="Open calendar"
          disabled={disabled}
          className="absolute top-1/2 right-1 flex size-7 -translate-y-1/2 items-center justify-center rounded text-[#777] hover:bg-white/[0.06] hover:text-[#ddd] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => {
            const picker = pickerRef.current;
            if (!picker) return;
            if (typeof picker.showPicker === "function") picker.showPicker();
            else picker.click();
          }}
        >
          <CalendarDays size={15} />
        </button>
        <input
          ref={pickerRef}
          type="date"
          aria-hidden="true"
          tabIndex={-1}
          value={isoValue}
          disabled={disabled}
          className="pointer-events-none absolute size-px opacity-0"
          onChange={(event) =>
            setDisplayValue(isoToDisplayDate(event.target.value))
          }
        />
      </span>
      {name && (
        <input type="hidden" name={name} value={isoValue} disabled={disabled} />
      )}
    </>
  );
}

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  /** Show a strength meter under the field (for new-password inputs). */
  showStrength?: boolean;
};

/** Password field with a show/hide toggle and optional strength meter. */
export function PasswordInput({ className, showStrength = false, onChange, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const [current, setCurrent] = useState(String(props.value ?? props.defaultValue ?? ""));
  return (
    <>
      <div className="relative">
        <Input
          {...props}
          type={visible ? "text" : "password"}
          spellCheck={false}
          autoCapitalize="off"
          className={cn("pr-10", className)}
          onChange={(event) => {
            setCurrent(event.target.value);
            onChange?.(event);
          }}
        />
        <button
          type="button"
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          onClick={() => setVisible((value) => !value)}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-[#666] hover:text-[#bbb]"
        >
          {visible ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
      {showStrength && <PasswordStrength value={String(props.value ?? current)} />}
    </>
  );
}

/** Rough strength estimate for UI feedback only; the server enforces policy. */
export function passwordScore(value: string): 0 | 1 | 2 | 3 | 4 {
  if (value.length < 12) return value.length === 0 ? 0 : 1;
  let variety = 0;
  if (/[a-z]/.test(value)) variety++;
  if (/[A-Z]/.test(value)) variety++;
  if (/[0-9]/.test(value)) variety++;
  if (/[^A-Za-z0-9]/.test(value)) variety++;
  const unique = new Set(value.toLowerCase()).size;
  if (unique <= 4) return 1;
  if (value.length >= 20 || (value.length >= 16 && variety >= 3)) return 4;
  if (value.length >= 14 || variety >= 3) return 3;
  return 2;
}

export function PasswordStrength({ value }: { value: string }) {
  const score = passwordScore(value);
  const labels = ["", "Too short", "Fair", "Good", "Strong"];
  const colors = ["", "bg-rose-400", "bg-amber-300", "bg-emerald-400/70", "bg-emerald-400"];
  if (!value) return null;
  return (
    <div className="mt-2 flex items-center gap-2" aria-live="polite">
      <div className="grid flex-1 grid-cols-4 gap-1">
        {[1, 2, 3, 4].map((step) => (
          <span
            key={step}
            className={cn(
              "h-1 rounded-full transition-colors",
              step <= score ? colors[score] : "bg-white/[0.08]",
            )}
          />
        ))}
      </div>
      <span className="w-14 text-right text-[10px] text-[#888]">{labels[score]}</span>
    </div>
  );
}
