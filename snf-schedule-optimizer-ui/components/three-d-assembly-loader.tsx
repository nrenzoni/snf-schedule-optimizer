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

// --- HELPER: Random Position within constrained radius ---
const getRandomPosition = () => {
    const theta = Math.random() * 2 * Math.PI;
    const phi = Math.acos(2 * Math.random() - 1);
    // Restrict radius to keep it in the "middle 1/3" visually
    const r = SCATTER_RADIUS * (0.7 + Math.random() * 0.3);

    return [
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi) // Z-depth scatter
    ] as [number, number, number];
};

// --- 3D BLOCK COMPONENT ---
const AnimatedBlock = ({position, color, rotation}: any) => {
    return (
        <a.mesh position={position} rotation={rotation} castShadow receiveShadow>
            <boxGeometry args={[BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE]}/>
            <meshStandardMaterial
                color={color}
                roughness={0.2}
                metalness={0.8}
            />
        </a.mesh>
    );
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
    const scatteredPositions = useMemo(() => Array.from({length: count}, getRandomPosition), [count]);

    // Random initial rotations for chaos
    const randomRotations = useMemo(() =>
            Array.from({length: count}, () => [Math.random() * Math.PI, Math.random() * Math.PI, 0]),
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
    const {groupRotation} = useSpring({
        groupRotation: step === 2 ? [0, Math.PI, 0] : [0, 0, 0],
        config: {mass: 1, tension: 180, friction: 12}, // Springy spin
    });

    // Colors
    const colors = useMemo(() =>
            new Array(count).fill(0).map((_, i) => i % 2 === 0 ? "#818cf8" : "#c7d2fe"),
        [count]);

    return (
        // We rotate the whole group for the "Spin" phase
        // @ts-ignore
        <a.group rotation={groupRotation}>
            {blockSprings.map((props, i) => (
                <AnimatedBlock
                    key={i}
                    position={props.position}
                    rotation={props.rotation}
                    color={colors[i]}
                />
            ))}
        </a.group>
    );
};

// --- MAIN EXPORT ---
export default function ThreeDAssemblyLoader({isLoading}: { isLoading: boolean }) {
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
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-slate-950/90 backdrop-blur-sm"
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
                  <pointLight position={[-10, -5, -5]} intensity={1} color="#4f46e5"/>

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
                    className="text-lg font-semibold tracking-wide text-white"
                >
                    {LOADING_PHASES[msgIndex]}
                </motion.p>
                </AnimatePresence>
            </div>

            <div className="w-48 h-1 mt-4 bg-slate-800 rounded-full overflow-hidden">
                 <motion.div
                    className="h-full bg-indigo-500"
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
