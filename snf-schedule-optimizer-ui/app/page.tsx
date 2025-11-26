'use client';

import {useScheduling} from '@/hooks/useScheduling';
import {CalendarGrid} from '@/components/CalendarGrid';
import {ShiftModal} from '@/components/ShiftModal';

// Date formatter for the calendar header (e.g., 'November 2025')
const monthYearFormatter = new Intl.DateTimeFormat('en-US', {year: 'numeric', month: 'long'});

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const App = () => {
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

    return (
        <div className="p-4 md:p-8 bg-gray-50 min-h-screen">
            {/* Calendar Header */}
            <div className="max-w-4xl mx-auto bg-white shadow-xl rounded-xl p-4 sm:p-6 mb-6">
                <header className="flex justify-between items-center mb-6 border-b pb-4">

                    {/* Left Side: Month Navigator (Hidden if 2-Week View is active) */}
                    <button onClick={() => changeMonth(-1)}
                            disabled={isTwoWeekView}
                            className="p-2 rounded-full text-gray-700 hover:bg-gray-100 transition duration-150">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                             xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                  d="M15 19l-7-7 7-7"></path>
                        </svg>
                    </button>

                    <h2 className="text-3xl font-bold text-gray-800 tracking-tight">
                        {monthYearFormatter.format(currentDate)}
                    </h2>

                    {/* Right Side: Toggle Button & Month Navigator */}
                    <div className="flex items-center space-x-2">
                        <button
                            onClick={toggleCalendarView}
                            className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-md transition duration-200 
                            ${isTwoWeekView
                                ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                            }`}
                        >
                            {isTwoWeekView ? 'Full Month' : '2 Week Shift'}
                        </button>

                        <button onClick={() => changeMonth(1)}
                                disabled={isTwoWeekView}
                                className={`p-2 rounded-full text-gray-700 hover:bg-gray-100 transition duration-150 ${isTwoWeekView ? 'opacity-0 cursor-default' : ''}`}>
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                                 xmlns="http://www.w3.org/2000/svg">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                      d="M9 5l7 7-7 7"></path>
                            </svg>
                        </button>
                    </div>
                </header>

                {/* Weekday Names */}
                <div className="grid grid-cols-7 text-center font-semibold text-sm sm:text-base text-gray-600 mb-2">
                    {DAYS_OF_WEEK.map(day => (
                        <div key={day} className="py-2">{day}</div>
                    ))}
                </div>

                {/* Calendar Grid Component */}
                <CalendarGrid
                    calendarDays={calendarDays}
                    openShiftDetails={openShiftDetails}
                    selectedDayDateString={selectedDay?.dateString || null}
                />

                {/* Legend */}
                <div className="mt-6 pt-4 border-t flex flex-wrap justify-center gap-6 text-sm">
                    <div className="flex items-center space-x-2">
                        <span className="w-3 h-3 rounded-full bg-green-500"></span>
                        <span>100% HRPD Covered (GREEN)</span>
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="w-3 h-3 rounded-full bg-red-500"></span>
                        <span>&lt;100% HRPD Covered (RED)</span>
                    </div>
                </div>
            </div>

            {/* Modal Component */}
            <ShiftModal
                selectedDay={selectedDay}
                isModalVisible={isModalVisible}
                closeModal={closeModal}
            />
        </div>
    );
};

export default App;