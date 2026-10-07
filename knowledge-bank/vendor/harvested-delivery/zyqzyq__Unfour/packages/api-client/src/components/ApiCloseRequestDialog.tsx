import {
  Button,
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@unfour/ui";

export function ApiCloseRequestDialog({
  onCancel,
  onDiscard,
  onSave,
  open,
  title,
}: {
  onCancel: () => void;
  onDiscard: () => void;
  onSave: () => void;
  open: boolean;
  title: string;
}) {
  return (
    <Dialog onOpenChange={(next) => !next && onCancel()} open={open}>
      <DialogContent title="Close modified request">
        <DialogHeader>
          <DialogTitle>Save changes?</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <DialogDescription>
            {title} has unsaved changes. Save before closing?
          </DialogDescription>
        </DialogBody>
        <DialogFooter>
          <Button onClick={onCancel} type="button" variant="ghost">
            Cancel
          </Button>
          <Button onClick={onDiscard} type="button" variant="outline">
            Don't Save
          </Button>
          <Button onClick={onSave} type="button">
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
