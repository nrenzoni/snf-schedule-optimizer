"use client";

import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface ModalContainerProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  // Optional: Pass through custom classes for modal size/styling
  contentClassName?: string;
}

// Define the duration in ms for transition consistency
const DEFAULT_TRANSITION_DURATION = 300;

export default function ModalContainer({
  isOpen,
  onClose,
  children,
  contentClassName = "max-w-xl", // Default size
}: ModalContainerProps) {
  const [isMounted, setIsMounted] = useState(isOpen);
  const [isVisible, setIsVisible] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }

    if (frameRef.current) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }

    if (isOpen) {
      frameRef.current = requestAnimationFrame(() => {
        setIsMounted(true);
        frameRef.current = requestAnimationFrame(() => setIsVisible(true));
      });
      return;
    }

    frameRef.current = requestAnimationFrame(() => setIsVisible(false));
    closeTimerRef.current = setTimeout(
      () => {
        setIsMounted(false);
        closeTimerRef.current = null;
      },
      DEFAULT_TRANSITION_DURATION,
    );

    return () => {
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isMounted) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMounted, onClose]);

  if (!isMounted) return null;

  const backdropClasses = isVisible
    ? "bg-black/60 opacity-100 backdrop-blur-sm"
    : "pointer-events-none bg-black/0 opacity-0 backdrop-blur-0";
  const contentClasses = isVisible
    ? "scale-100 opacity-100"
    : "scale-95 opacity-0";

  return createPortal(
    // 1. BACKDROP CONTAINER: Handles the blur and opacity fade of the whole screen
    <div
      // Fixes: Blur, Fade, Full Screen, High Z-Index
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 ease-out ${backdropClasses}`}
      onClick={onClose} // Close on outside click
      role="dialog"
      aria-modal="true"
    >
      {/* 2. MODAL CONTENT: Handles the content's scale and zoom effect */}
      <div
        // Base styling for the content box
        className={`bg-white rounded-xl shadow-2xl w-full overflow-hidden transition-all duration-300 ease-out ${contentClassName} ${contentClasses}`}
        onClick={(e) => e.stopPropagation()} // Prevent click from closing the modal
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
