"use client";

import React, { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface ModalContainerProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  contentClassName?: string;
  disableClose?: boolean;
}

export default function ModalContainer({
  isOpen,
  onClose,
  children,
  contentClassName = "max-w-xl",
  disableClose = false,
}: ModalContainerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prevOpenRef = useRef(isOpen);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const wasOpen = prevOpenRef.current;
    prevOpenRef.current = isOpen;

    if (isOpen && (wasOpen !== isOpen || !dialog.open)) {
      if (disableClose) {
        dialog.showModal();
        const handler = (e: Event) => {
          if (e instanceof KeyboardEvent && e.key === "Escape") {
            e.preventDefault();
          }
        };
        dialog.addEventListener("keydown", handler, { once: false });
        return () => {
          dialog.removeEventListener("keydown", handler);
        };
      } else {
        dialog.showModal();
      }
    } else if (!isOpen && dialog.open) {
      dialog.close();
    }
  }, [isOpen, disableClose]);

  return (
    <dialog
      ref={dialogRef}
      onClose={() => {
        if (!disableClose) onClose();
      }}
      className={cn(
        "app-modal-surface backdrop:bg-foreground/35 backdrop:backdrop-blur-sm open:animate-in open:fade-in open:zoom-in-95",
        contentClassName,
      )}
      onClick={(e) => {
        if (e.target === dialogRef.current && !disableClose) {
          onClose();
        }
      }}
    >
      <div className="p-4">{children}</div>
    </dialog>
  );
}
