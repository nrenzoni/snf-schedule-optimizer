"use client";

import React, { useEffect, useMemo, useState } from "react";
import { a, useSpring, useSprings } from "@react-spring/three";

const GRID_SIZE = 4;
const SPACING = 0.6;
const BLOCK_SIZE = 0.5;
const SCATTER_RADIUS = 3.5;

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
    r * Math.cos(phi),
  ] as [number, number, number];
};

export default function BlocksScene({ isLoading }: { isLoading: boolean }) {
  const [step, setStep] = useState(0);

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
  const scatteredPositions = useMemo(
    () => Array.from({ length: count }, (_, index) => getDeterministicPosition(index)),
    [count],
  );

  const randomRotations = useMemo(
    () =>
      Array.from(
        { length: count },
        (_, index) =>
          [
            seededValue(index + 11) * Math.PI,
            seededValue(index + 17) * Math.PI,
            0,
          ] as [number, number, number],
      ),
    [count],
  );

  useEffect(() => {
    if (!isLoading) {
      return;
    }

    const loop = async () => {
      setStep(1);
      await new Promise((r) => setTimeout(r, 800));

      setStep(2);
      await new Promise((r) => setTimeout(r, 800));

      setStep(0);
      await new Promise((r) => setTimeout(r, 600));
    };

    const interval = setInterval(loop, 2500);
    loop();

    return () => clearInterval(interval);
  }, [isLoading]);

  const [blockSprings] = useSprings(count, (i) => {
    const isAssembled = step >= 1;
    return {
      position: isAssembled ? gridPositions[i] : scatteredPositions[i],
      rotation: isAssembled ? [0, 0, 0] : randomRotations[i],
      config: {
        mass: 1,
        tension: isAssembled ? 280 : 400,
        friction: isAssembled ? 25 : 30,
      },
      delay: isAssembled ? i * 20 : 0,
    };
  }, [step, gridPositions, scatteredPositions, randomRotations]);

  const { rotationY } = useSpring({
    rotationY: step === 2 ? Math.PI : 0,
    config: { mass: 1, tension: 180, friction: 12 },
  });

  const colors = useMemo(
    () => new Array(count).fill(0).map((_, i) => (i % 2 === 0 ? "#168039" : "#dfffea")),
    [count],
  );

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
          <boxGeometry args={[BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE]} />
          <meshStandardMaterial color={colors[i]} roughness={0.2} metalness={0.8} />
        </a.mesh>
      ))}
    </a.group>
  );
}
