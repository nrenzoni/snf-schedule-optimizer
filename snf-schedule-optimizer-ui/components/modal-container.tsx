import React from "react";

interface ModalContainerProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  // Optional: Pass through custom classes for modal size/styling
  contentClassName?: string;
  // Define transition duration once
  transitionDuration?: number;
}

// Define the duration in ms for transition consistency
const DEFAULT_TRANSITION_DURATION = 300;

export default function ModalContainer({
  isOpen,
  onClose,
  children,
  contentClassName = "max-w-xl", // Default size
  transitionDuration = DEFAULT_TRANSITION_DURATION,
}: ModalContainerProps) {
  if (!isOpen) return null;

  // Base classes for transition control
  const baseTransition = `transition-all duration-${transitionDuration}`;
  const backdropClasses = `${baseTransition} opacity-100`;
  // Scale down when closing for a nice zoom effect
  const contentClasses = `${baseTransition} transform scale-100 opacity-100`;

  return (
    // 1. BACKDROP CONTAINER: Handles the blur and opacity fade of the whole screen
    <div
      // Fixes: Blur, Fade, Full Screen, High Z-Index
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm ${backdropClasses}`}
      onClick={onClose} // Close on outside click
      role="dialog"
      aria-modal="true"
    >
      {/* 2. MODAL CONTENT: Handles the content's scale and zoom effect */}
      <div
        // Base styling for the content box
        className={`bg-white rounded-xl shadow-2xl w-full overflow-hidden ${contentClassName} ${contentClasses}`}
        onClick={(e) => e.stopPropagation()} // Prevent click from closing the modal
      >
        {children}
      </div>
    </div>
  );
}
