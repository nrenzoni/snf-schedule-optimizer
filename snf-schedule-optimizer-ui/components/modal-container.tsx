import React, { useEffect, useState } from "react";

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
  // 1. State to control rendering after fade-out completes
  const [shouldRender, setShouldRender] = useState(isOpen);
  // 2. State to trigger the visual fade transition (opacity and transform)
  const [showContent, setShowContent] = useState(false);

  // 3. Effect to manage mounting/unmounting and fade transitions
  useEffect(() => {
    if (isOpen) {
      // When opening: Mount immediately and then trigger the visual fade-in
      setShouldRender(true);
      setTimeout(() => setShowContent(true), 10);
    } else {
      // When closing: Trigger the visual fade-out
      setShowContent(false);
      // After fade-out time, unmount the component entirely
      const timer = setTimeout(() => {
        setShouldRender(false);
      }, transitionDuration);
      return () => clearTimeout(timer);
    }
  }, [isOpen, transitionDuration]);

  if (!shouldRender) return null;

  // Base classes for transition control
  const baseTransition = `transition-all duration-${transitionDuration}`;
  const backdropClasses = `${baseTransition} ${showContent ? "opacity-100" : "opacity-0"}`;
  // Scale down when closing for a nice zoom effect
  const contentClasses = `${baseTransition} transform ${showContent ? "scale-100 opacity-100" : "scale-95 opacity-0"}`;

  return (
    // 1. BACKDROP CONTAINER: Handles the blur and opacity fade of the whole screen
    <div
      // Fixes: Blur, Fade, Full Screen, High Z-Index
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm ${backdropClasses}`}
      onClick={onClose} // Close on outside click
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
