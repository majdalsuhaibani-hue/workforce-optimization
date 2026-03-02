from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd
from pathlib import Path

from solver import solve_model

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent


def read_csv(name: str) -> pd.DataFrame:
    path = BASE_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {name} (expected at {path})")
    return pd.read_csv(path)


def build_hire_costs(costs_df: pd.DataFrame) -> pd.DataFrame:
    cols = set(costs_df.columns)
    needed = {"task", "time", "skill", "hire_cost"}
    if needed.issubset(cols):
        return costs_df[["task", "time", "skill", "hire_cost"]].drop_duplicates()
    return pd.DataFrame(columns=["task", "time", "skill", "hire_cost"])


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h2>Workforce Optimization API is running 🚀</h2>
    <p>Go to <a href="/ui">/ui</a> to open the dashboard.</p>
    <p>Go to <a href="/solve">/solve</a> to view the JSON results.</p>
    """


from fastapi import Query

@app.get("/solve")
def solve(
    w_cover: float = Query(0.35),
    w_pref: float = Query(0.25),
    w_cost: float = Query(0.20),
    w_hire: float = Query(0.20),
):
    volunteers = read_csv("volunteers.csv")
    preferences = read_csv("preferences.csv")
    skills = read_csv("skills.csv")
    availability = read_csv("availability.csv")
    demand = read_csv("demand.csv")
    costs = read_csv("costs.csv")

    # hire_costs.csv optional (fallback from costs.csv if available)
    try:
        hire_costs = read_csv("hire_costs.csv")
    except FileNotFoundError:
        hire_costs = build_hire_costs(costs)

    assignments_df, hires_df, summary = solve_model(
        volunteers, preferences, skills, availability, demand, costs, hire_costs
    )

    # Assignment cost from costs.csv
    total_assignment_cost = 0.0
    if not assignments_df.empty:
        merged = assignments_df.merge(
            costs,
            left_on=["volunteer", "task", "time"],
            right_on=["volunteer_id", "task", "time"],
            how="left",
        )
        if "cost" in merged.columns:
            total_assignment_cost = float(merged["cost"].fillna(0).sum())

    # Hiring cost from hire_costs (qty * hire_cost)
    total_hiring_cost = 0.0
    total_external_hires_qty = 0.0
    if not hires_df.empty:
        total_external_hires_qty = float(hires_df["qty"].fillna(0).sum())
        if not hire_costs.empty and "hire_cost" in hire_costs.columns:
            h = hires_df.merge(
                hire_costs,
                on=["task", "time", "skill"],
                how="left",
            )
            total_hiring_cost = float((h["qty"].fillna(0) * h["hire_cost"].fillna(0)).sum())

    meta = {
        "total_volunteers": int(len(volunteers)),
        "num_assignments": int(len(assignments_df)),
        "total_external_hires_qty": float(total_external_hires_qty),
        "total_assignment_cost": float(total_assignment_cost),
        "total_hiring_cost": float(total_hiring_cost),
        "total_cost": float(total_assignment_cost + total_hiring_cost),
    }

    return JSONResponse(
        {
            "summary": summary,
            "meta": meta,
            "assignments": assignments_df.to_dict(orient="records"),
            "external_hires": hires_df.to_dict(orient="records"),
        }
    )


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Workforce Optimization Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root{
      --nav:#0b1220; --bg:#f5f7fb; --card:#ffffff; --muted:#6b7280;
      --line:#e5e7eb; --accent:#2563eb; --shadow:0 10px 25px rgba(2,6,23,.08);
      --radius:16px;
    }
    *{box-sizing:border-box}
    body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial;background:var(--bg);color:#111827}
    .topbar{background:linear-gradient(90deg,#071021,#0b1b36);color:#fff;padding:22px}
    .topbar h1{margin:0;font-size:28px}
    .wrap{max-width:1100px;margin:18px auto;padding:0 16px}
    .row{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
    .btn{
      background:var(--accent);color:#fff;border:0;border-radius:12px;
      padding:12px 16px;font-weight:800;cursor:pointer;box-shadow:0 12px 20px rgba(37,99,235,.18)
    }
    .hint{color:var(--muted);margin-top:6px}
    .cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:14px}
    @media (max-width:980px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
    .card{
      background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);
      padding:14px 16px;border:1px solid rgba(229,231,235,.7)
    }
    .label{color:var(--muted);font-size:13px;font-weight:800}
    .value{margin-top:6px;font-size:22px;font-weight:900}
    .section{margin-top:18px}
    .section h2{margin:0 0 10px 0;font-size:22px}
    .tablewrap{
      background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);
      overflow:hidden;border:1px solid rgba(229,231,235,.7)
    }
    table{width:100%;border-collapse:collapse}
    thead th{
      background:linear-gradient(90deg,#071021,#0b1b36);color:#fff;
      text-align:left;padding:12px 14px;font-size:14px
    }
    tbody td{padding:12px 14px;border-top:1px solid var(--line);font-size:14px}
    .grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
    @media (max-width:980px){.grid2{grid-template-columns:1fr}}
    .chartCard{
      background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);
      border:1px solid rgba(229,231,235,.7);padding:14px 16px
    }
    .chartTitle{margin:0 0 10px 0;font-size:16px;font-weight:900}
    .chartBox{height:260px}
    .note{
      margin-top:10px;color:var(--muted);font-size:13px;
      background:#fff;border:1px dashed #d1d5db;border-radius:12px;padding:10px 12px
    }
    .err{
      display:none;margin-top:10px;border-radius:12px;
      background:#fff1f2;border:1px solid #fecdd3;color:#9f1239;
      padding:10px 12px;font-size:13px;white-space:pre-wrap
    }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>Workforce Optimization Dashboard</h1>
  </div>

  <div class="wrap">
    <div class="row">
    <div class="card" style="margin-bottom:14px;max-width:720px">
  <div class="label">Objective Weights (Presets + Sliders + Auto-normalize)</div>

  <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
    <select id="preset" style="padding:10px 12px;border-radius:10px;border:1px solid #e5e7eb;min-width:240px">
      <option value="balanced" selected>Balanced (Default)</option>
      <option value="coverage">Max Coverage</option>
      <option value="satisfaction">Max Volunteer Satisfaction</option>
      <option value="min_cost">Min Assignment Cost</option>
      <option value="min_hire">Min Hiring Cost</option>
    </select>

    <button class="btn" onclick="applyPreset()" type="button">Apply Preset</button>
    <button class="btn" onclick="resetDefault()" type="button" style="background:#111827">Reset to Default</button>
  </div>

  <div class="hint" style="margin-top:10px">
    Sliders can be any values. We auto-normalize them so that (W_cover + W_pref + W_cost + W_hire = 1).
  </div>

  <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div>
      <div class="label">W_cover (Coverage)</div>
      <input id="s_cover" type="range" min="0" max="100" value="35" oninput="updateWeightsUI()"
             style="width:100%">
      <div class="hint">Raw: <b id="raw_cover">35</b> | Normalized: <b id="n_cover">0.35</b></div>
    </div>

    <div>
      <div class="label">W_pref (Preference)</div>
      <input id="s_pref" type="range" min="0" max="100" value="25" oninput="updateWeightsUI()"
             style="width:100%">
      <div class="hint">Raw: <b id="raw_pref">25</b> | Normalized: <b id="n_pref">0.25</b></div>
    </div>

    <div>
      <div class="label">W_cost (Assignment Cost)</div>
      <input id="s_cost" type="range" min="0" max="100" value="20" oninput="updateWeightsUI()"
             style="width:100%">
      <div class="hint">Raw: <b id="raw_cost">20</b> | Normalized: <b id="n_cost">0.20</b></div>
    </div>

    <div>
      <div class="label">W_hire (Hiring Cost)</div>
      <input id="s_hire" type="range" min="0" max="100" value="20" oninput="updateWeightsUI()"
             style="width:100%">
      <div class="hint">Raw: <b id="raw_hire">20</b> | Normalized: <b id="n_hire">0.20</b></div>
    </div>
  </div>
</div>
      <button class="btn" onclick="runOpt()">Run Optimization</button>
      <div>
        <div class="hint">Click Run Optimization to generate and display the results.</div>
        <div class="hint">The dashboard shows costs, volunteers, assignments, and the assignment table.</div>
        <div id="errBox" class="err"></div>
      </div>
    </div>

    <div class="cards">
      <div class="card"><div class="label">Status</div><div class="value" id="status">-</div></div>
      <div class="card"><div class="label">Objective</div><div class="value" id="objective">-</div></div>
      <div class="card"><div class="label">Number of Volunteers</div><div class="value" id="nVol">-</div></div>
      <div class="card"><div class="label">Number of Assignments</div><div class="value" id="nAsg">-</div></div>
      <div class="card"><div class="label">Assignment Cost</div><div class="value" id="asgCost">-</div></div>
      <div class="card"><div class="label">Hiring Cost</div><div class="value" id="hireCost">-</div></div>
      <div class="card"><div class="label">Total Cost</div><div class="value" id="totalCost">-</div></div>
      <div class="card"><div class="label">External Hires</div><div class="value" id="nHire">-</div></div>
    </div>

    <div class="section">
      <h2>Analytics</h2>
      <div class="grid2">
        <div class="chartCard">
          <div class="chartTitle">Assignments per Task</div>
          <div class="chartBox"><canvas id="taskChart"></canvas></div>
        </div>
        <div class="chartCard">
          <div class="chartTitle">Assignments by Time</div>
          <div class="chartBox"><canvas id="timeChart"></canvas></div>
        </div>
      </div>
      <div class="note">Note: The page fetches the results from <b>/solve</b>.</div>
    </div>

    <div class="section">
      <h2>Assignments</h2>
      <div class="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Volunteer</th>
              <th>Task</th>
              <th>Time</th>
              <th>Skill (if any)</th>
            </tr>
          </thead>
          <tbody id="asgBody">
            <tr><td colspan="4" style="color:#6b7280">Click Run Optimization to display results…</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

<script>
let taskChartInstance = null;
let timeChartInstance = null;

function fmt(x){
  if (x === null || x === undefined) return "-";
  if (typeof x === "number") return x.toFixed(2);
  return String(x);
}

function showErr(msg){
  const box = document.getElementById("errBox");
  box.style.display = "block";
  box.textContent = msg;
}

function clearErr(){
  const box = document.getElementById("errBox");
  box.style.display = "none";
  box.textContent = "";
}

function buildBarChart(canvasId, labels, values, title){
  const ctx = document.getElementById(canvasId);
  const maxVal = values.length ? Math.max(...values) : 0;
  const suggestedMax = maxVal <= 0 ? 1 : Math.ceil(maxVal * 1.2);

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: title, data: values }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          suggestedMax,
          ticks: { stepSize: 1 }
        }
      }
    }
  });
}
function getRawWeights(){
  return {
    cover: Number(document.getElementById("s_cover").value || 0),
    pref:  Number(document.getElementById("s_pref").value || 0),
    cost:  Number(document.getElementById("s_cost").value || 0),
    hire:  Number(document.getElementById("s_hire").value || 0),
  };
}

function normalizeWeights(w){
  const sum = w.cover + w.pref + w.cost + w.hire;
  if (sum <= 0){
    return { cover: 0.25, pref: 0.25, cost: 0.25, hire: 0.25 };
  }
  return {
    cover: w.cover / sum,
    pref:  w.pref  / sum,
    cost:  w.cost  / sum,
    hire:  w.hire  / sum,
  };
}

function updateWeightsUI(){
  const raw = getRawWeights();
  const n = normalizeWeights(raw);

  document.getElementById("raw_cover").textContent = raw.cover;
  document.getElementById("raw_pref").textContent  = raw.pref;
  document.getElementById("raw_cost").textContent  = raw.cost;
  document.getElementById("raw_hire").textContent  = raw.hire;

  document.getElementById("n_cover").textContent = n.cover.toFixed(2);
  document.getElementById("n_pref").textContent  = n.pref.toFixed(2);
  document.getElementById("n_cost").textContent  = n.cost.toFixed(2);
  document.getElementById("n_hire").textContent  = n.hire.toFixed(2);
}

function applyPreset(){
  const presets = {
    balanced:     { cover:35, pref:25, cost:20, hire:20 },
    coverage:     { cover:70, pref:20, cost:5,  hire:5  },
    satisfaction: { cover:20, pref:70, cost:5,  hire:5  },
    min_cost:     { cover:20, pref:20, cost:50, hire:10 },
    min_hire:     { cover:20, pref:20, cost:10, hire:50 }
  };

  const key = document.getElementById("preset").value;
  const p = presets[key] || presets.balanced;

  document.getElementById("s_cover").value = p.cover;
  document.getElementById("s_pref").value  = p.pref;
  document.getElementById("s_cost").value  = p.cost;
  document.getElementById("s_hire").value  = p.hire;

  updateWeightsUI();
}

function resetDefault(){
  document.getElementById("preset").value = "balanced";
  applyPreset();
}

// تحديث أول ما تفتح الصفحة
updateWeightsUI();
async function runOpt(){
  clearErr();

  let r;
  try{
 const raw = getRawWeights();
const n = normalizeWeights(raw);

const qs = new URLSearchParams({
  w_cover: n.cover,
  w_pref:  n.pref,
  w_cost:  n.cost,
  w_hire:  n.hire
}).toString();

r = await fetch("/solve?" + qs, { cache: "no-store" });
  }catch(e){
    showErr("Network error while calling /solve\\n" + e);
    return;
  }

  if (!r.ok){
    const t = await r.text();
    showErr("Error from /solve (" + r.status + ")\\n" + t);
    return;
  }

  const data = await r.json();
  const s = data.summary || {};
  const meta = data.meta || {};
  const assignments = data.assignments || [];
  const hires = data.external_hires || [];

  document.getElementById("status").textContent = fmt(s.status);
  document.getElementById("objective").textContent = fmt(s.objective_value);

  document.getElementById("nVol").textContent = (typeof meta.total_volunteers === "number") ? meta.total_volunteers : "-";
  document.getElementById("nAsg").textContent = (typeof meta.num_assignments === "number") ? meta.num_assignments : assignments.length;

  document.getElementById("asgCost").textContent = fmt(meta.total_assignment_cost);
  document.getElementById("hireCost").textContent = fmt(meta.total_hiring_cost);
  document.getElementById("totalCost").textContent = fmt(meta.total_cost);
  document.getElementById("nHire").textContent = (typeof meta.total_external_hires_qty === "number") ? meta.total_external_hires_qty : hires.length;

  const body = document.getElementById("asgBody");
  body.innerHTML = "";
  if (assignments.length === 0){
    body.innerHTML = '<tr><td colspan="4" style="color:#6b7280">No assignments returned.</td></tr>';
  } else {
    for (const a of assignments){
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${fmt(a.volunteer)}</td>
        <td>${fmt(a.task)}</td>
        <td>${fmt(a.time)}</td>
        <td>${fmt(a.skill)}</td>
      `;
      body.appendChild(tr);
    }
  }

  // Charts
  const taskCounts = {};
  for (const a of assignments){
    taskCounts[a.task] = (taskCounts[a.task] || 0) + 1;
  }
  const timeCounts = {};
  for (const a of assignments){
    timeCounts[a.time] = (timeCounts[a.time] || 0) + 1;
  }

  if (taskChartInstance) taskChartInstance.destroy();
  if (timeChartInstance) timeChartInstance.destroy();

  taskChartInstance = buildBarChart("taskChart", Object.keys(taskCounts), Object.values(taskCounts), "Assignments per Task");
  timeChartInstance = buildBarChart("timeChart", Object.keys(timeCounts), Object.values(timeCounts), "Assignments by Time");
}
</script>

</body>
</html>
"""
