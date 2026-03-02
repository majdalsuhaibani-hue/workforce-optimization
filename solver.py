import pandas as pd
import pulp as pl

def solve_model(volunteers_df, preferences_df, skills_df,
                availability_df, demand_df, costs_df, hire_costs_df,
                w_cover=0.35, w_pref=0.25, w_cost=0.20, w_hire=0.20):

    vol = volunteers_df["volunteer_id"].astype(str).tolist()
    tasks = preferences_df["task"].astype(str).unique().tolist()
    skills = skills_df["skill"].astype(str).unique().tolist()
    times = sorted(list(set(
        availability_df["time"].astype(str).tolist()
        + demand_df["time"].astype(str).tolist()
    )))

    sigma = {(r.volunteer_id, r.skill): r.has_skill for r in skills_df.itertuples()}
    pref = {(r.volunteer_id, r.task): r.preference for r in preferences_df.itertuples()}
    avail = {(r.volunteer_id, r.time): r.available for r in availability_df.itertuples()}
    demand = {(r.task, r.time, r.skill): r.demand for r in demand_df.itertuples()}
    costs = {(r.volunteer_id, r.task, r.time): r.cost for r in costs_df.itertuples()}
    hire_cost = {(r.task, r.time, r.skill): r.hire_cost for r in hire_costs_df.itertuples()}

    model = pl.LpProblem("Volunteer_Allocation", pl.LpMaximize)

    x = pl.LpVariable.dicts("x", (vol, tasks, times), 0, 1, pl.LpBinary)
    Cov = pl.LpVariable.dicts("Cov", (tasks, times, skills), 0)
    h = pl.LpVariable.dicts("hire", (tasks, times, skills), 0)

    # 🎯 Objective with dynamic weights
    model += (
        w_cover * pl.lpSum(Cov[s][t][k] for s in tasks for t in times for k in skills)
        + w_pref * pl.lpSum(pref.get((v, s), 0) * x[v][s][t]
                            for v in vol for s in tasks for t in times)
        - w_cost * pl.lpSum(costs.get((v, s, t), 0) * x[v][s][t]
                            for v in vol for s in tasks for t in times)
        - w_hire * pl.lpSum(hire_cost.get((s, t, k), 0) * h[s][t][k]
                            for s in tasks for t in times for k in skills)
    )

    # Constraints
    for s in tasks:
        for t in times:
            for k in skills:
                model += Cov[s][t][k] + h[s][t][k] == demand.get((s, t, k), 0)
                model += Cov[s][t][k] == pl.lpSum(
                    sigma.get((v, k), 0) * x[v][s][t] for v in vol
                )

    for v in vol:
        for t in times:
            model += pl.lpSum(x[v][s][t] for s in tasks) <= 1
            for s in tasks:
                model += x[v][s][t] <= avail.get((v, t), 0)

    model.solve(pl.PULP_CBC_CMD(msg=False))

    status = pl.LpStatus[model.status]
    objective = pl.value(model.objective)

    assignments = []
    for v in vol:
        for s in tasks:
            for t in times:
                if x[v][s][t].value() == 1:
                    assignments.append({"volunteer": v, "task": s, "time": t})

    hires = []
    for s in tasks:
        for t in times:
            for k in skills:
                val = h[s][t][k].value()
                if val and val > 0:
                    hires.append({"task": s, "time": t, "skill": k, "qty": val})

    return (
        pd.DataFrame(assignments),
        pd.DataFrame(hires),
        {"status": status, "objective_value": objective}
    )
