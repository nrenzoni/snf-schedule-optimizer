'use client';

import React, {useEffect, useState} from 'react';
import {BarChart2, Brain, Calendar, ChevronLeft, ChevronRight, ListChecks, Settings} from 'lucide-react';
import {CalendarGrid} from "@/components/CalendarGrid";
import {useScheduling} from "@/hooks/useScheduling";
import {ShiftModal} from "@/components/ShiftModal";
import {SchedulerSettings, ScheduleSummaryModal} from "@/components/ScheduleSummaryModal";
import {ScenarioAnalyzerDashboard} from "@/components/ScenarioAnalyzerDashboard";
import {MLForecastsDashboard} from "@/components/MLForecastsDashboard";
import {SchedulingConfigModal} from "@/components/SchedulingConfigModal";

// --- MOCKED DATA & HELPERS ---

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const monthYearFormatter = new Intl.DateTimeFormat('en-US', {year: 'numeric', month: 'long'});

type ActiveModuleType = 'scheduling' | 'analyzer' | 'ml-forecasts';

// --- MAIN COMPONENT ---
const App = () => {
    // STATE: Track the active module
    const [activeModule, setActiveModule] = useState<ActiveModuleType>('scheduling');

    // STATE: Pulse visibility (for 2 seconds)
    const [showPulse, setShowPulse] = useState(true);
    const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
    const [isSummaryModalOpen, setIsSummaryModalOpen] = useState(false); // NEW STATE

    // STATE: Scheduling Configuration (Now includes new rules)
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

    const openConfigModal = () => setIsConfigModalOpen(true);
    const closeConfigModal = () => setIsConfigModalOpen(false);
    const openSummaryModal = () => setIsSummaryModalOpen(true); // NEW FUNCTION
    const closeSummaryModal = () => setIsSummaryModalOpen(false); // NEW FUNCTION

    // Effect to hide pulse after 2 seconds
    useEffect(() => {
        const timer = setTimeout(() => {
            setShowPulse(false);
        }, 2000); // Hide after 2 seconds
        return () => clearTimeout(timer);
    }, []);

    const {
        currentDate,
        calendarDays,
        selectedDay,
        isModalVisible,
        isTwoWeekView,
        toggleCalendarView,
        changeMonth,
        openShiftDetails,
        closeModal,
    } = useScheduling();

    // Custom pulse class application
    const mlForecastButtonClasses = `
        relative z-10 flex items-center space-x-2 px-4 md:px-6 py-2.5 rounded-lg text-sm font-bold transition-all duration-200 ease-out whitespace-nowrap
        ${activeModule === 'ml-forecasts'
        ? 'bg-white text-purple-600 shadow-sm cursor-default ring-1 ring-black/5'
        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50 cursor-pointer'}
        ${showPulse ? 'animate-pulse bg-purple-200 ring-2 ring-purple-500/50 hover:bg-purple-200/80' : ''}
    `;

    return (
        <div className="p-4 md:p-8 bg-gray-50 min-h-screen font-sans">

            {/* Top Level Module Selector */}
            <div className="flex justify-center mb-8 relative">
                <div
                    className="bg-gray-200 p-1.5 rounded-xl flex space-x-1 shadow-inner overflow-x-auto max-w-full z-10">
                    {/* Button 1: Scheduling */}
                    <button
                        onClick={() => setActiveModule('scheduling')}
                        disabled={activeModule === 'scheduling'}
                        className={`
                            flex items-center space-x-2 px-4 md:px-6 py-2.5 rounded-lg text-sm font-bold transition-all duration-200 ease-out whitespace-nowrap
                            ${activeModule === 'scheduling'
                            ? 'bg-white text-indigo-600 shadow-sm cursor-default ring-1 ring-black/5'
                            : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50 cursor-pointer'}
                        `}
                    >
                        <Calendar size={16}/>
                        <span>Scheduling</span>
                    </button>

                    {/* Button 2: Scenario Analyzer */}
                    <button
                        onClick={() => setActiveModule('analyzer')}
                        disabled={activeModule === 'analyzer'}
                        className={`
                            flex items-center space-x-2 px-4 md:px-6 py-2.5 rounded-lg text-sm font-bold transition-all duration-200 ease-out whitespace-nowrap
                            ${activeModule === 'analyzer'
                            ? 'bg-white text-indigo-600 shadow-sm cursor-default ring-1 ring-black/5'
                            : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50 cursor-pointer'}
                        `}
                    >
                        <BarChart2 size={16}/>
                        <span>Scenario Analyzer</span>
                    </button>

                    {/* Button 3: ML Forecasts (with Pulse) */}
                    <div className="relative">
                        <button
                            onClick={() => setActiveModule('ml-forecasts')}
                            disabled={activeModule === 'ml-forecasts'}
                            className={mlForecastButtonClasses}
                        >
                            <Brain size={16}/>
                            <span>ML Forecasts</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* CONDITIONAL CONTENT RENDERING */}
            <div className="min-h-[600px]">
                {activeModule === 'scheduling' && (
                    // WRAPPER FOR TRANSITION
                    <div key="scheduling" className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                        {/* --- EXISTING SCHEDULING MODULE --- */}
                        <div className="max-w-5xl mx-auto bg-white shadow-xl rounded-xl p-4 sm:p-6 mb-6">
                            <header className="flex justify-between items-center mb-6 border-b pb-4">
                                <button
                                    onClick={() => changeMonth(-1)}
                                    disabled={isTwoWeekView}
                                    className={`p-2 rounded-full text-gray-700 hover:bg-gray-100 transition duration-150 ${isTwoWeekView ? 'opacity-30 cursor-not-allowed' : ''}`}
                                >
                                    <ChevronLeft size={24}/>
                                </button>

                                <h2 className="text-2xl sm:text-3xl font-bold text-gray-800 tracking-tight">
                                    {monthYearFormatter.format(currentDate)}
                                </h2>

                                <div className="flex items-center space-x-2">
                                    <button
                                        onClick={openSummaryModal}
                                        className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200 bg-white text-indigo-600 hover:bg-indigo-50 border-indigo-200 flex items-center gap-1`}
                                    >
                                        <ListChecks size={16}/>
                                        Summary
                                    </button>

                                    <button
                                        onClick={openConfigModal}
                                        className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200 bg-white text-gray-700 hover:bg-gray-50 border-gray-200 flex items-center gap-1`}
                                    >
                                        <Settings size={16}/>
                                        Configure
                                    </button>

                                    <button
                                        onClick={toggleCalendarView}
                                        className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200
                                        ${isTwoWeekView
                                            ? 'bg-indigo-600 text-white hover:bg-indigo-700 border-transparent'
                                            : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-200'
                                        }`}
                                    >
                                        {isTwoWeekView ? 'View: 2 Week' : 'View: Month'}
                                    </button>

                                    <button
                                        onClick={() => changeMonth(1)}
                                        disabled={isTwoWeekView}
                                        className={`p-2 rounded-full text-gray-700 hover:bg-gray-100 transition duration-150 ${isTwoWeekView ? 'opacity-30 cursor-not-allowed' : ''}`}
                                    >
                                        <ChevronRight size={24}/>
                                    </button>
                                </div>
                            </header>

                            {/* Weekday Names */}
                            <div
                                className="grid grid-cols-7 text-center font-semibold text-xs uppercase tracking-wide text-gray-500 mb-2">
                                {DAYS_OF_WEEK.map(day => (
                                    <div key={day} className="py-2">{day}</div>
                                ))}
                            </div>

                            {/* Calendar Grid Component */}
                            <CalendarGrid
                                calendarDays={calendarDays}
                                openShiftDetails={openShiftDetails}
                                isTwoWeekView={isTwoWeekView}
                                selectedDayDateString={selectedDay?.dateString || null}
                            />

                            {/* Legend */}
                            <div
                                className="mt-8 pt-4 border-t flex flex-wrap justify-center gap-6 text-sm text-gray-600">
                                <div className="flex items-center space-x-2">
                                    <span className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></span>
                                    <span>100% HPRD Covered</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <span className="w-3 h-3 rounded-full bg-red-500 shadow-sm"></span>
                                    <span>&lt;100% HPRD Covered</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {activeModule === 'analyzer' && (
                    // WRAPPER FOR TRANSITION
                    <div key="analyzer" className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <ScenarioAnalyzerDashboard/>
                    </div>
                )}

                {activeModule === 'ml-forecasts' && (
                    // WRAPPER FOR TRANSITION
                    <div key="ml-forecasts" className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <MLForecastsDashboard/>
                    </div>
                )}
            </div>

            {/* Shift Details Modal Component */}
            <ShiftModal
                selectedDay={selectedDay}
                isModalVisible={isModalVisible}
                closeModal={closeModal}
            />

            {/* Scheduler Configuration Modal */}
            <SchedulingConfigModal
                settings={schedulerSettings}
                isOpen={isConfigModalOpen}
                onClose={closeConfigModal}
                onUpdate={updateSchedulerSettings}
            />

            {/* Schedule Summary Modal */}
            <ScheduleSummaryModal
                settings={schedulerSettings}
                isOpen={isSummaryModalOpen}
                onClose={closeSummaryModal}
            />
        </div>
    );
};

export default App;
