import { CheckCircle2, XCircle } from "lucide-react";
import {
  Button,
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  useI18n,
} from "@unfour/ui";

/**
 * Popup that surfaces the outcome of a "test connection" attempt. The inline
 * footer message could not show long failure details, so the full message is
 * rendered here in a scrollable, wrapping body.
 */
export function SshTestResultDialog({
  onOpenChange,
  result,
}: {
  onOpenChange: (open: boolean) => void;
  result: { ok: boolean; message: string } | null;
}) {
  const { t } = useI18n();
  const title = result?.ok ? t("ssh.dialog.testSuccess") : t("ssh.dialog.testFailed");

  return (
    <Dialog onOpenChange={onOpenChange} open={result !== null}>
      <DialogContent className="w-[min(460px,calc(100vw-32px))]" title={title}>
        <DialogHeader>
          <DialogTitle>
            <span
              className="flex items-center gap-2"
              style={{
                color: result?.ok
                  ? "var(--u-color-success)"
                  : "var(--u-color-danger)",
              }}
            >
              {result?.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
              {title}
            </span>
          </DialogTitle>
        </DialogHeader>
        <DialogBody>
          <p className="max-h-[40vh] overflow-auto whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-[var(--u-color-text)]">
            {result?.message}
          </p>
        </DialogBody>
        <DialogFooter>
          <DialogClose asChild>
            <Button autoFocus type="button">
              {t("ssh.dialog.testClose")}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
