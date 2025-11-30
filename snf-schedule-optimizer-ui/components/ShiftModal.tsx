import React, {useMemo} from 'react';
import {CalendarDay, Nurse, Shift} from '@/types/scheduling';
import {useScheduling} from '@/hooks/useScheduling';
import {NurseDetailsPanel} from './NurseDetailsPanel';
import {X} from "lucide-react";

interface ShiftModalProps {
    selectedDay: CalendarDay | null;
    isModalVisible: boolean;
    closeModal: () => void;
}

const ShiftModalNew: React.FC<ShiftModalProps> = ({selectedDay, isModalVisible, closeModal}) => {
    if (!isModalVisible || !selectedDay) return null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4 backdrop-blur-sm animate-in fade-in duration-200">
            <div
                className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="bg-indigo-600 p-4 flex justify-between items-center text-white">
                    <h3 className="text-lg font-bold">Shift Details</h3>
                    <button onClick={closeModal} className="hover:bg-indigo-700 p-1 rounded">
                        <X size={20}/>
                    </button>
                </div>
                <div className="p-6">
                    <p className="text-gray-600 text-lg mb-4">
                        Date: <span
                        className="font-semibold text-gray-900">{selectedDay?.date ? selectedDay.date.toDateString() : selectedDay?.dateString}</span>
                    </p>
                    <div className="space-y-3">
                        <div className="flex justify-between p-3 bg-gray-50 rounded border">
                            <span>Coverage</span>
                            <span
                                className={`font-bold ${selectedDay.coverage === 100 ? 'text-green-600' : 'text-red-600'}`}>
                                {selectedDay.coverage}%
                            </span>
                        </div>
                        <div className="flex justify-between p-3 bg-gray-50 rounded border">
                            <span>Staff Scheduled</span>
                            <span className="font-bold text-gray-800">12 / 12</span>
                        </div>
                    </div>
                    <div className="mt-6 flex justify-end">
                        <button
                            onClick={closeModal}
                            className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition"
                        >
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export const ShiftModal: React.FC<ShiftModalProps> = ({selectedDay, isModalVisible, closeModal}) => {
    const {
        selectedShift,
        selectedNurse,
        selectShift,
        openNurseDetails,
    } = useScheduling();

    // Date formatter for the modal header (e.g., 'Nov 25, 2025')
    const modalDateFormatter = useMemo(() => new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    }), []);

    if (!selectedDay || !selectedDay.schedule) return null;

    return (
        <div
            className={`schedule-modal fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50 p-4 ${isModalVisible ? 'modal-visible' : ''}`}
            onClick={closeModal}>
            <div onClick={e => e.stopPropagation()}
                 className="bg-white rounded-xl shadow-2xl w-full max-w-4xl h-[90vh] flex transform transition-all duration-300 scale-100">

                {/* Left Panel (Shift Summary & Nurse List - Level 1) */}
                <div className="flex-grow p-6 flex flex-col min-w-[20rem]">
                    <div className="flex justify-between items-start mb-4 border-b pb-3">
                        <h3 className="text-2xl font-semibold text-gray-800">
                            Schedule: {selectedDay.date ? modalDateFormatter.format(selectedDay.date) : selectedDay.dateString}
                        </h3>
                        <button onClick={closeModal} className="text-gray-400 hover:text-gray-600">
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                                 xmlns="http://www.w3.org/2000/svg">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                      d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>

                    <div className="space-y-4 mb-4">
                        {selectedDay.schedule.shifts.map((shift: Shift) => (
                            <div key={shift.shiftName}
                                 onClick={() => selectShift(shift)}
                                 className={`p-3 rounded-lg border transition duration-150 cursor-pointer 
                              ${selectedShift?.shiftName === shift.shiftName ? 'ring-2 ring-indigo-500 shadow-lg bg-white' : 'hover:shadow-md'}
                              ${shift.isHPRDMet && selectedShift?.shiftName !== shift.shiftName ? 'bg-green-100' : ''}
                              ${!shift.isHPRDMet && selectedShift?.shiftName !== shift.shiftName ? 'bg-red-100' : ''}`}>
                                <div className="flex justify-between items-center mb-1">
                                    <p className={`font-bold text-lg ${shift.isHPRDMet ? 'text-green-700' : 'text-red-700'}`}>
                                        {shift.shiftName} Shift: {shift.isHPRDMet ? 'MET' : 'NOT MET'}
                                    </p>
                                    <span
                                        className="text-sm font-medium text-gray-500">({shift.nurses.length} Nurses)</span>
                                </div>
                                <p className="text-xs text-gray-600">
                                    Required: {shift.requiredHours.toFixed(1)} hrs |
                                    Actual: {shift.actualHours.toFixed(1)} hrs
                                </p>
                            </div>
                        ))}
                    </div>

                    {/* Nurse List (Active Shift) */}
                    <h4 className="text-xl font-medium mb-3 border-t pt-3">Nurses
                        for {selectedShift?.shiftName || 'Selected'} Shift</h4>
                    <div className="overflow-y-auto space-y-2 flex-grow pr-1">
                        {selectedShift ? (
                            selectedShift.nurses.length > 0 ? (
                                selectedShift.nurses.map((nurse: Nurse) => (
                                    <div key={nurse.id}
                                         onClick={() => openNurseDetails(nurse)}
                                         className={`p-3 border rounded-lg flex justify-between items-center cursor-pointer hover:bg-indigo-50 transition duration-150 
                                  ${selectedNurse?.id === nurse.id ? 'bg-indigo-100 border-indigo-400' : 'bg-white border-gray-200'}`}>
                                        <span className="font-medium text-gray-800">{nurse.name}</span>
                                        <span
                                            className="text-sm font-semibold text-indigo-600">{nurse.shiftHours} hrs</span>
                                    </div>
                                ))
                            ) : (
                                <p className="text-gray-500 italic">No nurses currently scheduled for this shift.</p>
                            )
                        ) : (
                            <p className="text-gray-500 italic">Select a shift above to view the nurse list.</p>
                        )}
                    </div>
                </div>

                {/* Right Panel (Nurse Details) */}
                <NurseDetailsPanel/>
            </div>

            {/* Custom CSS for Modal Fade Transition */}
            <style jsx={true}>{`
                .schedule-modal {
                    opacity: 0;
                    transition: opacity 0.3s ease-in-out;
                    pointer-events: none;
                }

                .schedule-modal.modal-visible {
                    opacity: 1;
                    pointer-events: auto;
                }
            `}</style>
        </div>
    );
};