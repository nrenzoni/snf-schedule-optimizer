import { create } from "zustand";

interface UIState {
  isConfigModalOpen: boolean;
  isSummaryModalOpen: boolean;
  isTreeModalOpen: boolean;

  openConfigModal: () => void;
  closeConfigModal: () => void;
  openSummaryModal: () => void;
  closeSummaryModal: () => void;
  openTreeModal: () => void;
  closeTreeModal: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  isConfigModalOpen: false,
  isSummaryModalOpen: false,
  isTreeModalOpen: false,

  openConfigModal: () => set({ isConfigModalOpen: true }),
  closeConfigModal: () => set({ isConfigModalOpen: false }),
  openSummaryModal: () => set({ isSummaryModalOpen: true }),
  closeSummaryModal: () => set({ isSummaryModalOpen: false }),
  openTreeModal: () => set({ isTreeModalOpen: true }),
  closeTreeModal: () => set({ isTreeModalOpen: false }),
}));
