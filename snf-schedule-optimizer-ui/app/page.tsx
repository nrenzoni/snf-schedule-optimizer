'use client';

import React, {useCallback, useEffect, useState} from 'react';
import {BarChart2, Brain, Calendar} from 'lucide-react';
import {ShiftModal} from "@/components/modals/ShiftModal";
import {SchedulerSettings, ScheduleSummaryModal} from "@/components/modals/ScheduleSummaryModal";
import {ScenarioAnalyzerDashboard} from "@/components/ScenarioAnalyzerDashboard";
import {MLForecastsDashboard} from "@/components/MLForecastsDashboard";
import {SchedulingConfigModal} from "@/components/modals/SchedulingConfigModal";
import {SchedulingModule} from "@/components/SchedulingModule";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {useUIStore} from "@/store/uiStore";
import {useSchedulingStore} from "@/store/schedulingStore";
import {useSchedulingInitializer} from "@/hooks/useSchedulingInitializer";
import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {useShallow} from "zustand/react/shallow";
import {cn} from "@/lib/utils";

// --- MOCKED DATA & HELPERS ---

const queryClient = new QueryClient();

const AppContent = () => {

    const uiStore = useUIStore(useShallow(state => ({
        activeModule: state.activeModule,
        setActiveModule: state.setActiveModule,
        isConfigModalOpen: state.isConfigModalOpen,
        closeConfigModal: state.closeConfigModal,
        openConfigModal: state.openConfigModal,
        isSummaryModalOpen: state.isSummaryModalOpen,
        closeSummaryModal: state.closeSummaryModal,
        openSummaryModal: state.openSummaryModal,
    })));

    const setIsOptimized = useSchedulingStore(state => state.setIsOptimized);

    // Shift Modal State Selectors (Only used by ShiftModal)
    // NOTE: This complex selector is only run for the Modals, reducing cascade risk.
    const shiftModalProps = useSchedulingStore(useShallow(state => ({
        selectedDay: state.selectedDay,
        selectedShift: state.selectedShift,
        selectedNurse: state.selectedNurse,
        closeModal: state.closeShiftModal, // Renamed for clarity in modal

        // Handlers:
        selectShift: state.selectShift,
        openNurseDetails: state.openNurseDetails,
        closeNurseDetails: state.closeNurseDetails,
        removeNurseFromShift: state.removeNurseFromShift,
        addNurseToShift: state.addNurseToShift,
    })));

    const {isAppLoading, error} = useSchedulingInitializer();
    const [isOptimizing, setIsOptimizing] = useState(false);
    // const [optimizationCount, setOptimizationCount] = useState(0);
    const [showPulse, setShowPulse] = useState(true);

    const [schedulerSettings, setSchedulerSettings] = useState<SchedulerSettings>({
        useMLForecast: false,
        useCalloutBuffer: true,
        bufferThreshold: 10,
        minRestPeriod: 10,
        maxShiftLength: 12,
        premiumWeekend: true,
        premiumHoliday: false
    });

    /**
     * 2. Type Definition for updateSchedulerSettings
     * - key: uses `keyof SchedulerSettings` to ensure it's a valid key string.
     * - value: uses `SchedulerSettings[keyof SchedulerSettings]` (an indexed access type)
     * which creates a union of all possible value types (boolean | number).
     */
    const updateSchedulerSettings = (
        key: keyof SchedulerSettings,
        value: SchedulerSettings[keyof SchedulerSettings]
    ) => {
        setSchedulerSettings(prev => ({...prev, [key]: value}));
    };
    useCallback(async () => {
        if (isOptimizing)
            return;

        setIsOptimizing(true);
        console.log("Optimization started...");

        try {
            // 1. Simulate API call for 1 second
            await new Promise(resolve => setTimeout(resolve, 1000));

            setIsOptimized(true);

            // 2. Mock a result/update (In a real app, this would trigger a re-fetch of the schedule)
            console.log("Optimization complete! Schedule updated (mock).");

        } catch (error) {
            console.error("Optimization failed:", error);
        } finally {
            setIsOptimizing(false);
        }
    }, [isOptimizing, setIsOptimized]);

    // Effect to hide pulse after 2 seconds
    useEffect(() => {
        const timer = setTimeout(() => {
            setShowPulse(false);
        }, 2000); // Hide after 2 seconds
        return () => clearTimeout(timer);
    }, []);

    // Helper for Tab Triggers
    const renderTabTrigger = (value: string, icon: React.ReactNode, label: string, isPulse = false) => {
        const isActive = uiStore.activeModule === value;

        return (
            <TabsTrigger
                value={value}
                className={cn(
                    "flex items-center space-x-2 px-4 md:px-6 py-2.5 rounded-lg text-sm font-bold h-auto transition-all",
                    "text-gray-500 hover:text-gray-700 hover:bg-gray-200/50",
                    "data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:ring-1 data-[state=active]:ring-black/5",
                    value === 'ml-forecasts' && isActive ? "data-[state=active]:text-purple-600" : "data-[state=active]:text-indigo-600",
                    isPulse && showPulse && "animate-pulse bg-purple-200 ring-2 ring-purple-500/50 hover:bg-purple-200/80"
                )}
            >
                {icon}
                <span>{label}</span>
            </TabsTrigger>
        );
    };

    return (
        <div className="p-4 md:p-8 bg-gray-50 min-h-screen font-sans">

            {/* Centralized Tabs Component (Replaces manual module selector) */}
            <div className="max-w-4xl mx-auto">
                <Tabs value={uiStore.activeModule} onValueChange={uiStore.setActiveModule} className="w-full">

                    {/* Navigation Bar */}
                    <div className="flex justify-center mb-8 relative">
                        <TabsList className="bg-gray-200 p-1.5 rounded-xl flex space-x-1 shadow-inner overflow-x-auto max-w-full z-10 h-auto">
                            {renderTabTrigger("scheduling", <Calendar size={16} />, "Scheduling")}
                            {renderTabTrigger("analyzer", <BarChart2 size={16} />, "Scenario Analyzer")}
                            {renderTabTrigger("ml-forecasts", <Brain size={16} />, "ML Forecasts", true)}
                        </TabsList>
                    </div>


                    {/*Tabs Content*/}
                    <div className="min-h-[600px]">

                        {/*Data Loading/Error Display (Remains outside TabsContent for persistence)*/}
                        {isAppLoading && (
                            <div className="text-center py-12 text-indigo-600 font-semibold text-lg flex flex-col items-center">
                                <div className="animate-spin w-6 h-6 border-4 border-t-indigo-500 border-indigo-200 rounded-full mb-4"></div>
                                Loading schedule data...
                            </div>
                        )}
                        {error && (
                            <div className="text-center py-12 text-red-600 font-semibold text-lg">
                                Error loading schedules: {error.message}
                            </div>
                        )}

                        {/*Scheduling Module Content*/}
                        <TabsContent value="scheduling" className="mt-0">
                            {!isAppLoading && (
                                <SchedulingModule
                                    // State consumed via Zustand
                                />
                            )}
                        </TabsContent>

                        <TabsContent value="analyzer" className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <ScenarioAnalyzerDashboard />
                        </TabsContent>

                        <TabsContent value="ml-forecasts" className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <MLForecastsDashboard />
                        </TabsContent>
                    </div>
                </Tabs>

                {/* Modals */}
                <ShiftModal
                    {...shiftModalProps}
                    isModalVisible={!!shiftModalProps.selectedDay}
                />
                <SchedulingConfigModal
                    settings={schedulerSettings}
                    isOpen={uiStore.isConfigModalOpen}
                    onClose={uiStore.closeConfigModal}
                    onUpdate={updateSchedulerSettings}
                />
                <ScheduleSummaryModal
                    settings={schedulerSettings}
                    isOpen={uiStore.isSummaryModalOpen}
                    onClose={uiStore.closeSummaryModal}
                />
            </div>
        </div>
    );
};


const App = () => (
    <QueryClientProvider client={queryClient}>
        <AppContent/>
    </QueryClientProvider>
);


export default App;
