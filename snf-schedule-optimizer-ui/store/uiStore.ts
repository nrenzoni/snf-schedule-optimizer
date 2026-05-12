import { create } from "zustand";

interface UIState {
  isConfigModalOpen: boolean;
  isSummaryModalOpen: boolean;

  openConfigModal: () => void;
  closeConfigModal: () => void;
  openSummaryModal: () => void;
  closeSummaryModal: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  isConfigModalOpen: false,
  isSummaryModalOpen: false,

  openConfigModal: () => set({ isConfigModalOpen: true }),
  closeConfigModal: () => set({ isConfigModalOpen: false }),
  openSummaryModal: () => set({ isSummaryModalOpen: true }),
  closeSummaryModal: () => set({ isSummaryModalOpen: false }),
}));
