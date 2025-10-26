# EmployeeOptimizer (Optimizador de Plantilla)

A Streamlit app to compute the minimum number of employees required to cover weekend shifts (Saturdays and Sundays) each week, assuming every employee has one weekend off per month. The UI is in Spanish and the optimization model uses PuLP (CBC solver) with an exact precalculation of how each work pattern contributes to each week.

This README was generated from the application's source (`app.py`) and documents usage, model logic, configuration options and known limitations.

---

## Features

- Enumerates all possible 3-week work patterns (combinations of Saturdays, Sundays and full weekends).
- Allows multiple employee "types" with configurable maximum headcount and number of services/month.
- Precalculates exact per-week contributions of each pattern given all possible rest weeks.
- Builds and solves an integer linear program (minimize total employees) that ensures weekly coverage for Saturdays and Sundays.
- Generates a detailed weekly schedule template and an Excel download of the assignment.
- Interactive UI (Streamlit) to change demand and employee-type settings.

---

## Requirements

- Python 3.8+
- Packages:
  - streamlit
  - pulp
  - pandas
  - openpyxl

Example quick install:
```bash
python -m pip install streamlit pulp pandas openpyxl
```

(Consider pinning versions in a requirements.txt if needed.)

---

## How it works (high level)

1. generate_3week_patterns()
   - Generates all possible distributions of weekend services across 3 work weeks:
     - s = number of Saturdays alone
     - d = number of Sundays alone
     - c = number of full weekends (both days)
   - Keeps patterns with 1 to 3 worked weekends in the 3-week block.

2. precalculate_contributions(master_pattern_map, WEEKS)
   - For each pattern and for each possible rest week (1..4) the employee can take off in the month, deterministically assigns which of the other 3 weeks are:
     - "Finde Completo" (full weekend), "Sábado", "Domingo", or "Descanso".
   - Produces a contribution map:
     { pattern_str: { rest_week: { week: (s_contrib, d_contrib) } } }
   - These are integer contributions (0 or 1) used in coverage constraints.

   IMPORTANT: The deterministic assignment logic here is identical to that used to build the final schedule preview. This ensures that the coverage computed by the model matches the schedule exported to Excel.

3. Model variables and objective
   - N_vars[type] : total employees of each type (integer)
   - x_vars[type][pattern][rest_week] : number of employees of that type assigned to that pattern and rest week (integer)
   - Objective: minimize sum(N_vars)

4. Constraints
   - For each week w:
     - Sum over all types/patterns/rest_weeks of x_vars * contribution_map[pattern][rest_week][w][0] >= DEMAND_SATURDAY
     - Sum over all types/patterns/rest_weeks of x_vars * contribution_map[pattern][rest_week][w][1] >= DEMAND_SUNDAY
   - For each type:
     - Sum over patterns/rest_weeks of x_vars == N_vars[type]
     - N_vars[type] <= max_employees[type]

5. After solving
   - If optimal, the app presents:
     - Total minimum employees (rounded up)
     - Per-type totals
     - A summary by pattern (services/month, employees, contributions)
     - Downloadable Excel with the weekly schedule template and totals
   - If infeasible, the app shows guidance (raise max staff, change patterns or demands).

---

## Running the app

From the repository root:

```bash
streamlit run app.py
```

Open the URL printed by Streamlit (usually http://localhost:8501).

---

## UI (what you can configure)

- Plazas necesarias por Sábado (cada semana) — DEMANDA_SABADO (default in source: 116)
- Plazas necesarias por Domingo (cada semana) — DEMANDA_DOMINGO (default in source: 81)
- Número de tipos de empleados (1, 2, 3)
- For each type:
  - Nº Máximo de empleados del Tipo (default: 150)
  - Nº total de servicios/mes (allowed choices 1..6, default shown 4) — this filters the set of available 3-week patterns to only those that sum to that number of services. The multiselect shows allowed distributions for that type; you may choose a subset.

Then press "Calcular Plantilla Óptima".

---

## Output files

- The app can generate/download an Excel file named `plantilla_turnos_semanal.xlsx` with:
  - Detailed assignment per employee ID, type, assigned pattern, and each week's assignment (Sábado/Domingo/Finde Completo/Descanso).
  - Weekly totals and grand totals for the month.

---

## Implementation notes & important details

- The assignment logic that builds the schedule for each employee must be IDENTICAL to the logic used when precalculating the pattern contributions to ensure model coverage equals the exported schedule. The code enforces this deterministic logic in both places.
- The contributions are computed per-week and are strict 0/1 indicators (an assignment of "Finde Completo" contributes to both Saturday and Sunday).
- The app assumes a 4-week month with employees having one rest week per month.
- Rounding/integers: PuLP variables are Integer; where floats are encountered from solver internals, results are rounded using int(round(...)) before producing schedules or counts.

---

## Typical troubleshooting / suggestions

- If the model is infeasible:
  - Increase the maximum number of employees for one or more types.
  - Allow different patterns (change services/month or selected distributions).
  - Verify demands (maybe DEMANDA_SABADO / DEMANDA_DOMINGO are too high).
- If totals in the preview do not match the demand, ensure no manual changes were made to the assignment logic — both precalculation and schedule generation must match.
- For large values or many options, solving may take longer; consider reducing the number of pattern choices per type.

---

## Files of interest

- app.py — main Streamlit application (contains pattern generation, contribution precalc, PuLP model, and schedule export).
- (You may add a requirements.txt with pinned versions if distributing.)

---

## Local development tips

- To test quickly, reduce demands to small numbers and use only one employee type with a small max headcount.
- Add logging or print statements if you want to trace the assignment for a specific pattern/rest_week.
- If you want to change the month length from 4 weeks, you must:
  - Update WEEKS list (in source it's defined as [1,2,3,4]).
  - Re-check pattern generation & contribution precalc logic to ensure patterns still represent feasible distributions.

---