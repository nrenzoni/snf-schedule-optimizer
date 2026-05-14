"use client";

import ModalContainer from "@/components/modal-container";
import { Loader2 } from "lucide-react";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDestructive?: boolean;
  isPending?: boolean;
}

export default function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  isDestructive = false,
  isPending = false,
}: ConfirmDialogProps) {
  return (
    <ModalContainer
      isOpen={isOpen}
      onClose={onCancel}
      contentClassName="max-w-md"
      disableClose={isPending}
    >
      <div className="p-6">
        <h2 className="app-title text-lg">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="app-button-secondary"
            disabled={isPending}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={isDestructive ? "app-button-danger" : "app-button-primary"}
            disabled={isPending}
          >
            {isPending ? <Loader2 size={16} className="animate-spin" /> : null}
            {isPending ? "Working..." : confirmLabel}
          </button>
        </div>
      </div>
    </ModalContainer>
  );
}
