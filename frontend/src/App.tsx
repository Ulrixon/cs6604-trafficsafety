import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  BrainCircuit,
  Database,
  Gauge,
  Layers,
  LineChart,
  MapPinned,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Table2
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

type ViewKey = "overview" | "trends" | "analytics" | "sensitivity" | "database";

type Intersection = {
  intersection_id?: string | number;
  intersection_name?: string;
  intersection?: string;
  safety_index?: number | null;
  final_safety_index?: number | null;
  rt_si_score?: number | null;
  rt_si_index?: number | null;
  mcdm_index?: number | null;
  traffic_volume?: number | null;
  vru_index?: number | null;
  vehicle_index?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  index_type?: string;
  [key: string]: unknown;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type TrendPoint = {
  time_bin?: string;
  timestamp?: string;
  safety_index?: number | null;
  final_safety_index?: number | null;
  rt_si_score?: number | null;
  mcdm_index?: number | null;
  vru_index?: number | null;
  vehicle_index?: number | null;
  raw_crash_rate?: number | null;
  eb_crash_rate?: number | null;
  uplift_factor?: number | null;
  vehicle_count?: number | null;
  incident_count?: number | null;
  near_miss_count?: number | null;
  vru_count?: number | null;
  avg_speed?: number | null;
  speed_variance?: number | null;
  saw_score?: number | null;
  edas_score?: number | null;
  codas_score?: number | null;
  [key: string]: unknown;
};

const fallbackIntersections: Intersection[] = [
  {
    intersection_id: 1,
    intersection_name: "Main St & 1st Ave",
    safety_index: 45.2,
    traffic_volume: 15000,
    latitude: 38.8951,
    longitude: -77.0364,
    mcdm_index: 44.8,
    rt_si_score: 46.1
  },
  {
    intersection_id: 2,
    intersection_name: "Broadway & 5th St",
    safety_index: 68.5,
    traffic_volume: 22000,
    latitude: 38.9072,
    longitude: -77.0369,
    mcdm_index: 66.2,
    rt_si_score: 69.5
  },
  {
    intersection_id: 3,
    intersection_name: "Oak Rd & Pine St",
    safety_index: 82.1,
    traffic_volume: 8500,
    latitude: 38.8877,
    longitude: -77.0411,
    mcdm_index: 80.3,
    rt_si_score: 84.4
  },
  {
    intersection_id: 4,
    intersection_name: "Washington Blvd & Jefferson Ave",
    safety_index: 35.8,
    traffic_volume: 18000,
    latitude: 38.9003,
    longitude: -77.0297,
    mcdm_index: 37.1,
    rt_si_score: 34.9
  },
  {
    intersection_id: 5,
    intersection_name: "Lincoln Hwy & Roosevelt Dr",
    safety_index: 71.3,
    traffic_volume: 12000,
    latitude: 38.8824,
    longitude: -77.0478,
    mcdm_index: 70.1,
    rt_si_score: 72.6
  }
];

const navItems: Array<{ key: ViewKey; label: string; icon: typeof Gauge }> = [
  { key: "overview", label: "Operations", icon: Gauge },
  { key: "trends", label: "Trends", icon: LineChart },
  { key: "analytics", label: "Validation", icon: BarChart3 },
  { key: "sensitivity", label: "Sensitivity", icon: BrainCircuit },
  { key: "database", label: "Database", icon: Database }
];

const examplePrompts = [
  "Give me a morning safety briefing for all intersections.",
  "Which intersection is the most dangerous right now?",
  "Why is the Glebe-Potomac score elevated?",
  "What is driving risk at E. Broad & N. Washington?",
  "Compare all intersections by VRU count.",
  "What is the historical crash baseline for Birch & Broad?",
  "Which intersection has the lowest risk for emergency vehicle routing?"
];

function configuredApiBase() {
  const raw = import.meta.env.VITE_API_URL || "/api/v1";
  return String(raw).replace(/\/safety\/index\/?$/, "").replace(/\/$/, "");
}

const API_BASE = configuredApiBase();
const SAFETY_BASE = `${API_BASE}/safety/index`;

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const url = new URL(path.startsWith("http") ? path : `${API_BASE}${path}`, window.location.origin);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

function formatDateTimeLocal(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function fetchJson<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const response = await fetch(buildUrl(path, params));
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch {
      // Ignore non-JSON error bodies.
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

function toNumber(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatNumber(value: unknown, digits = 1) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/A";
  return numeric.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

function formatPercent(value: unknown, digits = 1) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "N/A";
  return `${(numeric * 100).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  })}%`;
}

function boolValue(value: unknown) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value > 0;
  if (typeof value === "string") return ["true", "1", "yes", "y"].includes(value.toLowerCase());
  return false;
}

function pearsonCorrelation(xs: number[], ys: number[]) {
  const pairs = xs
    .map((x, index) => ({ x, y: ys[index] }))
    .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
  if (pairs.length < 2) return null;
  const meanX = pairs.reduce((sum, item) => sum + item.x, 0) / pairs.length;
  const meanY = pairs.reduce((sum, item) => sum + item.y, 0) / pairs.length;
  const numerator = pairs.reduce((sum, item) => sum + (item.x - meanX) * (item.y - meanY), 0);
  const denomX = Math.sqrt(pairs.reduce((sum, item) => sum + (item.x - meanX) ** 2, 0));
  const denomY = Math.sqrt(pairs.reduce((sum, item) => sum + (item.y - meanY) ** 2, 0));
  const denominator = denomX * denomY;
  return denominator > 0 ? numerator / denominator : null;
}

function averageRanks(values: number[]) {
  const sorted = values
    .map((value, index) => ({ value, index }))
    .sort((a, b) => a.value - b.value);
  const ranks = Array(values.length).fill(0);
  let i = 0;
  while (i < sorted.length) {
    let j = i + 1;
    while (j < sorted.length && sorted[j].value === sorted[i].value) j += 1;
    const rank = (i + 1 + j) / 2;
    for (let k = i; k < j; k += 1) ranks[sorted[k].index] = rank;
    i = j;
  }
  return ranks;
}

function spearmanCorrelation(xs: number[], ys: number[]) {
  const pairs = xs
    .map((x, index) => ({ x, y: ys[index] }))
    .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
  if (pairs.length < 2) return null;
  return pearsonCorrelation(
    averageRanks(pairs.map((item) => item.x)),
    averageRanks(pairs.map((item) => item.y))
  );
}

function intersectionName(item: Intersection | TrendPoint | Record<string, unknown>) {
  return String(
    item.intersection_name ||
      item.intersection ||
      item.intersection_id ||
      "Unknown intersection"
  );
}

function scoreOf(item: Intersection | TrendPoint) {
  return toNumber(item.final_safety_index ?? item.safety_index ?? item.rt_si_score ?? item.mcdm_index, 0);
}

function riskLevel(score: number) {
  if (score >= 75) return { label: "High", className: "risk-high", color: "#d13f3f" };
  if (score >= 60) return { label: "Medium", className: "risk-medium", color: "#bf7a16" };
  return { label: "Low", className: "risk-low", color: "#2b8a57" };
}

function blendScore(mcdm: unknown, rtSi: unknown, alpha: number) {
  const m = toNumber(mcdm, 50);
  const r = rtSi === null || rtSi === undefined ? null : toNumber(rtSi, NaN);
  return Number.isFinite(Number(r)) ? alpha * Number(r) + (1 - alpha) * m : m;
}

function App() {
  const [view, setView] = useState<ViewKey>("overview");
  const [alpha, setAlpha] = useState(0.7);
  const [intersections, setIntersections] = useState<Intersection[]>([]);
  const [selected, setSelected] = useState<Intersection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<"live" | "fallback">("live");

  const loadIntersections = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJson<Intersection[]>("/safety/index/", {
        alpha,
        include_mcdm: true,
        bin_minutes: 15
      });
      const hasLiveData = Array.isArray(data) && data.length > 0;
      const normalized = hasLiveData ? data : fallbackIntersections;
      setIntersections(normalized);
      setSelected((current) => current || normalized[0] || null);
      setDataSource(hasLiveData ? "live" : "fallback");
      if (!hasLiveData) {
        setError("Backend returned no intersections. Showing fallback sample data until live safety data is available.");
      }
    } catch (err) {
      setIntersections(fallbackIntersections);
      setSelected((current) => current || fallbackIntersections[0]);
      setDataSource("fallback");
      setError(`Using fallback sample data. Backend request failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadIntersections();
  }, [alpha]);

  return (
    <div className="app-shell">
      <aside className="nav-rail">
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={24} />
          </div>
          <div>
            <strong>VTTSI</strong>
            <span>Safety Ops</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="Dashboard sections">
          {navItems.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className={view === key ? "nav-item active" : "nav-item"}
              onClick={() => setView(key)}
              type="button"
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="blend-control">
          <div className="label-row">
            <SlidersHorizontal size={16} />
            <span>RT-SI Weight</span>
            <strong>{Math.round(alpha * 100)}%</strong>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={alpha}
            onChange={(event) => setAlpha(Number(event.target.value))}
            aria-label="RT-SI blending weight"
          />
          <small>{Math.round((1 - alpha) * 100)}% MCDM blend</small>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Integrated traffic safety command center</p>
            <h1>Safety dashboard</h1>
          </div>
          <button className="icon-text-button" type="button" onClick={() => void loadIntersections()}>
            <RefreshCw size={17} />
            Refresh
          </button>
        </header>

        {error && <div className="notice warning">{error}</div>}

        {view === "overview" && (
          <OverviewPanel
            alpha={alpha}
            loading={loading}
            intersections={intersections}
            selected={selected}
            onSelect={setSelected}
            dataSource={dataSource}
          />
        )}
        {view === "trends" && <TrendPanel alpha={alpha} />}
        {view === "analytics" && <AnalyticsPanel />}
        {view === "sensitivity" && <SensitivityPanel />}
        {view === "database" && <DatabasePanel />}
      </main>

      <ChatDock alpha={alpha} />
    </div>
  );
}

function OverviewPanel({
  alpha,
  loading,
  intersections,
  selected,
  onSelect,
  dataSource
}: {
  alpha: number;
  loading: boolean;
  intersections: Intersection[];
  selected: Intersection | null;
  onSelect: (intersection: Intersection) => void;
  dataSource: "live" | "fallback";
}) {
  const [query, setQuery] = useState("");
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  const [volumeMin, setVolumeMin] = useState(0);

  const filtered = useMemo(() => {
    return intersections
      .filter((item) => intersectionName(item).toLowerCase().includes(query.toLowerCase()))
      .filter((item) => {
        const score = scoreOf(item);
        return score >= scoreRange[0] && score <= scoreRange[1];
      })
      .filter((item) => toNumber(item.traffic_volume, 0) >= volumeMin)
      .sort((a, b) => scoreOf(b) - scoreOf(a));
  }, [intersections, query, scoreRange, volumeMin]);

  const stats = useMemo(() => {
    const scores = filtered.map(scoreOf);
    const highRisk = filtered.filter((item) => scoreOf(item) >= 75).length;
    const avgScore = scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : 0;
    const totalVolume = filtered.reduce((sum, item) => sum + toNumber(item.traffic_volume, 0), 0);
    const avgRtSi =
      filtered.reduce((sum, item) => sum + toNumber(item.rt_si_score ?? item.rt_si_index, 0), 0) /
      Math.max(filtered.length, 1);
    const avgMcdm = filtered.reduce((sum, item) => sum + toNumber(item.mcdm_index, 0), 0) / Math.max(filtered.length, 1);
    const geocoded = filtered.filter((item) => Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude))).length;
    const noData = filtered.filter((item) => String(item.index_type || "").toLowerCase().includes("no data")).length;
    return { avgScore, highRisk, totalVolume, avgRtSi, avgMcdm, geocoded, noData };
  }, [filtered]);

  return (
    <section className="content-grid overview-grid">
      <div className="span-8 stack">
        <div className="metric-strip">
          <MetricCard label="Avg blended score" value={formatNumber(stats.avgScore)} icon={Gauge} />
          <MetricCard label="High-risk sites" value={stats.highRisk} icon={AlertTriangle} tone="danger" />
          <MetricCard label="Traffic volume" value={stats.totalVolume.toLocaleString()} icon={Activity} />
          <MetricCard label="Avg RT-SI" value={formatNumber(stats.avgRtSi)} icon={Layers} />
        </div>

        <div className="info-band">
          <InfoItem
            label="Data status"
            value={dataSource === "live" ? "Live backend data" : "Fallback sample data"}
            detail={`${filtered.length} visible, ${stats.geocoded} geocoded, ${stats.noData} no-data records`}
            tone={dataSource === "live" ? "good" : "warn"}
          />
          <InfoItem
            label="Blend formula"
            value={`Final = ${alpha.toFixed(1)} x RT-SI + ${(1 - alpha).toFixed(1)} x MCDM`}
            detail="Higher safety index means higher operational risk."
          />
          <InfoItem
            label="Method coverage"
            value={`Avg MCDM ${formatNumber(stats.avgMcdm)} | Avg RT-SI ${formatNumber(stats.avgRtSi)}`}
            detail="MCDM captures long-term priority; RT-SI captures current traffic conditions."
          />
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Network risk map</h2>
              <p>Marker size tracks traffic volume. Marker color tracks blended risk.</p>
            </div>
            <div className="legend">
              <span><i className="dot low" /> Low</span>
              <span><i className="dot medium" /> Medium</span>
              <span><i className="dot high" /> High</span>
            </div>
          </div>
          <GeoPlot intersections={filtered} selected={selected} onSelect={onSelect} />
        </div>

        <div className="panel">
          <div className="panel-header compact">
            <div>
              <h2>Intersections</h2>
              <p>{loading ? "Loading live safety scores..." : `${filtered.length} visible of ${intersections.length}`}</p>
            </div>
          </div>
          <IntersectionTable rows={filtered} onSelect={onSelect} selected={selected} />
        </div>
      </div>

      <div className="span-4 stack">
        <div className="panel controls-panel">
          <h2>Operational filters</h2>
          <label>
            <span>Search intersection</span>
            <div className="input-with-icon">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or ID" />
            </div>
          </label>
          <div className="two-col">
            <label>
              <span>Min score</span>
              <input
                type="number"
                min="0"
                max="100"
                value={scoreRange[0]}
                onChange={(event) => setScoreRange([Number(event.target.value), scoreRange[1]])}
              />
            </label>
            <label>
              <span>Max score</span>
              <input
                type="number"
                min="0"
                max="100"
                value={scoreRange[1]}
                onChange={(event) => setScoreRange([scoreRange[0], Number(event.target.value)])}
              />
            </label>
          </div>
          <label>
            <span>Minimum volume</span>
            <input
              type="number"
              min="0"
              value={volumeMin}
              onChange={(event) => setVolumeMin(Number(event.target.value))}
            />
          </label>
        </div>

        <MethodologyPanel alpha={alpha} />

        <div className="panel selected-panel">
          <div className="panel-header compact">
            <div>
              <h2>Selected site</h2>
              <p>Alpha {alpha.toFixed(1)} blended index</p>
            </div>
          </div>
          {selected ? <IntersectionDetails item={selected} /> : <EmptyState icon={MapPinned} title="No intersection selected" />}
        </div>

        <div className="panel">
          <div className="panel-header compact">
            <div>
              <h2>Priority queue</h2>
              <p>Highest risk intersections first</p>
            </div>
          </div>
          <div className="rank-list">
            {filtered.slice(0, 6).map((item, index) => {
              const score = scoreOf(item);
              const risk = riskLevel(score);
              return (
                <button key={`${item.intersection_id}-${index}`} type="button" onClick={() => onSelect(item)}>
                  <strong>{index + 1}</strong>
                  <span>{intersectionName(item)}</span>
                  <em className={risk.className}>{formatNumber(score)}</em>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function TrendPanel({ alpha }: { alpha: number }) {
  const [intersections, setIntersections] = useState<string[]>([]);
  const [intersection, setIntersection] = useState("glebe-potomac");
  const [startTime, setStartTime] = useState("2025-11-01T08:00");
  const [endTime, setEndTime] = useState("2025-11-01T18:00");
  const [binMinutes, setBinMinutes] = useState(15);
  const [trendData, setTrendData] = useState<TrendPoint[]>([]);
  const [specificPoint, setSpecificPoint] = useState<Record<string, unknown> | null>(null);
  const [correlationAnalysis, setCorrelationAnalysis] = useState<Record<string, unknown> | null>(null);
  const [metadata, setMetadata] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchJson<{ intersections: string[] }>("/safety/index/intersections/list")
      .then((data) => {
        setIntersections(data.intersections || []);
        if (data.intersections?.length) setIntersection(data.intersections[0]);
      })
      .catch(() => setIntersections(["glebe-potomac", "broad-washington", "birch-broad"]));
  }, []);

  const loadTrend = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const response = await fetchJson<{
        time_series?: TrendPoint[];
        correlation_analysis?: Record<string, unknown>;
        metadata?: Record<string, unknown>;
      } | TrendPoint[]>("/safety/index/time/range", {
        intersection,
        start_time: startTime,
        end_time: endTime,
        bin_minutes: binMinutes,
        alpha,
        include_correlations: true
      });
      const rows = Array.isArray(response) ? response : response.time_series || [];
      setTrendData(rows.map((row) => ({ ...row, final_safety_index: blendScore(row.mcdm_index, row.rt_si_score, alpha) })));
      setCorrelationAnalysis(Array.isArray(response) ? null : response.correlation_analysis || null);
      setMetadata(Array.isArray(response) ? null : response.metadata || null);
      setStatus(`Loaded ${rows.length} trend points for ${intersection}.`);
    } catch (err) {
      setTrendData([]);
      setCorrelationAnalysis(null);
      setMetadata(null);
      setStatus(`Trend request failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const applyPreset = (hours: number) => {
    const start = new Date(startTime);
    if (Number.isNaN(start.getTime())) return;
    const end = new Date(start.getTime() + hours * 60 * 60 * 1000);
    setEndTime(formatDateTimeLocal(end));
  };

  const loadSpecific = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const point = await fetchJson<Record<string, unknown>>("/safety/index/time/specific", {
        intersection,
        time: startTime,
        bin_minutes: binMinutes,
        alpha
      });
      setSpecificPoint(point);
      setStatus(`Loaded single time-bin detail for ${intersection}.`);
    } catch (err) {
      setSpecificPoint(null);
      setStatus(`Specific time request failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const summary = useMemo(() => {
    const totalVehicles = trendData.reduce((sum, row) => sum + toNumber(row.vehicle_count, 0), 0);
    const incidents = trendData.reduce((sum, row) => sum + toNumber(row.incident_count, 0), 0);
    const nearMisses = trendData.reduce((sum, row) => sum + toNumber(row.near_miss_count, 0), 0);
    const avgFinal = trendData.reduce((sum, row) => sum + scoreOf(row), 0) / Math.max(trendData.length, 1);
    const avgRtSi = trendData.reduce((sum, row) => sum + toNumber(row.rt_si_score, 0), 0) / Math.max(trendData.length, 1);
    const avgMcdm = trendData.reduce((sum, row) => sum + toNumber(row.mcdm_index, 0), 0) / Math.max(trendData.length, 1);
    return { totalVehicles, incidents, nearMisses, avgFinal, avgRtSi, avgMcdm };
  }, [trendData]);

  const normalizedRows = useMemo(() => {
    const keys = [
      "mcdm_index",
      "rt_si_score",
      "vehicle_count",
      "incident_count",
      "near_miss_count",
      "vru_count",
      "avg_speed",
      "speed_variance"
    ];
    const maxByKey = Object.fromEntries(keys.map((key) => [
      key,
      Math.max(...trendData.map((row) => Math.abs(toNumber(row[key]))), 0)
    ]));
    return trendData.map((row) => {
      const next: Record<string, unknown> = { time_bin: row.time_bin || row.timestamp };
      keys.forEach((key) => {
        const max = maxByKey[key] || 0;
        next[`${key}_normalized`] = max > 0 ? (toNumber(row[key]) / max) * 100 : 0;
      });
      return next;
    });
  }, [trendData]);

  return (
    <section className="stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2>Trend analysis</h2>
            <p>Inspect a single time bin or a full range with RT-SI and MCDM separated.</p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            <span>Intersection</span>
            <select value={intersection} onChange={(event) => setIntersection(event.target.value)}>
              {intersections.map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>
          <label>
            <span>Start time</span>
            <input type="datetime-local" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
          </label>
          <label>
            <span>End time</span>
            <input type="datetime-local" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
          </label>
          <label>
            <span>Bin minutes</span>
            <select value={binMinutes} onChange={(event) => setBinMinutes(Number(event.target.value))}>
              <option value={15}>15</option>
              <option value={30}>30</option>
              <option value={60}>60</option>
            </select>
          </label>
          <button className="primary-button" type="button" onClick={() => void loadTrend()} disabled={loading}>
            <LineChart size={17} />
            Load range
          </button>
          <button className="secondary-button" type="button" onClick={() => void loadSpecific()} disabled={loading}>
            <Gauge size={17} />
            Load time bin
          </button>
        </div>
        <div className="preset-row" aria-label="Quick time range presets">
          {[2, 6, 12, 24].map((hours) => (
            <button key={hours} className="secondary-button" type="button" onClick={() => applyPreset(hours)}>
              {hours}h
            </button>
          ))}
        </div>
        {status && <div className="notice">{status}</div>}
      </div>

      {trendData.length > 0 && (
        <>
          <div className="metric-strip">
            <MetricCard label="Avg final index" value={formatNumber(summary.avgFinal)} icon={Gauge} />
            <MetricCard label="Avg RT-SI" value={formatNumber(summary.avgRtSi)} icon={Layers} />
            <MetricCard label="Avg MCDM" value={formatNumber(summary.avgMcdm)} icon={ShieldCheck} />
            <MetricCard label="Vehicles" value={summary.totalVehicles.toLocaleString()} icon={Activity} />
            <MetricCard label="Incidents" value={summary.incidents.toLocaleString()} icon={AlertTriangle} tone="danger" />
            <MetricCard label="Near misses" value={summary.nearMisses.toLocaleString()} icon={Layers} />
          </div>

          <div className="panel">
            <h2>Safety index trend</h2>
            <MultiLineChart
              rows={trendData}
              xKey="time_bin"
              series={[
                { key: "final_safety_index", label: "Final", color: "#d13f3f" },
                { key: "rt_si_score", label: "RT-SI", color: "#2463eb" },
                { key: "mcdm_index", label: "MCDM", color: "#2b8a57" }
              ]}
            />
          </div>

          <div className="content-grid">
            <div className="panel span-6">
              <h2>Traffic factors</h2>
              <MultiLineChart
                rows={trendData}
                xKey="time_bin"
                series={[
                  { key: "vehicle_count", label: "Vehicles", color: "#277da1" },
                  { key: "vru_count", label: "VRU", color: "#8f5fbf" },
                  { key: "incident_count", label: "Incidents", color: "#bf3f3f" },
                  { key: "near_miss_count", label: "Near misses", color: "#bf7a16" }
                ]}
              />
            </div>
            <div className="panel span-6">
              <h2>Speed factors</h2>
              <MultiLineChart
                rows={trendData}
                xKey="time_bin"
                series={[
                  { key: "avg_speed", label: "Average speed", color: "#c2410c" },
                  { key: "speed_variance", label: "Speed variance", color: "#7c3aed" }
                ]}
              />
            </div>
            <div className="panel span-6">
              <h2>RT-SI sub-indices</h2>
              <MultiLineChart
                rows={trendData}
                xKey="time_bin"
                series={[
                  { key: "rt_si_score", label: "RT-SI", color: "#d13f3f" },
                  { key: "vru_index", label: "VRU index", color: "#8f5fbf" },
                  { key: "vehicle_index", label: "Vehicle index", color: "#bf7a16" }
                ]}
              />
            </div>
            <div className="panel span-6">
              <h2>MCDM methods</h2>
              <MultiLineChart
                rows={trendData}
                xKey="time_bin"
                series={[
                  { key: "mcdm_index", label: "MCDM index", color: "#111827" },
                  { key: "saw_score", label: "SAW", color: "#0f766e" },
                  { key: "edas_score", label: "EDAS", color: "#7c3aed" },
                  { key: "codas_score", label: "CODAS", color: "#c2410c" }
                ]}
              />
            </div>
            <div className="panel span-12">
              <h2>All variables normalized</h2>
              <p>Each metric is scaled to its own maximum so trends can be compared on one 0-100 chart.</p>
              <MultiLineChart
                rows={normalizedRows}
                xKey="time_bin"
                series={[
                  { key: "mcdm_index_normalized", label: "MCDM", color: "#2463eb" },
                  { key: "rt_si_score_normalized", label: "RT-SI", color: "#d13f3f" },
                  { key: "vehicle_count_normalized", label: "Vehicles", color: "#2b8a57" },
                  { key: "incident_count_normalized", label: "Incidents", color: "#bf3f3f" },
                  { key: "near_miss_count_normalized", label: "Near misses", color: "#bf7a16" },
                  { key: "vru_count_normalized", label: "VRU", color: "#277da1" },
                  { key: "avg_speed_normalized", label: "Avg speed", color: "#c2410c" },
                  { key: "speed_variance_normalized", label: "Speed variance", color: "#7c3aed" }
                ]}
              />
            </div>
            {correlationAnalysis ? (
              <div className="panel span-12">
                <CorrelationPanel data={correlationAnalysis} />
              </div>
            ) : trendData.length >= 3 ? (
              <div className="notice span-12">
                Correlation analysis was requested but not returned. The backend may lack enough valid variables for this time range.
              </div>
            ) : null}
            <div className="panel span-12">
              <h2>Trend data preview</h2>
              <p>{metadata ? `Backend metadata: ${JSON.stringify(metadata)}` : "Raw time-series fields returned by the safety API."}</p>
              <DataTable rows={trendData} maxRows={20} />
            </div>
          </div>
        </>
      )}

      {specificPoint && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Single time-bin detail</h2>
              <p>{String(specificPoint.intersection || intersection)} at {String(specificPoint.time_bin || startTime)}</p>
            </div>
          </div>
          <SingleTimeBreakdown data={specificPoint} alpha={alpha} />
        </div>
      )}
    </section>
  );
}

function CorrelationPanel({ data }: { data: Record<string, unknown> }) {
  const summary = (data.summary || {}) as Record<string, unknown>;
  const variableCorrelations = (data.variable_correlations || {}) as Record<string, any>;
  const rows = Object.values(variableCorrelations).map((item: any) => ({
    "Variable 1": item.variable_1,
    "Variable 2": item.variable_2,
    "Pearson r": item.pearson?.correlation,
    "Pearson p": item.pearson?.p_value,
    "Pearson significant": item.pearson?.significant ? "Yes" : "No",
    "Spearman rho": item.spearman?.correlation,
    "Spearman p": item.spearman?.p_value,
    "Spearman significant": item.spearman?.significant ? "Yes" : "No",
    N: item.n_samples,
    Description: item.description
  })).sort((a, b) => Math.abs(toNumber(b["Pearson r"])) - Math.abs(toNumber(a["Pearson r"])));

  const strengthRows = rows.slice(0, 12).map((row) => ({
    label: `${row["Variable 1"]} / ${row["Variable 2"]}`,
    value: Math.abs(toNumber(row["Pearson r"]))
  }));

  return (
    <div className="stack">
      <div>
        <h2>Correlation analysis</h2>
        <p>Pearson and Spearman relationships between returned trend variables.</p>
      </div>
      <div className="metric-strip">
        <MetricCard label="Variables" value={formatNumber(summary.total_variables, 0)} icon={Database} />
        <MetricCard label="Correlations" value={formatNumber(summary.total_correlations, 0)} icon={BarChart3} />
        <MetricCard label="Strong" value={formatNumber(summary.strong_correlations, 0)} icon={AlertTriangle} tone="danger" />
        <MetricCard label="Moderate" value={formatNumber(summary.moderate_correlations, 0)} icon={Activity} />
      </div>
      <div className="content-grid">
        <div className="span-5">
          <h3>Top relationship strength</h3>
          <SimpleBarChart rows={strengthRows} labelKey="label" valueKey="value" />
        </div>
        <div className="span-7">
          <h3>Correlation table</h3>
          <DataTable rows={rows} maxRows={20} />
        </div>
      </div>
    </div>
  );
}

function deriveValidationMetrics(
  rows: Record<string, unknown>[],
  threshold: number,
  startDate: string,
  endDate: string
) {
  const usableRows = rows.filter((row) => Number.isFinite(Number(row.safety_index)));
  const scores = usableRows.map((row) => Number(row.safety_index));
  const actuals = usableRows.map((row) => (boolValue(row.had_crash) || toNumber(row.crash_count, 0) > 0 ? 1 : 0));
  const predictions = scores.map((score) => (score >= threshold ? 1 : 0));
  const tp = predictions.filter((prediction, index) => prediction === 1 && actuals[index] === 1).length;
  const fp = predictions.filter((prediction, index) => prediction === 1 && actuals[index] === 0).length;
  const tn = predictions.filter((prediction, index) => prediction === 0 && actuals[index] === 0).length;
  const fn = predictions.filter((prediction, index) => prediction === 0 && actuals[index] === 1).length;
  const precision = tp + fp > 0 ? tp / (tp + fp) : null;
  const recall = tp + fn > 0 ? tp / (tp + fn) : null;
  const f1Score = precision !== null && recall !== null && precision + recall > 0 ? (2 * precision * recall) / (precision + recall) : null;
  const total = tp + fp + tn + fn;
  const crashIntervals = actuals.filter(Boolean).length;
  const crashEvents = usableRows.reduce((sum, row) => sum + Math.max(toNumber(row.crash_count, 0), boolValue(row.had_crash) ? 1 : 0), 0);

  return {
    total_crashes: crashEvents,
    crash_intervals: crashIntervals,
    total_intervals: usableRows.length,
    crash_rate: usableRows.length ? crashIntervals / usableRows.length : null,
    threshold,
    true_positives: tp,
    false_positives: fp,
    true_negatives: tn,
    false_negatives: fn,
    precision,
    recall,
    f1_score: f1Score,
    accuracy: total ? (tp + tn) / total : null,
    pearson_correlation: pearsonCorrelation(scores, actuals),
    spearman_correlation: spearmanCorrelation(scores, actuals),
    start_date: startDate,
    end_date: endDate,
    derived_from_rows: true
  };
}

function hasUsableValidationMetrics(metrics: Record<string, unknown> | null) {
  if (!metrics) return false;
  return toNumber(metrics.total_intervals, 0) > 0 || toNumber(metrics.total_crashes, 0) > 0;
}

function validationSummary(metrics: Record<string, unknown>) {
  const pearson = Number(metrics.pearson_correlation);
  if (!Number.isFinite(pearson)) {
    return {
      tone: "warn" as const,
      title: "Correlation unavailable",
      detail: "The selected data has too little variation to compute a stable Pearson correlation."
    };
  }
  if (pearson > 0.3) {
    return {
      tone: "good" as const,
      title: "Strong positive relationship",
      detail: "Higher safety index values align with observed crash intervals in this window."
    };
  }
  if (pearson > 0.15) {
    return {
      tone: "warn" as const,
      title: "Moderate relationship",
      detail: "The signal is present, but formula weights may need tuning for this window."
    };
  }
  return {
    tone: "warn" as const,
    title: "Weak relationship",
    detail: "The selected window does not show a strong crash correlation. Check date coverage and threshold."
  };
}

function AnalyticsPanel() {
  const today = new Date().toISOString().slice(0, 10);
  const prior = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState("2025-11-01");
  const [endDate, setEndDate] = useState("2025-11-23");
  const [threshold, setThreshold] = useState(60);
  const [radius, setRadius] = useState(500);
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [scatter, setScatter] = useState<Record<string, unknown>[]>([]);
  const [series, setSeries] = useState<Record<string, unknown>[]>([]);
  const [weather, setWeather] = useState<Record<string, unknown>[]>([]);
  const [validationSource, setValidationSource] = useState<"backend" | "derived" | "none">("none");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    setStatus(null);
    const params = { start_date: startDate, end_date: endDate, proximity_radius: radius };
    const [metricResult, scatterResult, timeResult, weatherResult] = await Promise.allSettled([
      fetchJson<Record<string, unknown>>("/analytics/correlation", { ...params, threshold }),
      fetchJson<Record<string, unknown>[]>("/analytics/scatter-data", params),
      fetchJson<Record<string, unknown>[]>("/analytics/time-series", params),
      fetchJson<Record<string, unknown>[]>("/analytics/weather-impact", params)
    ]);

    const metricData = metricResult.status === "fulfilled" ? metricResult.value : null;
    const scatterData = scatterResult.status === "fulfilled" ? scatterResult.value : [];
    const timeData = timeResult.status === "fulfilled" ? timeResult.value : [];
    const weatherData = weatherResult.status === "fulfilled" ? weatherResult.value : [];
    const validationRows = scatterData.length ? scatterData : timeData;
    const derivedMetrics = validationRows.length ? deriveValidationMetrics(validationRows, threshold, startDate, endDate) : null;
    const useBackend = hasUsableValidationMetrics(metricData);
    const nextMetrics = useBackend ? metricData : derivedMetrics;

    setMetrics(nextMetrics);
    setScatter(scatterData);
    setSeries(timeData);
    setWeather(weatherData);
    setValidationSource(useBackend ? "backend" : derivedMetrics ? "derived" : "none");

    const failures = [metricResult, scatterResult, timeResult, weatherResult].filter((result) => result.status === "rejected").length;
    if (nextMetrics && validationRows.length && !useBackend) {
      setStatus(`Validation metrics derived from ${validationRows.length} plotted rows because backend summary metrics were empty or unavailable.`);
    } else if (nextMetrics) {
      setStatus(failures ? `Validation loaded with ${failures} partial request failure(s).` : "Validation data loaded.");
    } else if (failures) {
      setStatus("Validation requests failed or returned no safety-index rows for this date range.");
    } else {
      setStatus("No validation rows returned. Try the demo data preset or widen the date range.");
    }
    setLoading(false);
  };

  const applyValidationPreset = (preset: "demo" | "recent" | "crash2024") => {
    if (preset === "demo") {
      setStartDate("2025-11-01");
      setEndDate("2025-11-23");
    } else if (preset === "recent") {
      setStartDate(prior);
      setEndDate(today);
    } else {
      setStartDate("2024-01-01");
      setEndDate("2024-12-31");
    }
  };

  const summary = metrics ? validationSummary(metrics) : null;

  return (
    <section className="stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2>Analytics and validation</h2>
            <p>Compare safety index thresholds against crash proximity and weather patterns.</p>
          </div>
        </div>
        <div className="explain-grid">
          <InfoItem label="Risk threshold" value="Classifies high-risk intervals" detail="Used to compute precision, recall, F1, and confusion-matrix counts." />
          <InfoItem label="Proximity radius" value="Crash matching distance" detail="Crashes within the selected radius are treated as related to an intersection." />
          <InfoItem label="Correlations" value="Pearson and Spearman" detail="Validate whether safety scores increase with observed crash occurrence." />
        </div>
        <div className="preset-row" aria-label="Validation date presets">
          <button className="secondary-button" type="button" onClick={() => applyValidationPreset("demo")}>
            Demo data
          </button>
          <button className="secondary-button" type="button" onClick={() => applyValidationPreset("recent")}>
            Last 30 days
          </button>
          <button className="secondary-button" type="button" onClick={() => applyValidationPreset("crash2024")}>
            2024 crashes
          </button>
        </div>
        <div className="form-grid">
          <label><span>Start date</span><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
          <label><span>End date</span><input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
          <label><span>Risk threshold</span><input type="number" value={threshold} min="0" max="100" onChange={(e) => setThreshold(Number(e.target.value))} /></label>
          <label><span>Radius meters</span><input type="number" value={radius} min="100" step="100" onChange={(e) => setRadius(Number(e.target.value))} /></label>
          <button className="primary-button" type="button" onClick={() => void run()} disabled={loading}>
            <BarChart3 size={17} />
            Run validation
          </button>
        </div>
        {status && <div className="notice">{status}</div>}
      </div>

      {metrics && (
        <>
          <div className="metric-strip">
            <MetricCard label="Crash events" value={formatNumber(metrics.total_crashes, 0)} icon={AlertTriangle} tone="danger" />
            <MetricCard label="Intervals" value={formatNumber(metrics.total_intervals, 0)} icon={Database} />
            <MetricCard label="Crash rate" value={formatPercent(metrics.crash_rate, 2)} icon={Activity} />
            <MetricCard label="Precision" value={formatPercent(metrics.precision, 1)} icon={Gauge} />
            <MetricCard label="Recall" value={formatPercent(metrics.recall, 1)} icon={Activity} />
            <MetricCard label="F1 score" value={formatNumber(metrics.f1_score, 3)} icon={ShieldCheck} />
            <MetricCard label="Accuracy" value={formatPercent(metrics.accuracy, 1)} icon={ShieldCheck} />
            <MetricCard label="Pearson r" value={formatNumber(metrics.pearson_correlation, 3)} icon={BarChart3} />
            <MetricCard label="Spearman rho" value={formatNumber(metrics.spearman_correlation, 3)} icon={BarChart3} />
          </div>
          <div className="info-band">
            <InfoItem
              label="Metric source"
              value={validationSource === "backend" ? "Backend summary" : validationSource === "derived" ? "Frontend derived" : "No data"}
              detail={validationSource === "derived" ? "Computed from returned scatter/time-series rows so the panel does not collapse to placeholder zeros." : "Using the analytics summary returned by the backend."}
              tone={validationSource === "backend" ? "good" : "warn"}
            />
            {summary && <InfoItem label="Interpretation" value={summary.title} detail={summary.detail} tone={summary.tone} />}
            <InfoItem
              label="Classification rule"
              value={`High risk if index >= ${formatNumber(metrics.threshold, 0)}`}
              detail={`${formatNumber(metrics.true_positives, 0)} TP, ${formatNumber(metrics.false_positives, 0)} FP, ${formatNumber(metrics.true_negatives, 0)} TN, ${formatNumber(metrics.false_negatives, 0)} FN`}
            />
          </div>
          <div className="content-grid">
            <div className="panel span-6">
              <h2>Confusion matrix</h2>
              <ConfusionMatrix metrics={metrics} />
            </div>
            <div className="panel span-6">
              <h2>Safety index and crash event</h2>
              <CrashScatter rows={scatter.length ? scatter : series} />
            </div>
            <div className="panel span-8">
              <h2>Time series with crash overlay</h2>
              <ValidationTimeSeries rows={series} />
            </div>
            <div className="panel span-4">
              <h2>Weather impact</h2>
              <SimpleBarChart rows={weather.slice(0, 10)} labelKey="condition" valueKey="crash_rate" />
            </div>
            <div className="panel span-12">
              <h2>Validation data preview</h2>
              <DataTable rows={(scatter.length ? scatter : series).slice(0, 50)} maxRows={50} />
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function SensitivityPanel() {
  const [intersections, setIntersections] = useState<string[]>([]);
  const [intersection, setIntersection] = useState("glebe-potomac");
  const [startTime, setStartTime] = useState("2025-11-01T08:00");
  const [endTime, setEndTime] = useState("2025-11-01T18:00");
  const [binMinutes, setBinMinutes] = useState(15);
  const [perturbation, setPerturbation] = useState(0.25);
  const [samples, setSamples] = useState(50);
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchJson<{ intersections: string[] }>("/safety/index/intersections/list")
      .then((payload) => {
        setIntersections(payload.intersections || []);
        if (payload.intersections?.length) setIntersection(payload.intersections[0]);
      })
      .catch(() => setIntersections(["glebe-potomac", "broad-washington", "birch-broad"]));
  }, []);

  const run = async () => {
    setLoading(true);
    setStatus("Running sensitivity analysis. Larger sample counts can take a while.");
    try {
      const result = await fetchJson<Record<string, any>>("/safety/index/sensitivity-analysis", {
        intersection,
        start_time: startTime,
        end_time: endTime,
        bin_minutes: binMinutes,
        perturbation_pct: perturbation,
        n_samples: samples
      });
      setData(result);
      setStatus("Sensitivity analysis complete.");
    } catch (err) {
      setStatus(`Sensitivity request failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const stability = data?.stability_metrics || {};
  const parameterRows = Object.entries(data?.parameter_importance || {}).map(([name, info]: [string, any]) => ({
    name,
    correlation: Number(info.correlation || 0),
    interpretation: String(info.interpretation || "")
  }));

  return (
    <section className="stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2>Sensitivity analysis</h2>
            <p>Validate that RT-SI rankings stay stable under parameter perturbation.</p>
          </div>
        </div>
        <div className="explain-grid">
          <InfoItem label="Baseline" value="Standard RT-SI parameters" detail="Scores from the unmodified model become the comparison reference." />
          <InfoItem label="Perturbation" value="Random parameter variation" detail="Tests beta, scaling, shrinkage, and VRU/vehicle blend robustness." />
          <InfoItem label="Robustness target" value="Stable ranking and tiers" detail="High Spearman rho and low tier changes indicate reliable prioritization." />
        </div>
        <div className="form-grid">
          <label><span>Intersection</span><select value={intersection} onChange={(e) => setIntersection(e.target.value)}>{intersections.map((name) => <option key={name}>{name}</option>)}</select></label>
          <label><span>Start time</span><input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} /></label>
          <label><span>End time</span><input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} /></label>
          <label><span>Bin minutes</span><select value={binMinutes} onChange={(e) => setBinMinutes(Number(e.target.value))}><option value={15}>15</option><option value={30}>30</option><option value={60}>60</option></select></label>
          <label><span>Perturbation</span><select value={perturbation} onChange={(e) => setPerturbation(Number(e.target.value))}><option value={0.1}>10%</option><option value={0.25}>25%</option><option value={0.5}>50%</option></select></label>
          <label><span>Samples</span><select value={samples} onChange={(e) => setSamples(Number(e.target.value))}><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label>
          <button className="primary-button" type="button" onClick={() => void run()} disabled={loading}>
            <BrainCircuit size={17} />
            Run analysis
          </button>
        </div>
        {status && <div className="notice">{status}</div>}
      </div>

      {data && (
        <>
          <div className="metric-strip">
            <MetricCard label="Mean Spearman rho" value={formatNumber(stability.spearman_correlations?.mean, 3)} icon={Gauge} />
            <MetricCard label="Mean score change" value={formatNumber(stability.score_changes?.mean, 2)} icon={Activity} />
            <MetricCard label="Max score change" value={formatNumber(stability.score_changes?.max, 2)} icon={AlertTriangle} tone="danger" />
            <MetricCard label="Tier unchanged" value={`${formatNumber(stability.tier_changes?.percentage_no_change, 1)}%`} icon={ShieldCheck} />
          </div>
          <div className="content-grid">
            <div className="panel span-6">
              <h2>Baseline versus perturbations</h2>
              <PerturbationChart data={data} />
            </div>
            <div className="panel span-6">
              <h2>Parameter importance</h2>
              <SimpleBarChart rows={parameterRows} labelKey="name" valueKey="correlation" absolute />
            </div>
            <div className="panel span-12">
              <h2>Parameter detail</h2>
              <DataTable rows={parameterRows} />
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function DatabasePanel() {
  const [tables, setTables] = useState<string[]>([]);
  const [table, setTable] = useState("");
  const [limit, setLimit] = useState(1000);
  const [filterValue, setFilterValue] = useState("");
  const [schema, setSchema] = useState<Record<string, unknown>[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<string[]>("/database/tables")
      .then((data) => {
        setTables(data);
        if (data.length) setTable(data[0]);
      })
      .catch((err) => setStatus(`Could not fetch tables: ${(err as Error).message}`));
  }, []);

  const load = async () => {
    if (!table) return;
    setStatus(null);
    try {
      const filter =
        table === "speed-distribution" && filterValue
          ? { filter_col: "intersection", filter_val: filterValue }
          : {};
      const [schemaData, rowData] = await Promise.all([
        fetchJson<Record<string, unknown>[]>(`/database/schema/${table}`),
        fetchJson<Record<string, unknown>[]>(`/database/data/${table}`, { limit, ...filter })
      ]);
      setSchema(schemaData);
      setRows(rowData);
      setStatus(`Loaded ${rowData.length} rows from ${table}.`);
    } catch (err) {
      setStatus(`Database request failed: ${(err as Error).message}`);
    }
  };

  useEffect(() => {
    if (table) void load();
  }, [table]);

  const numericColumns = Object.keys(rows[0] || {}).filter((key) => rows.some((row) => Number.isFinite(Number(row[key]))));
  const categoricalColumns = Object.keys(rows[0] || {}).filter((key) => !numericColumns.includes(key));
  const chartRows = numericColumns[0]
    ? rows.slice(0, 30).map((row, index) => ({ label: String(row[categoricalColumns[0]] ?? index + 1), value: Number(row[numericColumns[0]]) || 0 }))
    : [];

  return (
    <section className="stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2>Database explorer</h2>
            <p>Inspect raw tables, schema, and quick distribution views without leaving the dashboard.</p>
          </div>
        </div>
        <div className="form-grid">
          <label><span>Table</span><select value={table} onChange={(e) => setTable(e.target.value)}>{tables.map((name) => <option key={name}>{name}</option>)}</select></label>
          <label><span>Rows</span><input type="number" min="10" max="5000" value={limit} onChange={(e) => setLimit(Number(e.target.value))} /></label>
          <label><span>Speed table intersection filter</span><input value={filterValue} onChange={(e) => setFilterValue(e.target.value)} placeholder="glebe-potomac" /></label>
          <button className="primary-button" type="button" onClick={() => void load()}>
            <Table2 size={17} />
            Load table
          </button>
        </div>
        {status && <div className="notice">{status}</div>}
      </div>

      <div className="content-grid">
        <div className="panel span-5">
          <h2>Schema</h2>
          <DataTable rows={schema} maxRows={20} />
        </div>
        <div className="panel span-7">
          <h2>Quick chart</h2>
          {chartRows.length ? <SimpleBarChart rows={chartRows} labelKey="label" valueKey="value" /> : <EmptyState icon={BarChart3} title="No numeric columns available" />}
        </div>
        <div className="panel span-12">
          <h2>Data preview</h2>
          <DataTable rows={rows} />
        </div>
      </div>
    </section>
  );
}

function ChatDock({ alpha }: { alpha: number }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const send = async (prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || loading) return;

    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setInput("");
    setError(null);
    setLoading(true);

    const messagesToSend = nextMessages.map((message, index) =>
      index === nextMessages.length - 1
        ? {
            ...message,
            content: `${message.content}\n[User preference: use alpha=${alpha} for blended score calculations.]`
          }
        : message
    );

    try {
      const response = await fetch(buildUrl("/chat/"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: messagesToSend })
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setMessages([...nextMessages, { role: "assistant", content: data.reply || "No response received." }]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(input);
  };

  return (
    <aside className="chat-dock">
      <div className="chat-header">
        <div>
          <p className="eyebrow">Live assistant</p>
          <h2>SafetyChat</h2>
        </div>
        <Bot size={22} />
      </div>

      <div className="prompt-grid">
        {examplePrompts.map((prompt) => (
          <button key={prompt} type="button" onClick={() => void send(prompt)}>
            {prompt}
          </button>
        ))}
      </div>

      <div className="assistant-note">
        <strong>Grounding</strong>
        <span>SafetyChat sends conversation history to the VTTSI backend and includes alpha={alpha.toFixed(1)} for blended score calculations.</span>
      </div>

      <div className="chat-messages">
        {!messages.length && (
          <div className="empty-chat">
            <MessageSquare size={22} />
            <p>Ask about current risk, rankings, causal factors, or routing choices.</p>
          </div>
        )}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
            {message.content}
          </div>
        ))}
        {loading && <div className="chat-bubble assistant">Thinking...</div>}
      </div>

      {error && <div className="chat-error">{error}</div>}

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about intersection safety..."
        />
        <button type="submit" aria-label="Send message" disabled={loading}>
          <Send size={17} />
        </button>
      </form>
    </aside>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
  tone
}: {
  label: string;
  value: string | number;
  icon: typeof Gauge;
  tone?: "danger";
}) {
  return (
    <div className={tone === "danger" ? "metric-card danger" : "metric-card"}>
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InfoItem({
  label,
  value,
  detail,
  tone
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "good" | "warn";
}) {
  return (
    <div className={tone ? `info-item ${tone}` : "info-item"}>
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}

function MethodologyPanel({ alpha }: { alpha: number }) {
  return (
    <div className="panel methodology-panel">
      <div>
        <h2>Index guide</h2>
        <p>How to read the dashboard values.</p>
      </div>
      <div className="methodology-list">
        <div>
          <strong>Blended safety index</strong>
          <span>{alpha.toFixed(1)} x RT-SI + {(1 - alpha).toFixed(1)} x MCDM. Higher values mean more dangerous intersections.</span>
        </div>
        <div>
          <strong>RT-SI</strong>
          <span>Real-time safety index from current traffic, speed patterns, conflicts, and Empirical Bayes stabilization.</span>
        </div>
        <div>
          <strong>MCDM</strong>
          <span>Long-term prioritization using CRITIC weighting plus SAW, EDAS, and CODAS method scores.</span>
        </div>
        <div>
          <strong>Risk tiers</strong>
          <span>Low under 60, medium from 60 to 75, high at 75 and above.</span>
        </div>
      </div>
    </div>
  );
}

function SingleTimeBreakdown({ data, alpha }: { data: Record<string, unknown>; alpha: number }) {
  const finalIndex = blendScore(data.mcdm_index ?? data.safety_score, data.rt_si_score, alpha);
  return (
    <div className="stack">
      <div className="metric-strip">
        <MetricCard label="Final safety index" value={formatNumber(finalIndex, 2)} icon={Gauge} />
        <MetricCard label="RT-SI score" value={formatNumber(data.rt_si_score, 2)} icon={Layers} />
        <MetricCard label="MCDM index" value={formatNumber(data.mcdm_index, 2)} icon={ShieldCheck} />
        <MetricCard label="RT-SI weight" value={`${Math.round(alpha * 100)}%`} icon={SlidersHorizontal} />
      </div>

      <div className="content-grid">
        <div className="subpanel span-4">
          <h3>Traffic metrics</h3>
          <KeyValueGrid
            data={{
              "Vehicle count": data.vehicle_count,
              "VRU count": data.vru_count,
              Incidents: data.incident_count,
              "Near misses": data.near_miss_count,
              "Average speed": data.avg_speed === undefined ? "N/A" : `${formatNumber(data.avg_speed, 1)} mph`,
              "Speed variance": formatNumber(data.speed_variance, 1)
            }}
          />
        </div>
        <div className="subpanel span-4">
          <h3>RT-SI sub-indices</h3>
          <KeyValueGrid
            data={{
              "VRU index": formatNumber(data.vru_index, 4),
              "Vehicle index": formatNumber(data.vehicle_index, 4),
              "Raw crash rate": formatNumber(data.raw_crash_rate, 4),
              "EB crash rate": formatNumber(data.eb_crash_rate, 4),
              "Uplift factor": formatNumber(data.uplift_factor, 4)
            }}
          />
        </div>
        <div className="subpanel span-4">
          <h3>MCDM methods</h3>
          <KeyValueGrid
            data={{
              "SAW score": formatNumber(data.saw_score, 2),
              "EDAS score": formatNumber(data.edas_score, 2),
              "CODAS score": formatNumber(data.codas_score, 2),
              "Blend formula": `${alpha.toFixed(1)} x RT-SI + ${(1 - alpha).toFixed(1)} x MCDM`
            }}
          />
        </div>
        <div className="subpanel span-12">
          <h3>Raw API fields</h3>
          <DataTable rows={[data]} maxRows={1} />
        </div>
      </div>
    </div>
  );
}

function GeoPlot({
  intersections,
  selected,
  onSelect
}: {
  intersections: Intersection[];
  selected: Intersection | null;
  onSelect: (item: Intersection) => void;
}) {
  const points = intersections.filter((item) => item.latitude && item.longitude);
  const lats = points.map((item) => toNumber(item.latitude));
  const lons = points.map((item) => toNumber(item.longitude));
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const maxVolume = Math.max(...points.map((item) => toNumber(item.traffic_volume, 1)), 1);

  if (!points.length) {
    return <EmptyState icon={MapPinned} title="No geocoded intersections" />;
  }

  return (
    <div className="geo-plot">
      <div className="map-grid-lines" />
      {points.map((item, index) => {
        const lat = toNumber(item.latitude);
        const lon = toNumber(item.longitude);
        const x = ((lon - minLon) / Math.max(maxLon - minLon, 0.0001)) * 84 + 8;
        const y = (1 - (lat - minLat) / Math.max(maxLat - minLat, 0.0001)) * 78 + 11;
        const score = scoreOf(item);
        const risk = riskLevel(score);
        const radius = 10 + (toNumber(item.traffic_volume, 0) / maxVolume) * 20;
        const active = selected?.intersection_id === item.intersection_id;
        return (
          <button
            key={`${item.intersection_id}-${index}`}
            type="button"
            className={active ? "map-marker active" : "map-marker"}
            style={{
              left: `${x}%`,
              top: `${y}%`,
              width: `${radius}px`,
              height: `${radius}px`,
              background: risk.color
            }}
            onClick={() => onSelect(item)}
            title={`${intersectionName(item)}: ${formatNumber(score)}`}
          />
        );
      })}
    </div>
  );
}

function IntersectionTable({
  rows,
  selected,
  onSelect
}: {
  rows: Intersection[];
  selected: Intersection | null;
  onSelect: (item: Intersection) => void;
}) {
  return (
    <div className="table-wrap compact-table">
      <table>
        <thead>
          <tr>
            <th>Intersection</th>
            <th>Risk</th>
            <th>Final</th>
            <th>RT-SI</th>
            <th>MCDM</th>
            <th>Volume</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item, index) => {
            const score = scoreOf(item);
            const risk = riskLevel(score);
            const active = selected?.intersection_id === item.intersection_id;
            return (
              <tr key={`${item.intersection_id}-${index}`} className={active ? "selected-row" : ""} onClick={() => onSelect(item)}>
                <td>{intersectionName(item)}</td>
                <td><span className={`risk-pill ${risk.className}`}>{risk.label}</span></td>
                <td>{formatNumber(score)}</td>
                <td>{formatNumber(item.rt_si_score ?? item.rt_si_index)}</td>
                <td>{formatNumber(item.mcdm_index)}</td>
                <td>{toNumber(item.traffic_volume).toLocaleString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function IntersectionDetails({ item }: { item: Intersection }) {
  const score = scoreOf(item);
  const risk = riskLevel(score);
  return (
    <div className="details">
      <div>
        <span className={`risk-pill ${risk.className}`}>{risk.label} risk</span>
        <h3>{intersectionName(item)}</h3>
      </div>
      <div className="score-circle" style={{ borderColor: risk.color }}>
        <strong>{formatNumber(score)}</strong>
        <span>Final</span>
      </div>
      <KeyValueGrid
        data={{
          "Intersection ID": item.intersection_id,
          "Traffic volume": toNumber(item.traffic_volume).toLocaleString(),
          "RT-SI": formatNumber(item.rt_si_score ?? item.rt_si_index),
          "MCDM": formatNumber(item.mcdm_index),
          "VRU index": formatNumber(item.vru_index, 4),
          "Vehicle index": formatNumber(item.vehicle_index, 4),
          Latitude: formatNumber(item.latitude, 5),
          Longitude: formatNumber(item.longitude, 5)
        }}
      />
    </div>
  );
}

function KeyValueGrid({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="kv-grid">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "N/A")}</dd>
        </div>
      ))}
    </dl>
  );
}

function MultiLineChart({
  rows,
  xKey,
  series
}: {
  rows: Record<string, unknown>[];
  xKey: string;
  series: Array<{ key: string; label: string; color: string }>;
}) {
  const width = 760;
  const height = 300;
  const padding = { top: 18, right: 18, bottom: 46, left: 52 };
  const values = rows.flatMap((row) => series.map((item) => Number(row[item.key])).filter(Number.isFinite));
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const yScale = (value: number) =>
    height - padding.bottom - ((value - min) / Math.max(max - min, 1)) * (height - padding.top - padding.bottom);
  const xScale = (index: number) =>
    padding.left + (index / Math.max(rows.length - 1, 1)) * (width - padding.left - padding.right);

  if (!rows.length || !values.length) return <EmptyState icon={LineChart} title="No chart data" />;

  return (
    <div className="chart-box">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="axis" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} className="axis" />
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const y = padding.top + tick * (height - padding.top - padding.bottom);
          return <line key={tick} x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="grid-line" />;
        })}
        {series.map((line) => {
          const path = rows
            .map((row, index) => {
              const value = Number(row[line.key]);
              if (!Number.isFinite(value)) return null;
              return `${index === 0 ? "M" : "L"}${xScale(index)},${yScale(value)}`;
            })
            .filter(Boolean)
            .join(" ");
          return <path key={line.key} d={path} fill="none" stroke={line.color} strokeWidth="3" strokeLinecap="round" />;
        })}
        <text x={padding.left} y={14} className="chart-label">{formatNumber(max)}</text>
        <text x={padding.left} y={height - padding.bottom + 18} className="chart-label">{formatNumber(min)}</text>
      </svg>
      <div className="chart-legend">
        {series.map((line) => (
          <span key={line.key}><i style={{ background: line.color }} />{line.label}</span>
        ))}
      </div>
    </div>
  );
}

function SimpleBarChart({
  rows,
  labelKey,
  valueKey,
  absolute
}: {
  rows: Record<string, unknown>[];
  labelKey: string;
  valueKey: string;
  absolute?: boolean;
}) {
  const clean = rows
    .map((row) => ({ label: String(row[labelKey] ?? "N/A"), value: absolute ? Math.abs(Number(row[valueKey])) : Number(row[valueKey]) }))
    .filter((row) => Number.isFinite(row.value))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 12);
  const max = Math.max(...clean.map((row) => Math.abs(row.value)), 1);

  if (!clean.length) return <EmptyState icon={BarChart3} title="No chart data" />;

  return (
    <div className="bar-list">
      {clean.map((row) => (
        <div key={row.label} className="bar-row">
          <span>{row.label}</span>
          <div><i style={{ width: `${(Math.abs(row.value) / max) * 100}%` }} /></div>
          <strong>{formatNumber(row.value, 3)}</strong>
        </div>
      ))}
    </div>
  );
}

function ConfusionMatrix({ metrics }: { metrics: Record<string, unknown> }) {
  const matrix = [
    { label: "True negatives", value: metrics.true_negatives, className: "good" },
    { label: "False positives", value: metrics.false_positives, className: "warn" },
    { label: "False negatives", value: metrics.false_negatives, className: "warn" },
    { label: "True positives", value: metrics.true_positives, className: "good" }
  ];
  return (
    <div className="matrix">
      {matrix.map((cell) => (
        <div key={cell.label} className={cell.className}>
          <span>{cell.label}</span>
          <strong>{formatNumber(cell.value, 0)}</strong>
        </div>
      ))}
    </div>
  );
}

function CrashScatter({ rows }: { rows: Record<string, unknown>[] }) {
  const width = 620;
  const height = 260;
  const maxScore = Math.max(...rows.map((row) => toNumber(row.safety_index)), 100);

  if (!rows.length) return <EmptyState icon={BarChart3} title="No scatter data" />;

  return (
    <div className="chart-box">
      <svg viewBox={`0 0 ${width} ${height}`}>
        <line x1="36" y1="210" x2="590" y2="210" className="axis" />
        <line x1="36" y1="40" x2="36" y2="210" className="axis" />
        {rows.slice(0, 250).map((row, index) => {
          const x = 36 + (toNumber(row.safety_index) / Math.max(maxScore, 1)) * 540;
          const y = row.had_crash ? 78 : 178;
          return (
            <circle
              key={index}
              cx={x}
              cy={y + ((index % 7) - 3) * 3}
              r={row.had_crash ? 5 : 3}
              fill={row.had_crash ? "#d13f3f" : "#2b8a57"}
              opacity={row.had_crash ? 0.9 : 0.35}
            />
          );
        })}
        <text x="42" y="72" className="chart-label">Crash</text>
        <text x="42" y="178" className="chart-label">No crash</text>
      </svg>
    </div>
  );
}

function ValidationTimeSeries({ rows }: { rows: Record<string, unknown>[] }) {
  const width = 760;
  const height = 300;
  const padding = { top: 18, right: 18, bottom: 46, left: 52 };
  const values = rows.map((row) => Number(row.safety_index)).filter(Number.isFinite);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const yScale = (value: number) =>
    height - padding.bottom - ((value - min) / Math.max(max - min, 1)) * (height - padding.top - padding.bottom);
  const xScale = (index: number) =>
    padding.left + (index / Math.max(rows.length - 1, 1)) * (width - padding.left - padding.right);

  if (!rows.length || !values.length) return <EmptyState icon={LineChart} title="No validation time series" />;

  const path = rows
    .map((row, index) => {
      const value = Number(row.safety_index);
      if (!Number.isFinite(value)) return null;
      return `${index === 0 ? "M" : "L"}${xScale(index)},${yScale(value)}`;
    })
    .filter(Boolean)
    .join(" ");

  return (
    <div className="chart-box">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="axis" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} className="axis" />
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const y = padding.top + tick * (height - padding.top - padding.bottom);
          return <line key={tick} x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="grid-line" />;
        })}
        <path d={path} fill="none" stroke="#2463eb" strokeWidth="3" strokeLinecap="round" />
        {rows.map((row, index) => {
          const value = Number(row.safety_index);
          if (!Number.isFinite(value) || (!boolValue(row.had_crash) && toNumber(row.crash_count, 0) <= 0)) return null;
          return (
            <g key={`${row.timestamp}-${index}`}>
              <circle cx={xScale(index)} cy={yScale(value)} r="7" fill="#d13f3f" stroke="#ffffff" strokeWidth="2" />
              <line x1={xScale(index) - 5} y1={yScale(value) - 5} x2={xScale(index) + 5} y2={yScale(value) + 5} stroke="#ffffff" strokeWidth="2" />
              <line x1={xScale(index) + 5} y1={yScale(value) - 5} x2={xScale(index) - 5} y2={yScale(value) + 5} stroke="#ffffff" strokeWidth="2" />
            </g>
          );
        })}
        <text x={padding.left} y={14} className="chart-label">{formatNumber(max)}</text>
        <text x={padding.left} y={height - padding.bottom + 18} className="chart-label">{formatNumber(min)}</text>
      </svg>
      <div className="chart-legend">
        <span><i style={{ background: "#2463eb" }} />Safety index</span>
        <span><i style={{ background: "#d13f3f" }} />Crash interval</span>
      </div>
    </div>
  );
}

function PerturbationChart({ data }: { data: Record<string, any> }) {
  const baseline = data.baseline || {};
  const timestamps = baseline.timestamps || [];
  const baseRows = (baseline.rt_si_scores || []).map((score: number, index: number) => ({
    time_bin: timestamps[index] || index,
    baseline: score
  }));
  const samples = (data.perturbed_samples || []).slice(0, 3);
  const rows = baseRows.map((row: Record<string, unknown>, index: number) => {
    const next = { ...row };
    samples.forEach((sample: any, sampleIndex: number) => {
      next[`sample_${sampleIndex + 1}`] = sample.scores?.[index];
    });
    return next;
  });
  return (
    <MultiLineChart
      rows={rows}
      xKey="time_bin"
      series={[
        { key: "baseline", label: "Baseline", color: "#111827" },
        { key: "sample_1", label: "Sample 1", color: "#2463eb" },
        { key: "sample_2", label: "Sample 2", color: "#bf7a16" },
        { key: "sample_3", label: "Sample 3", color: "#8f5fbf" }
      ]}
    />
  );
}

function DataTable({ rows, maxRows = 100 }: { rows: Record<string, unknown>[]; maxRows?: number }) {
  const visible = rows.slice(0, maxRows);
  const columns = Object.keys(visible[0] || {}).slice(0, 10);

  if (!visible.length) return <EmptyState icon={Table2} title="No rows loaded" />;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr>
        </thead>
        <tbody>
          {visible.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ icon: Icon, title }: { icon: typeof Gauge; title: string }) {
  return (
    <div className="empty-state">
      <Icon size={24} />
      <span>{title}</span>
    </div>
  );
}

export default App;
