"use client";

import React, {useEffect, useMemo, useState} from "react";
import {Canvas} from "@react-three/fiber";
import {Environment, PerspectiveCamera} from "@react-three/drei";
import {a, useSpring, useSprings} from "@react-spring/three";
import {AnimatePresence, motion} from "framer-motion";

// --- CONFIGURATION ---
const GRID_SIZE = 4; // 4x4 Grid
const SPACING = 0.6; // Tighter spacing for a compact grid
const BLOCK_SIZE = 0.5; // Smaller blocks to fit middle 1/3
const SCATTER_RADIUS = 3.5; // Constrained to middle of screen (approx 1/3 height)

const LOADING_PHASES = [
    "Ingesting staff constraints...",
    "Calculating geometric optimality...",
    "Balancing RN/LPN ratios...",
    "Fitting puzzle pieces together...",
    "Solving linear programming variables...",
    "Checking overtime constraints...",
    "Finalizing the golden schedule...",
];

const seededValue = (seed: number) => {
    const next = Math.sin(seed * 12.9898) * 43758.5453;
    return next - Math.floor(next);
};

const getDeterministicPosition = (index: number) => {
    const theta = seededValue(index + 1) * 2 * Math.PI;
    const phi = Math.acos(2 * seededValue(index + 2) - 1);
    const r = SCATTER_RADIUS * (0.7 + seededValue(index + 3) * 0.3);

    return [
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi)
    ] as [number, number, number];
};

// --- SCENE MANAGER ---
const BlocksScene = ({isLoading}: { isLoading: boolean }) => {
    const [step, setStep] = useState(0); // 0: Scatter, 1: Assemble, 2: Spin

    // 1. Calculate Grid Positions (Centered)
    const gridPositions = useMemo(() => {
        const pos: [number, number, number][] = [];
        const offset = ((GRID_SIZE - 1) * SPACING) / 2;
        for (let x = 0; x < GRID_SIZE; x++) {
            for (let y = 0; y < GRID_SIZE; y++) {
                pos.push([x * SPACING - offset, y * SPACING - offset, 0]);
            }
        }
        return pos;
    }, []);

    const count = gridPositions.length;
    // Generate random scatter positions once
    const scatteredPositions = useMemo(
        () => Array.from({length: count}, (_, index) => getDeterministicPosition(index)),
        [count]
    );

    // Random initial rotations for chaos
    const randomRotations = useMemo(() =>
            Array.from(
                {length: count},
                (_, index) => [
                    seededValue(index + 11) * Math.PI,
                    seededValue(index + 17) * Math.PI,
                    0,
                ] as [number, number, number]
            ),
        [count]);

    // 2. Animation Loop Logic
    useEffect(() => {
        if (!isLoading) {
            return;
        }

        const loop = async () => {
            // Step 1: Assemble (Aggressive Snap)
            setStep(1);
            await new Promise(r => setTimeout(r, 800)); // Wait for snap

            // Step 2: Spin (Group rotates)
            setStep(2);
            await new Promise(r => setTimeout(r, 800)); // Wait for spin

            // Step 3: Explode (Scatter)
            setStep(0);
            await new Promise(r => setTimeout(r, 600)); // Wait for explosion

            // Repeat
        };

        const interval = setInterval(loop, 2500); // Total loop duration
        loop(); // Start immediately

        return () => clearInterval(interval);
    }, [isLoading]);


    // 3. Springs for Individual Blocks (Position & Local Rotation)
    const [blockSprings] = useSprings(count, (i) => {
        const isAssembled = step >= 1; // Assembled during step 1 and 2
        return {
            position: isAssembled ? gridPositions[i] : scatteredPositions[i],
            rotation: isAssembled ? [0, 0, 0] : randomRotations[i], // Align when assembled
            config: {
                mass: 1,
                tension: isAssembled ? 280 : 400, // Higher tension = Aggressive snap/explode
                friction: isAssembled ? 25 : 30 // Low friction = slight overshoot/bounce
            },
            delay: isAssembled ? i * 20 : 0, // Stagger slightly on assemble, explode instantly
        };
    }, [step, gridPositions, scatteredPositions, randomRotations]);


    // 4. Spring for the Entire Group (The "Spin")
    const {rotationY} = useSpring({
        rotationY: step === 2 ? Math.PI : 0,
        config: {mass: 1, tension: 180, friction: 12}, // Springy spin
    });

    // Colors
    const colors = useMemo(() =>
            new Array(count).fill(0).map((_, i) => i % 2 === 0 ? "#168039" : "#dfffea"),
        [count]);

    return (
        <a.group rotation-y={rotationY}>
            {blockSprings.map((props, i) => (
                <a.mesh
                    key={i}
                    position={props.position as never}
                    rotation={props.rotation as never}
                    castShadow
                    receiveShadow
                >
                    <boxGeometry args={[BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE]}/>
                    <meshStandardMaterial
                        color={colors[i]}
                        roughness={0.2}
                        metalness={0.8}
                    />
                </a.mesh>
            ))}
        </a.group>
    );
};

// --- MAIN EXPORT ---
export default function ThreeDAssemblyLoader({
  isLoading,
}: {
  isLoading: boolean;
}) {
    const [msgIndex, setMsgIndex] = useState(0);

    useEffect(() => {
        if (!isLoading) return;
        const interval = setInterval(() => {
            setMsgIndex((prev) => (prev + 1) % LOADING_PHASES.length);
        }, 2000);
        return () => clearInterval(interval);
    }, [isLoading]);

    return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          key="loader-overlay"
          // Define fade in/out states
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          // Added z-[100] to ensure it's on top of everything
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-background/95"
        >

          {/* 3D Container */}
          <div className="w-full h-[400px] relative flex items-center justify-center">
            {/* We still conditionally render Canvas so WebGL unmounts instantly on exit,
                saving resources while the background fades out smoothly */}
             {isLoading && (
                <Canvas shadows dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
                  <PerspectiveCamera makeDefault position={[0, 0, 10]} fov={45} />
                  <ambientLight intensity={0.5} />
                  <spotLight position={[10, 10, 10]} angle={0.3} penumbra={1} intensity={1.5} castShadow />
                  <pointLight position={[-10, -5, -5]} intensity={1} color="#168039"/>

                  {/* Pass isLoading down so the scene knows to stop animating */}
                  <BlocksScene isLoading={isLoading} />

                  <Environment preset="city" />
                </Canvas>
             )}
          </div>

          {/* Text Overlay */}
          {/* Wrapped in motion.div to fade out slightly faster than background */}
          <motion.div
             exit={{ opacity: 0, y: 10 }}
             transition={{ duration: 0.3 }}
             className="absolute bottom-1/4 flex flex-col items-center w-full text-center pointer-events-none"
          >
            <div className="h-8 overflow-hidden relative w-full">
                <AnimatePresence mode="wait">
                <motion.p
                    key={msgIndex}
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: -20, opacity: 0 }}
                    className="text-lg font-semibold tracking-wide text-foreground"
                >
                    {LOADING_PHASES[msgIndex]}
                </motion.p>
                </AnimatePresence>
            </div>

            <div className="mt-4 h-1 w-48 overflow-hidden rounded-full bg-muted">
                 <motion.div
                    className="h-full bg-primary"
                    initial={{ width: "0%" }}
                    animate={{ width: "100%" }}
                    transition={{ duration: 8, ease: "linear", repeat: Infinity }}
                 />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
