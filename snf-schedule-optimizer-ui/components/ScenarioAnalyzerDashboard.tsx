import React, {useState} from "react";
import {Activity, ArrowRight, DollarSign, PieChart, Play, TrendingUp, Users} from "lucide-react";
import {ModalType} from "@/types/ModalType";
import {SimulationConfigModal} from "@/components/SimulationConfigModal";

// 2. Define the interface for the modalConfig state
interface ModalConfig {
    isOpen: boolean;
    type: ModalType | null; // The type must be one of the defined ModalType.ts strings or null
}

interface SimulationResult {
    name: string;
    metrics: {
        costImpact: string;
        projectedTotal: string;
        variance: string;
        efficiency: string;
    };
    insight: string;
}

function SimulationResults(props: { result: SimulationResult, onClear: () => void }) {
    return null;
}

// --- COMPONENT: ScenarioAnalyzerDashboard (Existing) ---
export const ScenarioAnalyzerDashboard = () => {
    const [modalConfig, setModalConfig] = useState<ModalConfig>({isOpen: false, type: null});

    interface WageImpactParams {
        wageIncrease: string; // Used as a string and parsed to float inside the function
    }

    interface CensusImpactParams {
        censusChange: number; // Used as a number
    }

    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface AgencyReductionParams {
        // Maybe an empty object, or specific props like 'targetReductionPercent: number'
    }

    type SimulationParams = WageImpactParams | CensusImpactParams | AgencyReductionParams;

    const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);

    const openSimulation = (type: ModalType) => setModalConfig({isOpen: true, type});
    const closeSimulation = () => setModalConfig({...modalConfig, isOpen: false});

    const runSimulation = (type: ModalType | null, params: SimulationParams) => {
        // Mock calculation logic for demo purposes
        let result: SimulationResult = {
            name: '',
            metrics: {costImpact: '', projectedTotal: '', variance: '', efficiency: ''},
            insight: ''
        };

        if (type === 'WAGE_IMPACT') {
            const wageParams = params as WageImpactParams;
            const increase = parseFloat(wageParams.wageIncrease);
            const base = 1200000;
            const projected = base * (1 + increase / 100);

            result = {
                name: `Wage Increase Impact (${wageParams.wageIncrease}%)`,
                metrics: {
                    costImpact: `+${increase}%`,
                    projectedTotal: `$${(projected / 1000000).toFixed(2)}M`,
                    variance: `$${((projected - base) / 1000).toFixed(0)}k`,
                    efficiency: '94.2%'
                },
                insight: `Increasing wages by ${wageParams.wageIncrease}% improves retention probability by estimated 12% but exceeds Q4 budget.`
            };
        } else if (type === 'CENSUS_IMPACT') {
            // Confirm type locally for safe access
            const censusParams = params as CensusImpactParams;

            result = {
                name: `Census Drop Analysis (${censusParams.censusChange})`,
                metrics: {
                    costImpact: '-4%',
                    projectedTotal: '$1.15M',
                    variance: '-$50k',
                    efficiency: '88.5%'
                },
                insight: `Dropping census by ${Math.abs(censusParams.censusChange)} residents spikes HPPD to 4.2, suggesting overstaffing unless shifts are cut.`
            };
        } else if (type === 'AGENCY_REDUCTION') {
            result = {
                name: 'Agency Reduction Plan',
                metrics: {
                    costImpact: '-8%',
                    projectedTotal: '$1.10M',
                    variance: '-$100k',
                    efficiency: '98.1%'
                },
                insight: 'Converting 50% of agency usage to internal OT yields significant savings.'
            };
        }

        setSimulationResult(result);
    };

    const metrics = [
        {
            label: 'Total Labor Spend (MTD)',
            value: '$142,500',
            trend: '+4.2%',
            icon: DollarSign,
            color: 'text-green-600',
            trendColor: 'text-red-500'
        },
        {
            label: 'Agency Utilization',
            value: '18.5%',
            trend: '-2.1%',
            icon: Users,
            color: 'text-indigo-600',
            trendColor: 'text-green-500'
        },
        {
            label: 'Avg HPPD',
            value: '3.82',
            trend: 'Target: 3.6',
            icon: Activity,
            color: 'text-blue-600',
            trendColor: 'text-gray-500'
        },
        {
            label: 'Overtime %',
            value: '8.4%',
            trend: 'Target: <5%',
            icon: PieChart,
            color: 'text-orange-600',
            trendColor: 'text-orange-500'
        },
    ];

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            {/* Header / KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {metrics.map((kpi, idx) => (
                    <div key={idx}
                         className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-between hover:shadow-md transition">
                        <div className="flex justify-between items-start mb-2">
                            <span
                                className="text-gray-500 text-xs font-bold uppercase tracking-wider">{kpi.label}</span>
                            <kpi.icon size={18} className={kpi.color}/>
                        </div>
                        <div>
                            <span className="text-2xl font-bold text-gray-900">{kpi.value}</span>
                            <span className={`text-xs ml-2 font-medium ${kpi.trendColor}`}>{kpi.trend}</span>
                        </div>
                    </div>
                ))}
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                {/* Simulation Launcher */}
                <div className="lg:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h3 className="font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <Play size={18} className="text-indigo-600"/>
                        Run New Simulation
                    </h3>
                    <div className="space-y-3">
                        <button
                            onClick={() => openSimulation('WAGE_IMPACT')}
                            className="w-full text-left p-3 rounded-lg border hover:border-indigo-300 hover:bg-indigo-50 transition group"
                        >
                            <div className="flex justify-between items-center">
                                <span className="font-medium text-gray-700 group-hover:text-indigo-700">Wage Impact Analysis</span>
                                <ArrowRight size={16} className="text-gray-400 group-hover:text-indigo-500"/>
                            </div>
                            <p className="text-xs text-gray-500 mt-1">Model budget changes vs rate hikes</p>
                        </button>

                        <button
                            onClick={() => openSimulation('CENSUS_IMPACT')}
                            className="w-full text-left p-3 rounded-lg border hover:border-indigo-300 hover:bg-indigo-50 transition group"
                        >
                            <div className="flex justify-between items-center">
                                <span className="font-medium text-gray-700 group-hover:text-indigo-700">Census Volatility</span>
                                <ArrowRight size={16} className="text-gray-400 group-hover:text-indigo-500"/>
                            </div>
                            <p className="text-xs text-gray-500 mt-1">HPPD adjustments based on occupancy</p>
                        </button>

                        <button
                            onClick={() => openSimulation('AGENCY_REDUCTION')}
                            className="w-full text-left p-3 rounded-lg border hover:border-indigo-300 hover:bg-indigo-50 transition group"
                        >
                            <div className="flex justify-between items-center">
                                <span className="font-medium text-gray-700 group-hover:text-indigo-700">Agency Reduction Strategy</span>
                                <ArrowRight size={16} className="text-gray-400 group-hover:text-indigo-500"/>
                            </div>
                            <p className="text-xs text-gray-500 mt-1">Cost benefit of internal hiring</p>
                        </button>
                    </div>
                </div>

                {/* Main Content Area (Results or Placeholder) */}
                <div className="lg:col-span-2">
                    {simulationResult ? (
                        <SimulationResults result={simulationResult} onClear={() => setSimulationResult(null)}/>
                    ) : (
                        <div
                            className="h-full min-h-[300px] bg-gray-50 rounded-xl border-2 border-dashed border-gray-200 flex flex-col items-center justify-center text-center p-8">
                            <div className="bg-white p-4 rounded-full shadow-sm mb-4">
                                <TrendingUp size={32} className="text-gray-300"/>
                            </div>
                            <h3 className="text-gray-600 font-medium">No Active Simulation</h3>
                            <p className="text-gray-400 text-sm mt-2 max-w-xs">Select a simulation type from the left to
                                model financial and operational scenarios.</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Modal for Configuration */}
            <SimulationConfigModal
                type={modalConfig.type}
                isOpen={modalConfig.isOpen}
                onClose={closeSimulation}
                onRun={runSimulation}
            />
        </div>
    );
};