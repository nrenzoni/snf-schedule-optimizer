"use client";

import React, {useEffect, useState} from "react";
import {AnimatePresence, motion} from "framer-motion";
import {Brain, Calculator, Calendar, CheckCircle2, Coffee, Users} from "lucide-react";

// 1. DYNAMIC MESSAGES
// A mix of technical steps and "fun" SNF-specific personality
const LOADING_PHASES = [
    {text: "Ingesting staff constraints...", icon: Users},
    {text: "Calculating geometric optimality...", icon: Calculator},
    {text: "Balancing RN/LPN ratios...", icon: Brain},
    {text: "Negotiating with the weekend crew...", icon: Users},
    {text: "Optimizing for 5-star rating...", icon: CheckCircle2},
    {text: "Solving linear programming variables...", icon: Calculator},
    {text: "Refueling coffee for the algorithm...", icon: Coffee},
    {text: "Checking overtime constraints...", icon: Calendar},
    {text: "Finalizing the golden schedule...", icon: CheckCircle2},
];

export default function OptimizerLoader(
    {
        isLoading = true,
        onComplete
    }: {
        isLoading: boolean;
        onComplete?: () => void
    }) {
    const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);
    const [shuffledPhases] = useState(() => [...LOADING_PHASES]);

    // Cycle through messages
    useEffect(() => {
        if (!isLoading) return;

        const interval = setInterval(() => {
            setCurrentPhaseIndex((prev) => (prev + 1) % shuffledPhases.length);
        }, 2000); // Change message every 2 seconds

        return () => clearInterval(interval);
    }, [isLoading, shuffledPhases]);

    useEffect(() => {
        if (!isLoading) {
            onComplete?.();
        }
    }, [isLoading, onComplete]);

    // Helper to get the current phase object
    const activePhase = shuffledPhases[currentPhaseIndex];
    const ActiveIcon = activePhase.icon;

    if (!isLoading) return null;

    return (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#F4F6F8]/90">
            <div className="relative w-full max-w-md rounded-lg border border-[#E0E0E0] bg-white p-8 text-center shadow-sm">

                {/* ANIMATED ORBITING ICONS (Visual Chaos -> Order) */}
                <div className="relative flex items-center justify-center h-24 mb-6">
                    <motion.div
                        animate={{rotate: 360}}
                        transition={{duration: 8, repeat: Infinity, ease: "linear"}}
                        className="absolute inset-0 border-2 border-dashed rounded-full border-primary/20"
                    />
                    <motion.div
                        animate={{rotate: -360}}
                        transition={{duration: 12, repeat: Infinity, ease: "linear"}}
                        className="absolute inset-4 border-2 border-dashed rounded-full border-primary/40"
                    />

                    {/* Central Pulsing Icon */}
                    <motion.div
                        key={activePhase.text}
                        initial={{scale: 0.5, opacity: 0}}
                        animate={{scale: 1, opacity: 1}}
                        exit={{scale: 0.5, opacity: 0}}
                        className="relative z-10 p-4 rounded-full bg-primary/10 text-primary"
                    >
                        <ActiveIcon className="w-10 h-10"/>
                    </motion.div>
                </div>

                {/* DYNAMIC TEXT CAROUSEL */}
                <div className="h-12 overflow-hidden relative">
                    <AnimatePresence mode="wait">
                        <motion.h3
                            key={activePhase.text}
                            initial={{y: 20, opacity: 0}}
                            animate={{y: 0, opacity: 1}}
                            exit={{y: -20, opacity: 0}}
                            transition={{duration: 0.3}}
                            className="text-lg font-semibold tracking-tight"
                        >
                            {activePhase.text}
                        </motion.h3>
                    </AnimatePresence>
                </div>

                {/* PROGRESS BAR WITH "ALIVE" EFFECT */}
                <div className="w-full h-2 mt-6 overflow-hidden rounded-full bg-secondary">
                    <motion.div
                        className="h-full bg-primary"
                        initial={{width: "0%"}}
                        animate={{
                            width: ["0%", "30%", "45%", "60%", "80%", "100%"],
                            transition: {
                                duration: 10, // Adjust based on your actual avg wait time
                                ease: "easeInOut",
                                times: [0, 0.2, 0.4, 0.5, 0.8, 1]
                            }
                        }}
                    />
                </div>

                <p className="mt-2 text-xs text-muted-foreground animate-pulse">
                    Processing Optimization Model...
                </p>
            </div>
        </div>
    );
}
