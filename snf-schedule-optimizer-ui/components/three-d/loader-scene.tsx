"use client";

import React, { useEffect } from "react";
import { Environment, PerspectiveCamera } from "@react-three/drei";
import BlocksScene from "@/components/three-d/blocks-scene";

export default function LoaderScene({
  isLoading,
  setReady,
}: {
  isLoading: boolean;
  setReady: React.Dispatch<React.SetStateAction<boolean>>;
}) {
  useEffect(() => {
    const timeout = window.setTimeout(() => setReady(true), 0);
    return () => window.clearTimeout(timeout);
  }, [setReady]);

  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0, 10]} fov={45} />
      <ambientLight intensity={0.5} />
      <spotLight position={[10, 10, 10]} angle={0.3} penumbra={1} intensity={1.5} castShadow />
      <pointLight position={[-10, -5, -5]} intensity={1} color="#168039" />
      <BlocksScene isLoading={isLoading} />
      <Environment preset="city" />
    </>
  );
}
