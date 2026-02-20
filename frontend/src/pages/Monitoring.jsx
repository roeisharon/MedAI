import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";
import {
  LuMessageCircle, LuFileText, LuClock, LuZap,
  LuCircleAlert, LuRefreshCw, LuActivity, LuCircleCheck
} from "react-icons/lu";

const API = "/api";

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmtUptime = (s) => {
  if (s < 60)   return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
};

const fmtMs = (ms) => {
  if (!ms && ms !== 0) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
};

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, iconColor, sub }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4 flex items-center justify-between">
      <div>
        <p className="text-xs text-gray-400 mb-1">{label}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {sub && <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>}
      </div>
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconColor}`}>
        <Icon className="w-5 h-5" />
      </div>
    </div>
  );
}

// ── Custom tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-100 rounded-xl shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────
export default function Monitoring() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/metrics`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30_000); // auto-refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // ── Latency bucket data ───────────────────────────────────────────────────
  const latencyBuckets = data ? (() => {
    const samples = data._raw_latency_samples || [];
    // Reconstruct buckets from avg/min/max since backend doesn't send raw samples
    // We use the summary stats to build a representative distribution
    const avg = data.latency_ms?.avg || 0;
    const count = data.latency_ms?.count || 0;
    // Use errors_by_type as a proxy for per-bucket if not available
    // Show the summary stats as a simple bar chart instead
    return [
      { label: "Avg",  value: avg,                    fill: "#6366f1" },
      { label: "Min",  value: data.latency_ms?.min || 0, fill: "#10b981" },
      { label: "Max",  value: data.latency_ms?.max || 0, fill: "#f59e0b" },
      { label: "P95",  value: data.latency_ms?.p95 || 0, fill: "#ef4444" },
    ].filter(b => b.value > 0);
  })() : [];

  // ── Event type pie ────────────────────────────────────────────────────────
  const pieData = data ? [
    { name: "Questions",    value: data.llm_calls,     color: "#6366f1" },
    { name: "PDFs Uploaded",value: data.pdf_uploads,   color: "#10b981" },
    { name: "Sessions",     value: data.total_sessions, color: "#f59e0b" },
  ].filter(d => d.value > 0) : [];

  // ── Error breakdown ───────────────────────────────────────────────────────
  const errorEntries = data ? Object.entries(data.errors_by_type || {}) : [];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50 px-8 py-8">

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Monitoring Dashboard</h1>
          <p className="text-sm text-gray-400 mt-0.5">System observability and usage analytics</p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <p className="text-xs text-gray-400">
              Updated {lastRefresh.toLocaleTimeString()}
            </p>
          )}
          <button
            onClick={fetchMetrics}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <LuRefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-6 flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          <LuCircleAlert className="w-4 h-4 shrink-0" />
          Could not load metrics: {error}. Is the backend running?
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !data && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white rounded-2xl border border-gray-100 h-24 animate-pulse" />
          ))}
        </div>
      )}

      {data && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Total Questions"
              value={data.llm_calls}
              icon={LuMessageCircle}
              iconColor="bg-blue-50 text-blue-500"
              sub={`${data.llm_errors} failed`}
            />
            <StatCard
              label="Sessions"
              value={data.total_sessions}
              icon={LuZap}
              iconColor="bg-teal-50 text-teal-500"
              sub={`Uptime ${fmtUptime(data.uptime_seconds)}`}
            />
            <StatCard
              label="Leaflets Uploaded"
              value={data.pdf_uploads}
              icon={LuFileText}
              iconColor="bg-violet-50 text-violet-500"
            />
            <StatCard
              label="Avg Latency"
              value={fmtMs(data.latency_ms?.avg)}
              icon={LuClock}
              iconColor="bg-amber-50 text-amber-500"
              sub={data.latency_ms?.p95 ? `P95: ${fmtMs(data.latency_ms.p95)}` : `${data.latency_ms?.count || 0} samples`}
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-2 gap-5 mb-5">

            {/* Latency breakdown */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-2 mb-5">
                <LuClock className="w-4 h-4 text-amber-500" />
                <p className="text-sm font-semibold text-gray-800">Response Latency</p>
              </div>
              {latencyBuckets.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={latencyBuckets} barSize={36}>
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false}
                      tickFormatter={(v) => fmtMs(v)} />
                    <Tooltip content={<CustomTooltip />} formatter={(v) => fmtMs(v)} />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {latencyBuckets.map((b, i) => (
                        <Cell key={i} fill={b.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-48 flex items-center justify-center text-sm text-gray-400">
                  No latency data yet
                </div>
              )}
            </div>

            {/* Event type pie */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-2 mb-5">
                <LuActivity className="w-4 h-4 text-violet-500" />
                <p className="text-sm font-semibold text-gray-800">Event Types</p>
              </div>
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="40%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v, name) => [v, name]} />
                    <Legend
                      layout="vertical"
                      align="right"
                      verticalAlign="middle"
                      iconType="circle"
                      iconSize={8}
                      formatter={(value, entry) => (
                        <span className="text-xs text-gray-600">
                          {value} <span className="font-semibold text-gray-900">{entry.payload.value}</span>
                        </span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-48 flex items-center justify-center text-sm text-gray-400">
                  No events recorded yet
                </div>
              )}
            </div>
          </div>

          {/* Bottom row */}
          <div className="grid grid-cols-2 gap-5">

            {/* LLM stats */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-2 mb-4">
                <LuZap className="w-4 h-4 text-blue-500" />
                <p className="text-sm font-semibold text-gray-800">LLM Performance</p>
              </div>
              <div className="space-y-3">
                {[
                  { label: "Total Calls",    value: data.llm_calls },
                  { label: "Successful",     value: data.llm_calls - data.llm_errors, color: "text-green-600" },
                  { label: "Failed",         value: data.llm_errors, color: "text-red-500" },
                  { label: "Success Rate",
                    value: data.llm_calls > 0
                      ? `${Math.round(((data.llm_calls - data.llm_errors) / data.llm_calls) * 100)}%`
                      : "—",
                    color: "text-blue-600"
                  },
                  { label: "Total Requests", value: data.total_requests },
                  { label: "Min Latency",    value: fmtMs(data.latency_ms?.min) },
                  { label: "Max Latency",    value: fmtMs(data.latency_ms?.max) },
                ].map(({ label, value, color }) => (
                  <div key={label} className="flex justify-between items-center py-1 border-b border-gray-50 last:border-0">
                    <span className="text-xs text-gray-500">{label}</span>
                    <span className={`text-xs font-semibold ${color || "text-gray-900"}`}>{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Errors */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-2 mb-4">
                <LuCircleAlert className="w-4 h-4 text-red-500" />
                <p className="text-sm font-semibold text-gray-800">Recent Errors</p>
              </div>
              {errorEntries.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-36 text-center">
                  <LuCircleCheck className="w-8 h-8 text-green-400 mb-2" />
                  <p className="text-sm font-medium text-gray-600">No errors recorded</p>
                  <p className="text-xs text-gray-400 mt-0.5">System running smoothly</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {errorEntries.map(([type, count]) => (
                    <div key={type} className="flex justify-between items-center bg-red-50 rounded-xl px-3 py-2">
                      <span className="text-xs text-red-700 font-medium">{type.replace(/_/g, " ")}</span>
                      <span className="text-xs font-bold text-red-600 bg-red-100 px-2 py-0.5 rounded-lg">
                        {count}×
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}