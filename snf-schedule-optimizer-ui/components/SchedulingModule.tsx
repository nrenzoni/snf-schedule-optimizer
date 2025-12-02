import React, {useCallback} from 'react';
import {ChevronLeft, ChevronRight, ListChecks, Settings, Zap} from 'lucide-react';
import {CalendarGrid} from "@/components/scheduling/CalendarGrid";
import {useUIStore} from "@/store/uiStore";
import {useSchedulingStore} from "@/store/schedulingStore";
import {useShallow} from "zustand/react/shallow";
import OptimizerLoader from "@/components/optimizer-loader";
import ThreeDAssemblyLoader from "@/components/three-d-assembly-loader"; // Assuming UICalendarDay is imported from here

// --- HELPERS (MUST BE COPIED OR MOVED) ---
// You should move the Spinner, DAYS_OF_WEEK, and monthYearFormatter helpers
// to a shared utility file or define them here for now.

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const monthYearFormatter = new Intl.DateTimeFormat('en-US', {year: 'numeric', month: 'long'});

const Spinner = () => (
    <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
);

// --- END HELPERS ---


// 💡 Props are removed entirely
export const SchedulingModule: React.FC = () => {

    // 1. Consume Scheduling State & Actions
    const {
        currentDate,
        calendarDays,
        selectedDay,
        isTwoWeekView,
        isOptimizing,
        toggleCalendarView,
        changeMonth,
        openShiftDetails,
        setIsOptimizing,
        triggerOptimization,
    } = useSchedulingStore(useShallow(state => ({
        currentDate: state.currentDate,
        calendarDays: state.calendarDays,
        selectedDay: state.selectedDay,
        isTwoWeekView: state.isTwoWeekView,
        isOptimizing: state.isOptimizing,
        toggleCalendarView: state.toggleCalendarView,
        changeMonth: state.changeMonth,
        openShiftDetails: state.openShiftDetails,
        setIsOptimizing: state.setIsOptimizing,
        triggerOptimization: state.triggerOptimization,
    })));

    // 2. Consume UI Modal Actions
    const {openConfigModal, openSummaryModal} = useUIStore(useShallow(state => ({
        openConfigModal: state.openConfigModal,
        openSummaryModal: state.openSummaryModal,
    })));


    // 3. Optimized Handle Optimize (Moved back to SchedulingModule for self-containment)
    const handleOptimize = useCallback(async () => {
        if (isOptimizing) return;

        setIsOptimizing(true);
        console.log("Optimization started...");

        try {
            // 1. Simulate API call for 1 second
            await new Promise(resolve => setTimeout(resolve, 4500));

            // 2. Trigger the store state change
            triggerOptimization();

            console.log("Optimization complete! Schedule updated.");

        } catch (error) {
            console.error("Optimization failed:", error);
        } finally {
            setIsOptimizing(false);
        }
    }, [isOptimizing, setIsOptimizing, triggerOptimization]); // Dependencies from store/local state are clean


    return (
        // WRAPPER FOR TRANSITION
        <div key="scheduling" className="animate-in fade-in slide-in-from-bottom-4 duration-500">

            {/* loader handled via React Portal or Fixed positioning, so it overlays automatically */}
            {/*<OptimizerLoader isLoading={isOptimizing}/>*/}
            <ThreeDAssemblyLoader isLoading={isOptimizing}/>

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
                        {/* Optimize Button */}
                        <button
                            onClick={handleOptimize}
                            disabled={isOptimizing}
                            className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm transition duration-200 flex items-center gap-2 whitespace-nowrap
                                ${isOptimizing
                                ? 'bg-indigo-400 text-white cursor-not-allowed'
                                : 'bg-indigo-600 text-white hover:bg-indigo-700'
                            }`}
                        >
                            {isOptimizing ? <Spinner/> : <Zap size={16}/>}
                            <span>{isOptimizing ? 'Optimizing...' : 'Optimize'}</span>
                        </button>

                        {/* Summary Button */}
                        <button
                            onClick={openSummaryModal}
                            className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200 bg-white text-indigo-600 hover:bg-indigo-50 border-indigo-200 flex items-center gap-1`}
                        >
                            <ListChecks size={16}/>
                            Summary
                        </button>

                        {/* Configure Button */}
                        <button
                            onClick={openConfigModal}
                            className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200 bg-white text-gray-700 hover:bg-gray-50 border-gray-200 flex items-center gap-1`}
                        >
                            <Settings size={16}/>
                            Configure
                        </button>

                        {/* View Toggle Button */}
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

                        {/* Chevron Right Button */}
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

                    {/* 🟢 Ideal: 100% and above */}
                    <div className="flex items-center space-x-2">
                        <span className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></span>
                        <span>100%+ HPRD Covered (Ideal)</span>
                    </div>

                    {/* 🟡 Warning: 70% to 99% */}
                    <div className="flex items-center space-x-2">
                        <span className="w-3 h-3 rounded-full bg-yellow-400 shadow-sm"></span>
                        <span>70% - 99% HPRD Covered (Warning)</span>
                    </div>

                    {/* 🔴 Critical: Below 70% */}
                    <div className="flex items-center space-x-2">
                        <span className="w-3 h-3 rounded-full bg-red-500 shadow-sm"></span>
                        <span>&lt;70% HPRD Covered (Critical)</span>
                    </div>
                </div>
            </div>
        </div>
    );
};