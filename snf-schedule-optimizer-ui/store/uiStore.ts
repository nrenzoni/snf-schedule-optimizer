import { create } from 'zustand';

interface UIState {
    activeModule: 'scheduling' | 'analyzer' | 'ml-forecasts';
    isConfigModalOpen: boolean;
    isSummaryModalOpen: boolean;

    setActiveModule: (module: 'scheduling' | 'analyzer' | 'ml-forecasts') => void;
    openConfigModal: () => void;
    closeConfigModal: () => void;
    openSummaryModal: () => void;
    closeSummaryModal: () => void;
}

export const useUIStore = create<UIState>((set) => ({
    activeModule: 'scheduling',
    isConfigModalOpen: false,
    isSummaryModalOpen: false,

    setActiveModule: (module) => set({ activeModule: module }),
    openConfigModal: () => set({ isConfigModalOpen: true }),
    closeConfigModal: () => set({ isConfigModalOpen: false }),
    openSummaryModal: () => set({ isSummaryModalOpen: true }),
    closeSummaryModal: () => set({ isSummaryModalOpen: false }),
}));