import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Database,
  Flame,
  Grid3X3,
  Loader2,
  Play,
  RefreshCcw,
  Save,
  Trash2,
  Table2
} from "lucide-react";
import "./styles.css";

type Dataset = {
  name: string;
  path: string;
  ticker: string | null;
  period: string | null;
  interval: string | null;
  rows: number | null;
  date_min: string | null;
  date_max: string | null;
  time_min: string | null;
  time_max: string | null;
  tickers: string[];
};

type RecordRow = Record<string, string | number | boolean | null>;

type BacktestResponse = {
  results: RecordRow[];
  summary: RecordRow[];
  meta: {
    market_rows: number;
    result_rows: number;
    tickers: string[];
  };
};

type GridResponse = {
  results: RecordRow[];
  fills: RecordRow[];
  summary_by_strategy: RecordRow[];
  summary_by_placement: RecordRow[];
  summary_by_strategy_placement: RecordRow[];
  meta: {
    market_rows: number;
    result_rows: number;
    tickers: string[];
    fill_rows_returned: number;
    fill_rows_total: number;
  };
};

const API_BASE = "";
const PLACEMENTS = ["market", "marketable_limit", "aggressive_limit", "midpoint_limit", "passive_limit", "adaptive_limit"];
const DEFAULT_ADAPTIVE_WEIGHTS = {
  bullish_signal_multiplier: 1.4,
  bearish_signal_multiplier: 0.7,
  spread_penalty_multiplier: 0.75,
  volatility_penalty_multiplier: 0.85,
  liquidity_boost_multiplier: 1.2,
  urgency_weight: 1.0
};
const ADAPTIVE_PRESETS_KEY = "smart-execution-adaptive-presets";
const ADAPTIVE_SELECTED_KEY = "smart-execution-adaptive-selected";

const ADAPTIVE_FIELDS = [
  { key: "bullish_signal_multiplier", label: "Bullish signal", step: 0.05, min: 0.1, max: 3 },
  { key: "bearish_signal_multiplier", label: "Bearish signal", step: 0.05, min: 0.1, max: 3 },
  { key: "spread_penalty_multiplier", label: "Spread penalty", step: 0.05, min: 0.1, max: 3 },
  { key: "volatility_penalty_multiplier", label: "Volatility penalty", step: 0.05, min: 0.1, max: 3 },
  { key: "liquidity_boost_multiplier", label: "Liquidity boost", step: 0.05, min: 0.1, max: 3 },
  { key: "urgency_weight", label: "Urgency weight", step: 0.05, min: 0, max: 5 }
] as const;

type AdaptiveWeights = typeof DEFAULT_ADAPTIVE_WEIGHTS;
type AdaptivePreset = {
  name: string;
  weights: AdaptiveWeights;
};

function App() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetPath, setDatasetPath] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [maxOrders, setMaxOrders] = useState(1);
  const [placements, setPlacements] = useState<string[]>(["market", "passive_limit", "adaptive_limit"]);
  const [adaptiveWeights, setAdaptiveWeights] = useState(DEFAULT_ADAPTIVE_WEIGHTS);
  const [adaptivePresetName, setAdaptivePresetName] = useState("");
  const [adaptivePresetSelection, setAdaptivePresetSelection] = useState("Default");
  const [adaptivePresets, setAdaptivePresets] = useState<AdaptivePreset[]>([]);
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [grid, setGrid] = useState<GridResponse | null>(null);
  const [tapeStrategy, setTapeStrategy] = useState("all");
  const [tapePlacement, setTapePlacement] = useState("all");
  const [mode, setMode] = useState<"backtest" | "grid">("backtest");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    const selected = datasets.find((dataset) => dataset.path === datasetPath);
    if (!selected) {
      return;
    }
    setStartDate(normalizeDateValue(selected.date_min));
    setEndDate(normalizeDateValue(selected.date_max));
    setStartTime(normalizeTimeValue(selected.time_min));
    setEndTime(normalizeTimeValue(selected.time_max));
  }, [datasets, datasetPath]);

  useEffect(() => {
    const presets = readAdaptivePresets();
    setAdaptivePresets(presets);
    const selected = window.sessionStorage.getItem(ADAPTIVE_SELECTED_KEY) || "Default";
    setAdaptivePresetSelection(selected);
    const preset = presets.find((item) => item.name === selected);
    if (preset) {
      setAdaptiveWeights(preset.weights);
    }
  }, []);

  async function loadDatasets() {
    setError(null);
    const response = await fetch(`${API_BASE}/api/datasets`);
    if (!response.ok) {
      setError("Unable to load datasets.");
      return;
    }
    const payload = await response.json();
    setDatasets(payload.datasets);
    if (!datasetPath && payload.datasets.length > 0) {
      setDatasetPath(payload.datasets[0].path);
    }
  }

  async function runBacktest() {
    if (!datasetPath) {
      setError("Select a processed CSV dataset.");
      return;
    }
    setMode("backtest");
    setLoading(true);
    setError(null);
    try {
      const response = await postJson<BacktestResponse>("/api/backtest", {
        input_csv: datasetPath,
        max_orders_per_ticker: maxOrders,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        start_time: startTime || undefined,
        end_time: endTime || undefined,
        adaptive_weights: adaptiveWeights
      });
      setBacktest(response);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }

  async function runGrid() {
    if (!datasetPath) {
      setError("Select a processed CSV dataset.");
      return;
    }
    setMode("grid");
    setLoading(true);
    setError(null);
    try {
      const response = await postJson<GridResponse>("/api/execution-grid", {
        input_csv: datasetPath,
        max_orders_per_ticker: maxOrders,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        start_time: startTime || undefined,
        end_time: endTime || undefined,
        placement_styles: placements,
        adaptive_weights: adaptiveWeights,
        fill_row_limit: 400
      });
      setGrid(response);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }

  const activeSummary = mode === "grid" && grid ? grid.summary_by_strategy : backtest?.summary ?? [];
  const metricCards = useMemo(() => buildMetricCards(activeSummary), [activeSummary]);
  const tapeRows = useMemo(
    () => filterTapeRows(grid?.fills ?? [], tapeStrategy, tapePlacement),
    [grid, tapeStrategy, tapePlacement]
  );
  const tapeStrategies = useMemo(
    () => ["all", ...unique((grid?.fills ?? []).map((row) => String(row.strategy)))],
    [grid]
  );
  const tapePlacements = useMemo(
    () => ["all", ...unique((grid?.fills ?? []).map((row) => String(row.placement_style)))],
    [grid]
  );

  function saveAdaptivePreset() {
    const name = adaptivePresetName.trim();
    if (!name) {
      setError("Enter a preset name before saving.");
      return;
    }
    const nextPreset: AdaptivePreset = { name, weights: adaptiveWeights };
    const nextPresets = upsertPreset(adaptivePresets, nextPreset);
    setAdaptivePresets(nextPresets);
    setAdaptivePresetSelection(name);
    window.sessionStorage.setItem(ADAPTIVE_PRESETS_KEY, JSON.stringify(nextPresets));
    window.sessionStorage.setItem(ADAPTIVE_SELECTED_KEY, name);
    setAdaptivePresetName("");
  }

  function applyAdaptivePreset(name: string) {
    const preset = adaptivePresets.find((item) => item.name === name);
    setAdaptivePresetSelection(name);
    window.sessionStorage.setItem(ADAPTIVE_SELECTED_KEY, name);
    if (preset) {
      setAdaptiveWeights(preset.weights);
    } else if (name === "Default") {
      setAdaptiveWeights(DEFAULT_ADAPTIVE_WEIGHTS);
    }
  }

  function deleteAdaptivePreset(name: string) {
    if (name === "Default") {
      return;
    }
    const nextPresets = adaptivePresets.filter((item) => item.name !== name);
    setAdaptivePresets(nextPresets);
    window.sessionStorage.setItem(ADAPTIVE_PRESETS_KEY, JSON.stringify(nextPresets));
    if (adaptivePresetSelection === name) {
      setAdaptivePresetSelection("Default");
      window.sessionStorage.setItem(ADAPTIVE_SELECTED_KEY, "Default");
      setAdaptiveWeights(DEFAULT_ADAPTIVE_WEIGHTS);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Activity size={24} />
          <div>
            <h1>Smart Execution</h1>
            <span>Research dashboard</span>
          </div>
        </div>

        <section className="panel">
          <label htmlFor="dataset">Dataset</label>
          <div className="selectRow">
            <Database size={16} />
            <select id="dataset" value={datasetPath} onChange={(event) => setDatasetPath(event.target.value)}>
              {datasets.map((dataset) => (
                <option key={dataset.path} value={dataset.path}>
                  {formatDatasetLabel(dataset)}
                </option>
              ))}
            </select>
            <button className="iconButton" onClick={loadDatasets} title="Refresh datasets" type="button">
              <RefreshCcw size={16} />
            </button>
          </div>
          {selectedDatasetSummary(datasets, datasetPath) ? (
            <div className="datasetMeta">
              {selectedDatasetSummary(datasets, datasetPath)?.map((line) => (
                <div key={line}>{line}</div>
              ))}
            </div>
          ) : null}
          <div className="rangeGrid">
            <label className="weightField">
              <span>Start date</span>
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label className="weightField">
              <span>End date</span>
              <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            </label>
            <label className="weightField">
              <span>Start time</span>
              <input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
            </label>
            <label className="weightField">
              <span>End time</span>
              <input type="time" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
            </label>
          </div>
          <label htmlFor="maxOrders">Parent orders per ticker</label>
          <input
            id="maxOrders"
            min={1}
            max={20}
            type="number"
            value={maxOrders}
            onChange={(event) => setMaxOrders(Number(event.target.value))}
          />
        </section>

        <section className="panel">
          <div className="panelHeader">
            <Grid3X3 size={16} />
            <span>Placements</span>
          </div>
          <div className="checks">
            {PLACEMENTS.map((placement) => (
              <label className="check" key={placement}>
                <input
                  type="checkbox"
                  checked={placements.includes(placement)}
                  onChange={() => togglePlacement(placement, placements, setPlacements)}
                />
                <span>{placement}</span>
              </label>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panelHeader">
            <BarChart3 size={16} />
            <span>Adaptive Weights</span>
          </div>
          <div className="presetRow">
            <label className="weightField">
              <span>Preset</span>
              <select value={adaptivePresetSelection} onChange={(event) => applyAdaptivePreset(event.target.value)}>
                <option value="Default">Default</option>
                {adaptivePresets.map((preset) => (
                  <option key={preset.name} value={preset.name}>
                    {preset.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="weightField">
              <span>Save as</span>
              <input
                type="text"
                value={adaptivePresetName}
                onChange={(event) => setAdaptivePresetName(event.target.value)}
                placeholder="Current session"
              />
            </label>
          </div>
          <div className="presetActions">
            <button className="iconButton wide" onClick={saveAdaptivePreset} type="button">
              <Save size={14} />
              Save preset
            </button>
            <button className="iconButton wide danger" onClick={() => applyAdaptivePreset("Default")} type="button">
              Reset defaults
            </button>
          </div>
          <div className="weightGrid">
            {ADAPTIVE_FIELDS.map((field) => (
              <label className="weightField" key={field.key}>
                <span>{field.label}</span>
                <input
                  min={field.min}
                  max={field.max}
                  step={field.step}
                  type="number"
                  value={adaptiveWeights[field.key]}
                  onChange={(event) =>
                    setAdaptiveWeights({
                      ...adaptiveWeights,
                      [field.key]: Number(event.target.value)
                    })
                  }
                />
              </label>
            ))}
          </div>
          {adaptivePresets.length > 0 ? (
            <div className="presetList">
              {adaptivePresets.map((preset) => (
                <div className="presetItem" key={preset.name}>
                  <span>{preset.name}</span>
                  <button className="iconButton tiny danger" onClick={() => deleteAdaptivePreset(preset.name)} type="button">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <div className="actions">
          <button className="primary" onClick={runBacktest} disabled={loading || !datasetPath} type="button">
            {loading && mode === "backtest" ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
            Run Backtest
          </button>
          <button className="secondary" onClick={runGrid} disabled={loading || !datasetPath || placements.length === 0} type="button">
            {loading && mode === "grid" ? <Loader2 className="spin" size={16} /> : <BarChart3 size={16} />}
            Run Grid
          </button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h2>{mode === "grid" ? "Execution Grid" : "Strategy Backtest"}</h2>
            <span>{datasetPath || "No dataset selected"}</span>
          </div>
          <div className="status">
            {error ? <span className="error">{error}</span> : <span>{loading ? "Running" : "Ready"}</span>}
          </div>
        </header>

        <section className="metrics">
          {metricCards.map((card) => (
            <div className="metric" key={card.label}>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
            </div>
          ))}
        </section>

        <section className="gridTwo">
          <div className="surface">
            <div className="sectionHeader">
              <BarChart3 size={18} />
              <h3>Implementation Shortfall</h3>
            </div>
            <BarChart data={activeSummary} labelKey="strategy" valueKey="implementation_shortfall_bps" />
          </div>
          <div className="surface">
            <div className="sectionHeader">
              <Flame size={18} />
              <h3>Fill Rate</h3>
            </div>
            <BarChart data={activeSummary} labelKey="strategy" valueKey="fill_rate" percent />
          </div>
        </section>

        {mode === "grid" && grid ? (
          <section className="surface">
            <div className="sectionHeader">
              <Grid3X3 size={18} />
              <h3>Strategy / Placement Heatmap</h3>
            </div>
            <Heatmap data={grid.summary_by_strategy_placement} />
          </section>
        ) : null}

        <section className="surface">
          <div className="tableHeader">
            <div className="sectionHeader">
              <Table2 size={18} />
              <h3>{mode === "grid" ? "Fill Tape" : "Strategy Summary"}</h3>
            </div>
            {mode === "grid" && grid ? (
              <FillTapeFilters
                strategies={tapeStrategies}
                placements={tapePlacements}
                selectedStrategy={tapeStrategy}
                selectedPlacement={tapePlacement}
                onStrategyChange={setTapeStrategy}
                onPlacementChange={setTapePlacement}
                visibleRows={tapeRows.length}
                totalRows={grid.fills.length}
              />
            ) : null}
          </div>
          <DataTable rows={mode === "grid" && grid ? tapeRows : activeSummary} limit={16} />
        </section>
      </section>
    </main>
  );
}

function selectedDatasetSummary(datasets: Dataset[], datasetPath: string): string[] | null {
  const dataset = datasets.find((item) => item.path === datasetPath);
  if (!dataset) {
    return null;
  }
  const summary: string[] = [];
  if (dataset.ticker || dataset.period || dataset.interval) {
    summary.push([dataset.ticker, dataset.period, dataset.interval].filter(Boolean).join(" / "));
  }
  if (dataset.rows !== null) {
    summary.push(`${dataset.rows.toLocaleString()} rows`);
  }
  if (dataset.date_min || dataset.date_max) {
    summary.push(`Dates: ${formatRangeValue(dataset.date_min)} to ${formatRangeValue(dataset.date_max)}`);
  }
  if (dataset.time_min || dataset.time_max) {
    summary.push(`Times: ${formatRangeValue(dataset.time_min)} to ${formatRangeValue(dataset.time_max)}`);
  }
  if (dataset.tickers.length > 0) {
    summary.push(`Tickers: ${dataset.tickers.join(", ")}`);
  }
  return summary.length > 0 ? summary : null;
}

function formatDatasetLabel(dataset: Dataset): string {
  const parts = [dataset.ticker || dataset.name];
  if (dataset.period || dataset.interval) {
    parts.push([dataset.period, dataset.interval].filter(Boolean).join(" / "));
  }
  return parts.filter(Boolean).join(" - ");
}

function formatRangeValue(value: string | null): string {
  if (!value) {
    return "All";
  }
  return value;
}

function normalizeDateValue(value: string | null): string {
  if (!value) {
    return "";
  }
  return value.slice(0, 10);
}

function normalizeTimeValue(value: string | null): string {
  if (!value) {
    return "";
  }
  return value.slice(0, 8);
}

function FillTapeFilters({
  strategies,
  placements,
  selectedStrategy,
  selectedPlacement,
  onStrategyChange,
  onPlacementChange,
  visibleRows,
  totalRows
}: {
  strategies: string[];
  placements: string[];
  selectedStrategy: string;
  selectedPlacement: string;
  onStrategyChange: (value: string) => void;
  onPlacementChange: (value: string) => void;
  visibleRows: number;
  totalRows: number;
}) {
  return (
    <div className="tableControls">
      <label>
        <span>Strategy</span>
        <select value={selectedStrategy} onChange={(event) => onStrategyChange(event.target.value)}>
          {strategies.map((strategy) => (
            <option key={strategy} value={strategy}>
              {strategy === "all" ? "All strategies" : strategy}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Placement</span>
        <select value={selectedPlacement} onChange={(event) => onPlacementChange(event.target.value)}>
          {placements.map((placement) => (
            <option key={placement} value={placement}>
              {placement === "all" ? "All placements" : placement}
            </option>
          ))}
        </select>
      </label>
      <div className="rowCount">
        {visibleRows} / {totalRows}
      </div>
    </div>
  );
}

function BarChart({
  data,
  labelKey,
  valueKey,
  percent = false
}: {
  data: RecordRow[];
  labelKey: string;
  valueKey: string;
  percent?: boolean;
}) {
  const values = data.map((row) => toNumber(row[valueKey])).filter((value) => Number.isFinite(value));
  const max = Math.max(...values.map((value) => Math.abs(value)), percent ? 1 : 0, 1);
  if (!data.length) {
    return <div className="empty">Run an analysis to populate this chart.</div>;
  }
  return (
    <div className="bars">
      {data.map((row) => {
        const value = toNumber(row[valueKey]);
        const width = Math.max(2, Math.abs(value) / max * 100);
        return (
          <div className="barRow" key={`${row[labelKey]}-${valueKey}`}>
            <span>{String(row[labelKey])}</span>
            <div className="barTrack">
              <div className={value < 0 ? "bar negative" : "bar"} style={{ width: `${width}%` }} />
            </div>
            <b>{formatMetric(value, percent)}</b>
          </div>
        );
      })}
    </div>
  );
}

function Heatmap({ data }: { data: RecordRow[] }) {
  if (!data.length) {
    return <div className="empty">Run an execution grid to populate this view.</div>;
  }
  const strategies = unique(data.map((row) => String(row.strategy)));
  const placements = unique(data.map((row) => String(row.placement_style)));
  const values = data.map((row) => toNumber(row.implementation_shortfall_bps));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return (
    <div className="heatmap" style={{ gridTemplateColumns: `140px repeat(${placements.length}, minmax(104px, 1fr))` }}>
      <div />
      {placements.map((placement) => (
        <div className="heatHead" key={placement}>{placement}</div>
      ))}
      {strategies.map((strategy) => (
        <React.Fragment key={strategy}>
          <div className="heatSide">{strategy}</div>
          {placements.map((placement) => {
            const row = data.find((candidate) => candidate.strategy === strategy && candidate.placement_style === placement);
            const value = row ? toNumber(row.implementation_shortfall_bps) : 0;
            return (
              <div className="heatCell" key={`${strategy}-${placement}`} style={{ background: heatColor(value, min, max) }}>
                <span>{formatMetric(value, false)}</span>
              </div>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
}

function DataTable({ rows, limit }: { rows: RecordRow[]; limit: number }) {
  if (!rows.length) {
    return <div className="empty">No rows available.</div>;
  }
  const columns = Object.keys(rows[0]).slice(0, 10);
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, limit).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{formatCell(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json();
}

function togglePlacement(value: string, selected: string[], setSelected: (next: string[]) => void) {
  if (selected.includes(value)) {
    setSelected(selected.filter((item) => item !== value));
  } else {
    setSelected([...selected, value]);
  }
}

function filterTapeRows(rows: RecordRow[], strategy: string, placement: string) {
  return rows.filter((row) => {
    const strategyMatches = strategy === "all" || row.strategy === strategy;
    const placementMatches = placement === "all" || row.placement_style === placement;
    return strategyMatches && placementMatches;
  });
}

function readAdaptivePresets(): AdaptivePreset[] {
  if (typeof window === "undefined") {
    return [];
  }
  const raw = window.sessionStorage.getItem(ADAPTIVE_PRESETS_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as AdaptivePreset[];
    return parsed.filter((preset) => preset && typeof preset.name === "string" && preset.weights);
  } catch {
    return [];
  }
}

function upsertPreset(presets: AdaptivePreset[], nextPreset: AdaptivePreset): AdaptivePreset[] {
  const filtered = presets.filter((preset) => preset.name !== nextPreset.name);
  return [...filtered, nextPreset].sort((left, right) => left.name.localeCompare(right.name));
}

function buildMetricCards(summary: RecordRow[]) {
  return [
    { label: "Strategies", value: String(unique(summary.map((row) => String(row.strategy))).length || 0) },
    { label: "Avg Shortfall", value: formatMetric(mean(summary, "implementation_shortfall_bps"), false) },
    { label: "Avg Fill Rate", value: formatMetric(mean(summary, "fill_rate"), true) },
    { label: "Avg Impact", value: formatMetric(mean(summary, "impact_cost_bps"), false) }
  ];
}

function mean(rows: RecordRow[], key: string) {
  const values = rows.map((row) => toNumber(row[key])).filter((value) => Number.isFinite(value));
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function toNumber(value: unknown) {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number(value);
  return 0;
}

function unique<T>(values: T[]) {
  return Array.from(new Set(values));
}

function formatMetric(value: number, percent: boolean) {
  if (!Number.isFinite(value)) return "n/a";
  if (percent) return `${(value * 100).toFixed(1)}%`;
  return `${value.toFixed(2)} bps`;
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  return String(value);
}

function heatColor(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return "#eef2f7";
  const span = Math.max(max - min, 1e-9);
  const t = (value - min) / span;
  const hue = 150 - t * 120;
  return `hsl(${hue}, 55%, 72%)`;
}

function errorText(err: unknown) {
  return err instanceof Error ? err.message : "Request failed.";
}

createRoot(document.getElementById("root")!).render(<App />);
