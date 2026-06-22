import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Activity, IndianRupee, Percent, ShieldAlert, SlidersHorizontal, BrainCircuit } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [summary, setSummary] = useState({ policy_count: 0, avg_or: 0, total_gwp: 0, avg_discount: 0 });
  const [simulation, setSimulation] = useState({ waterfall: [], shap_breakdown: [], final_or: 0 });
  const [loading, setLoading] = useState(true);

  const [filters, setFilters] = useState({ fuel_type: [], segment_tier: [] });
  const [dials, setDials] = useState({ discount: 0.70, commission: 0.20 });

  const fetchData = async () => {
    setLoading(true);
    try {
      const payload = { ...filters, requested_discount: dials.discount, commission_rate: dials.commission };
      const [sumRes, simRes] = await Promise.all([
        axios.post(`${API_BASE}/cohort/summary`, payload),
        axios.post(`${API_BASE}/simulate`, payload)
      ]);
      setSummary(sumRes.data);
      setSimulation(simRes.data);
    } catch (err) {
      console.error("API Error:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    const timer = setTimeout(() => fetchData(), 300);
    return () => clearTimeout(timer);
  }, [filters, dials]);

  const toggleFilter = (category, value) => {
    setFilters(prev => ({
      ...prev,
      [category]: prev[category].includes(value) ? prev[category].filter(i => i !== value) : [...prev[category], value]
    }));
  };

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <div className="w-72 bg-white border-r border-slate-200 p-6 shadow-sm flex flex-col h-screen overflow-y-auto">
        <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center">
          <ShieldAlert className="w-5 h-5 mr-2 text-indigo-600" /> Cohort Filters
        </h2>
        
        <div className="mb-6">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Fuel Type</h3>
          {['Petrol', 'Diesel', 'Electric', 'CNG'].map(f => (
            <label key={f} className="flex items-center space-x-2 text-sm text-slate-700 cursor-pointer mb-2">
              <input type="checkbox" className="rounded text-indigo-600" checked={filters.fuel_type.includes(f)} onChange={() => toggleFilter('fuel_type', f)} />
              <span>{f}</span>
            </label>
          ))}
        </div>

        <div className="mb-8">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Segment</h3>
          {['MARUTI', 'HYUNDAI', 'TATA', 'PREMIUM1', 'PREMIUM2'].map(s => (
            <label key={s} className="flex items-center space-x-2 text-sm text-slate-700 cursor-pointer mb-2">
              <input type="checkbox" className="rounded text-indigo-600" checked={filters.segment_tier.includes(s)} onChange={() => toggleFilter('segment_tier', s)} />
              <span>{s}</span>
            </label>
          ))}
        </div>

        {/* The Underwriting Dials */}
        <div className="pt-6 border-t border-slate-100 mt-auto">
          <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
            <SlidersHorizontal className="w-5 h-5 mr-2 text-rose-500" /> UW Dials
          </h2>
          
          <div className="mb-5">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-slate-600 font-medium">Requested Discount</span>
              <span className="text-indigo-600 font-bold">{(dials.discount * 100).toFixed(1)}%</span>
            </div>
            <input type="range" min="0" max="0.95" step="0.01" value={dials.discount} onChange={(e) => setDials({...dials, discount: parseFloat(e.target.value)})} className="w-full accent-indigo-600" />
          </div>

          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-slate-600 font-medium">Commission & BSE</span>
              <span className="text-amber-600 font-bold">{(dials.commission * 100).toFixed(1)}%</span>
            </div>
            <input type="range" min="0" max="0.40" step="0.01" value={dials.commission} onChange={(e) => setDials({...dials, commission: parseFloat(e.target.value)})} className="w-full accent-amber-500" />
          </div>
        </div>
      </div>

      {/* Main Area */}
      <div className="flex-1 p-8 overflow-y-auto">
        <header className="mb-8 flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Portfolio Explorer</h1>
            <p className="text-slate-500 text-sm mt-1">Live simulation on {summary.policy_count.toLocaleString()} historical policies.</p>
          </div>
          <div className={`px-4 py-2 rounded-lg font-bold text-lg border shadow-sm ${simulation.final_or > 1.0 ? 'bg-rose-50 text-rose-600 border-rose-200' : 'bg-emerald-50 text-emerald-600 border-emerald-200'}`}>
            Simulated OR: {(simulation.final_or * 100).toFixed(2)}%
          </div>
        </header>

        {/* Existing Historical KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 opacity-75">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex items-center">
            <Activity className="w-6 h-6 text-slate-400 mr-4" />
            <div><p className="text-xs font-medium text-slate-400 uppercase">Historical OR</p><p className="text-xl font-bold text-slate-700">{(summary.avg_or * 100).toFixed(2)}%</p></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex items-center">
            <IndianRupee className="w-6 h-6 text-slate-400 mr-4" />
            <div><p className="text-xs font-medium text-slate-400 uppercase">Earned GWP</p><p className="text-xl font-bold text-slate-700">₹ {(summary.total_gwp / 100000).toFixed(2)} L</p></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex items-center">
            <Percent className="w-6 h-6 text-slate-400 mr-4" />
            <div><p className="text-xs font-medium text-slate-400 uppercase">Historical Discount</p><p className="text-xl font-bold text-slate-700">{(summary.avg_discount * 100).toFixed(2)}%</p></div>
          </div>
        </div>

        {/* --- NEW: The Dual Chart Layout --- */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          
          {/* Commercial Math Waterfall */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col">
            <div className="mb-4">
              <h3 className="text-lg font-bold text-slate-800 flex items-center">
                <IndianRupee className="w-5 h-5 mr-2 text-emerald-500" /> Commercial Execution
              </h3>
              <p className="text-sm text-slate-500">Premium vs Discount vs Expected Loss</p>
            </div>
            
            <div className="flex-1 min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={simulation.waterfall} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <XAxis dataKey="name" tick={{fontSize: 12}} />
                  <Tooltip formatter={(value) => `₹ ${value}`} cursor={{fill: '#f8fafc'}}/>
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  <Bar dataKey="Amount" radius={[4, 4, 4, 4]}>
                    {simulation.waterfall.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ML Risk Drivers Chart */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col">
            <div className="mb-4">
              <h3 className="text-lg font-bold text-slate-800 flex items-center">
                <BrainCircuit className="w-5 h-5 mr-2 text-blue-500" /> ML Risk Drivers (Cohort Level)
              </h3>
              <p className="text-sm text-slate-500">SHAP Explainability: What is driving the Expected Loss?</p>
            </div>

            <div className="flex-1 min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart layout="vertical" data={simulation.shap_breakdown} margin={{ top: 20, right: 30, left: 100, bottom: 5 }}>
                  <XAxis type="number" tick={{fontSize: 12}} />
                  <YAxis dataKey="name" type="category" width={120} tick={{fontSize: 11, fill: '#475569'}} />
                  <Tooltip formatter={(value) => `₹ ${value > 0 ? '+' : ''}${value}`} cursor={{fill: '#f8fafc'}} />
                  <ReferenceLine x={0} stroke="#cbd5e1" />
                  <Bar dataKey="impact" radius={[0, 4, 4, 0]} barSize={30}>
                    {simulation.shap_breakdown?.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}