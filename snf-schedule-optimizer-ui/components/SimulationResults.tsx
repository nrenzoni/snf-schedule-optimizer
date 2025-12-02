import React from "react";
import {AlertCircle, Download, FileText, X} from "lucide-react";

interface SimulationMetrics {
    costImpact: string;        // Used in the Projected Bar
    projectedTotal: string;    // Used in the Analysis Details table
    variance: string;          // Used in the Analysis Details table
    efficiency: string;        // Used in the Analysis Details table
}

interface SimulationResultData {
    name: string;                   // Used in the report header
    metrics: SimulationMetrics;     // Contains the nested metrics
    insight: string;                // Used in the Insight box
    // Add any other top-level properties of your simulation result here
}

interface SimulationResultsProps {
    result: SimulationResultData | null; // Can be null before data loads
    onClear: () => void;                 // Function to clear results
}

// --- COMPONENT: SimulationResults ---
export const SimulationResults = ({result, onClear}: SimulationResultsProps) => {
    if (!result) return null;

    return (
        <div
            className="mt-8 bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm animate-in slide-in-from-bottom-4 duration-500">
            <div className="bg-gray-50 border-b p-4 flex justify-between items-center">
                <div>
                    <h3 className="font-bold text-gray-800 flex items-center gap-2">
                        <FileText size={18} className="text-indigo-600"/>
                        Simulation Report: {result.name}
                    </h3>
                    <p className="text-xs text-gray-500 mt-1">Generated: {new Date().toLocaleString()}</p>
                </div>
                <div className="flex space-x-2">
                    <button
                        className="p-2 text-gray-600 hover:bg-white hover:shadow-sm rounded-lg border border-transparent hover:border-gray-200 transition">
                        <Download size={18}/>
                    </button>
                    <button onClick={onClear}
                            className="p-2 text-gray-600 hover:bg-white hover:shadow-sm rounded-lg border border-transparent hover:border-gray-200 transition">
                        <X size={18}/>
                    </button>
                </div>
            </div>

            <div className="p-6 grid md:grid-cols-2 gap-8">
                {/* Visual Representation (Mock Chart) */}
                <div className="space-y-4">
                    <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Projected Impact</h4>
                    <div className="h-48 flex items-end justify-around space-x-4 p-4 border rounded-lg bg-gray-50/50">
                        {/* Current Bar */}
                        <div className="relative w-16 bg-gray-300 rounded-t-lg transition-all hover:bg-gray-400 group"
                             style={{height: '60%'}}>
                            <div
                                className="absolute -top-6 left-0 right-0 text-center text-xs font-bold text-gray-600">Current
                            </div>
                            <div
                                className="absolute inset-0 flex items-end justify-center pb-2 opacity-0 group-hover:opacity-100 text-xs font-bold text-white transition-opacity">$1.2M
                            </div>
                        </div>
                        {/* Projected Bar */}
                        <div
                            className="relative w-16 bg-indigo-500 rounded-t-lg shadow-lg transition-all hover:bg-indigo-600 group"
                            style={{height: '85%'}}>
                            <div
                                className="absolute -top-6 left-0 right-0 text-center text-xs font-bold text-indigo-600">Proj.
                            </div>
                            <div
                                className="absolute inset-0 flex items-end justify-center pb-2 opacity-0 group-hover:opacity-100 text-xs font-bold text-white transition-opacity">
                                {result.metrics.costImpact}
                            </div>
                        </div>
                    </div>
                    <p className="text-sm text-center text-gray-500 italic">Visualizing annual cost variance</p>
                </div>

                {/* Key Metrics Table */}
                <div>
                    <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Analysis
                        Details</h4>
                    <div className="bg-white rounded-lg border divide-y">
                        <div className="p-3 flex justify-between items-center">
                            <span className="text-gray-600">Base Labor Cost</span>
                            <span className="font-mono font-medium">$1,200,000</span>
                        </div>
                        <div className="p-3 flex justify-between items-center bg-indigo-50/50">
                            <span className="text-indigo-900 font-medium">Projected Cost</span>
                            <span className="font-mono font-bold text-indigo-700">{result.metrics.projectedTotal}</span>
                        </div>
                        <div className="p-3 flex justify-between items-center">
                            <span className="text-gray-600">Variance</span>
                            <span className="font-mono font-medium text-red-500">+{result.metrics.variance}</span>
                        </div>
                        <div className="p-3 flex justify-between items-center">
                            <span className="text-gray-600">Efficiency Score</span>
                            <span className="font-mono font-medium">{result.metrics.efficiency}</span>
                        </div>
                    </div>

                    <div
                        className="mt-4 p-3 bg-yellow-50 text-yellow-800 text-sm rounded-lg border border-yellow-100 flex items-start space-x-2">
                        <AlertCircle size={16} className="mt-0.5 flex-shrink-0"/>
                        <p><strong>Insight:</strong> {result.insight}</p>
                    </div>
                </div>
            </div>
        </div>
    );
};