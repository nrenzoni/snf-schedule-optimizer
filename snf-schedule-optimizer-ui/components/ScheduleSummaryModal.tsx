import React from "react";
import {CheckCircle, Clock, DollarSign, Heart, ListChecks, Scale, Smile, Users, X} from "lucide-react";

export interface SchedulerSettings {
    useMLForecast: boolean;
    useCalloutBuffer: boolean;
    bufferThreshold: number;
    minRestPeriod: number;
    maxShiftLength: number;
    premiumWeekend: boolean;
    premiumHoliday: boolean;
}

interface ScheduleSummaryModalProps {
    settings: SchedulerSettings; // The configuration used to generate the summary
    isOpen: boolean;
    onClose: () => void; // Function that takes no arguments and returns nothing
}

// --- COMPONENT: ScheduleSummaryModal ---
export const ScheduleSummaryModal = ({settings, isOpen, onClose}: ScheduleSummaryModalProps) => {
    if (!isOpen) return null;

    // Mock data generation based on settings for demonstration
    const metrics = {
        // Operational Metrics
        avgCoverage: '98.5%',
        shiftsBelowThreshold: settings.useCalloutBuffer ? 2 : 7,
        restPeriodViolations: settings.minRestPeriod > 10 ? 0 : 3,
        maxShiftViolations: settings.maxShiftLength < 12 ? 1 : 0,

        // Financial Metrics
        totalLaborCost: '$1,254,000',
        totalPremiumPay: settings.premiumWeekend || settings.premiumHoliday ? '$45,200' : '$2,100',
        costPerPatientDay: '$85.45',
        overtimePercentage: '6.2%',

        // Wellbeing Metrics (NEW)
        preferenceMatch: '94%',
        teamSynergy: '87%',
        weekendFairness: 'Balanced', // or 'Skewed'
        avgConsecutiveDays: '3.4',
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4 backdrop-blur-sm animate-in fade-in duration-200">
            {/* Expanded width to max-w-6xl for 3 columns */}
            <div
                className="bg-white rounded-xl shadow-2xl w-full max-w-6xl overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="border-b p-4 flex justify-between items-center bg-indigo-600 text-white">
                    <div className="flex items-center space-x-2">
                        <ListChecks size={24}/>
                        <h3 className="font-bold text-xl">Monthly Schedule Summary</h3>
                    </div>
                    <button onClick={onClose} className="hover:bg-indigo-700 p-1 rounded-full"><X size={20}/></button>
                </div>

                {/* Changed to 3 columns grid */}
                <div className="p-6 grid lg:grid-cols-3 gap-8 max-h-[80vh] overflow-y-auto">

                    {/* COLUMN 1: Operational Metrics */}
                    <div>
                        <h4 className="text-lg font-semibold text-indigo-700 border-b pb-2 mb-4 flex items-center gap-2">
                            <CheckCircle size={18}/> Operational Compliance
                        </h4>
                        <div className="space-y-3">
                            <div className="flex justify-between p-3 bg-indigo-50 rounded-lg border border-indigo-200">
                                <span className="text-gray-700 font-medium">Avg. Daily Coverage</span>
                                <span className="font-bold text-xl text-indigo-700">{metrics.avgCoverage}</span>
                            </div>

                            <div
                                className={`flex justify-between p-3 rounded-lg border ${metrics.shiftsBelowThreshold > 5 ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
                                <div>
                                    <span className="text-gray-700 font-medium">Risk Shifts (Low Buffer)</span>
                                </div>
                                <span
                                    className={`font-bold text-xl ${metrics.shiftsBelowThreshold > 5 ? 'text-red-600' : 'text-green-600'}`}>
                                    {metrics.shiftsBelowThreshold}
                                </span>
                            </div>

                            <div
                                className={`flex justify-between p-3 rounded-lg border ${metrics.restPeriodViolations > 0 ? 'bg-yellow-50 border-yellow-200' : 'bg-white border-gray-200'}`}>
                                <div>
                                    <span className="text-gray-700 font-medium">Rest Period Violations</span>
                                </div>
                                <span
                                    className={`font-bold text-xl ${metrics.restPeriodViolations > 0 ? 'text-yellow-600' : 'text-gray-700'}`}>
                                    {metrics.restPeriodViolations}
                                </span>
                            </div>

                            <div
                                className={`flex justify-between p-3 rounded-lg border ${metrics.maxShiftViolations > 0 ? 'bg-yellow-50 border-yellow-200' : 'bg-white border-gray-200'}`}>
                                <div>
                                    <span className="text-gray-700 font-medium">Max Shift Violations</span>
                                </div>
                                <span
                                    className={`font-bold text-xl ${metrics.maxShiftViolations > 0 ? 'text-yellow-600' : 'text-gray-700'}`}>
                                    {metrics.maxShiftViolations}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* COLUMN 2: Financial Metrics */}
                    <div>
                        <h4 className="text-lg font-semibold text-indigo-700 border-b pb-2 mb-4 flex items-center gap-2">
                            <DollarSign size={18}/> Financial Impact
                        </h4>
                        <div className="space-y-3">
                            <div className="flex justify-between p-3 bg-indigo-50 rounded-lg border border-indigo-200">
                                <span className="text-gray-700 font-medium">Est. Labor Cost</span>
                                <span className="font-bold text-xl text-indigo-700">{metrics.totalLaborCost}</span>
                            </div>

                            <div className="flex justify-between p-3 bg-white rounded-lg border border-gray-200">
                                <span className="text-gray-700 font-medium">Cost Per Patient Day</span>
                                <span className="font-bold text-xl text-gray-800">{metrics.costPerPatientDay}</span>
                            </div>

                            <div className="flex justify-between p-3 bg-white rounded-lg border border-gray-200">
                                <span className="text-gray-700 font-medium">Overtime %</span>
                                <span
                                    className={`font-bold text-xl ${metrics.overtimePercentage > '5.0%' ? 'text-red-600' : 'text-green-600'}`}>
                                    {metrics.overtimePercentage}
                                </span>
                            </div>

                            <div className="flex justify-between p-3 bg-white rounded-lg border border-gray-200">
                                <div>
                                    <span className="text-gray-700 font-medium">Premium Pay</span>
                                </div>
                                <span className="font-bold text-xl text-gray-800">{metrics.totalPremiumPay}</span>
                            </div>
                        </div>
                    </div>

                    {/* COLUMN 3: Wellbeing Metrics (NEW) */}
                    <div>
                        <h4 className="text-lg font-semibold text-pink-600 border-b pb-2 mb-4 flex items-center gap-2">
                            <Heart size={18} fill="currentColor" className="text-pink-100 stroke-pink-600"/>
                            Staff Wellbeing
                        </h4>
                        <div className="space-y-3">
                            {/* Preference Match */}
                            <div className="p-3 bg-pink-50 rounded-lg border border-pink-100">
                                <div className="flex justify-between mb-1">
                                    <span className="text-gray-700 font-medium flex items-center gap-2">
                                        <Smile size={16} className="text-pink-600"/> Preferences Met
                                    </span>
                                    <span className="font-bold text-xl text-pink-700">{metrics.preferenceMatch}</span>
                                </div>
                                <div className="w-full bg-pink-200 rounded-full h-2">
                                    <div className="bg-pink-500 h-2 rounded-full"
                                         style={{width: metrics.preferenceMatch}}></div>
                                </div>
                                <p className="text-xs text-gray-500 mt-1">Ratio of shift/off requests granted.</p>
                            </div>

                            {/* Team Synergy */}
                            <div className="flex justify-between p-3 bg-white rounded-lg border border-gray-200">
                                <div>
                                    <span className="text-gray-700 font-medium flex items-center gap-2">
                                        <Users size={16}/> Team Synergy
                                    </span>
                                    <p className="text-xs text-gray-400">Preferred pairings met</p>
                                </div>
                                <span className="font-bold text-xl text-gray-800">{metrics.teamSynergy}</span>
                            </div>

                            {/* Fairness Score */}
                            <div className="flex justify-between p-3 bg-white rounded-lg border border-gray-200">
                                <div>
                                    <span className="text-gray-700 font-medium flex items-center gap-2">
                                        <Scale size={16}/> Fairness Index
                                    </span>
                                    <p className="text-xs text-gray-400">Weekend/Holiday equity</p>
                                </div>
                                <span className="font-bold text-lg text-green-600 px-2 py-0.5 bg-green-50 rounded">
                                    {metrics.weekendFairness}
                                </span>
                            </div>

                            {/* Fatigue Watch */}
                            <div className="flex justify-between p-3 bg-white rounded-lg border border-gray-200">
                                <div>
                                    <span className="text-gray-700 font-medium flex items-center gap-2">
                                        <Clock size={16}/> Fatigue Watch
                                    </span>
                                    <p className="text-xs text-gray-400">Avg consecutive days</p>
                                </div>
                                <span className="font-bold text-xl text-gray-800">{metrics.avgConsecutiveDays}</span>
                            </div>
                        </div>
                    </div>

                </div>

                <div className="bg-gray-50 p-4 rounded-b-xl flex justify-between items-center border-t">
                    <p className="text-sm text-gray-500 italic pl-2">
                        * Recommendation: High synergy score suggests strong team morale for this period.
                    </p>
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-md transition font-medium"
                    >
                        Close Summary
                    </button>
                </div>
            </div>
        </div>
    );
};