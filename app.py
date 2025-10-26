import streamlit as st
import pulp
import pandas as pd
import math
import io
from collections import defaultdict

# --- FUNCIÓN 1: SIN CAMBIOS ---
def generate_3week_patterns():
    """
    Genera TODOS los patrones de trabajo posibles que se pueden
    realizar en 3 semanas de trabajo (1 finde libre).
    
    Devuelve: { "display_str": {"pulp": (Sáb/sem, Dom/sem), "components": (s,d,c)} }
    """
    pattern_map = {}
    # s = sábados solos, d = domingos solos, c = fines de semana completos
    for c in range(4): # 0, 1, 2, 3
        for s in range(4): # 0, 1, 2, 3
            for d in range(4): # 0, 1, 2, 3
                
                total_weekends_worked = s + d + c
                
                if total_weekends_worked > 0 and total_weekends_worked <= 3:
                    
                    # Aporte SEMANAL (promedio sobre las 3 semanas de trabajo)
                    # NOTA: Este valor "pulp" ya no se usa en el modelo, pero se mantiene
                    # para no alterar la estructura de datos.
                    avg_s = (s + c) / 3.0
                    avg_d = (d + c) / 3.0
                    
                    pulp_tuple = (avg_s, avg_d)
                    components = (s, d, c)
                    
                    parts = []
                    if s > 0: parts.append(f"{s} Sáb. solo(s)")
                    if d > 0: parts.append(f"{d} Dom. solo(s)")
                    if c > 0: parts.append(f"{c} Finde(s) Completo(s)")
                    
                    display_str = ", ".join(parts)

                    if display_str:
                        pattern_map[display_str] = {
                            "pulp": pulp_tuple, # Clave "pulp" ya no se usa en el modelo
                            "components": components,
                            "work_weeks": total_weekends_worked
                        }
                        
    return pattern_map

# --- FUNCIÓN 2: SIN CAMBIOS ---
def generate_schedule_df(results_vars, employee_types_data, master_map):
    """
    Genera la plantilla de turnos detallada.
    LA LÓGICA DE ASIGNACIÓN AQUÍ DEBE SER IDÉNTICA A LA
    DE 'precalculate_contributions' PARA QUE EL MODELO FUNCIONE.
    """
    schedule_rows = []
    weeks = [1, 2, 3, 4]
    week_cols_final = [f"Semana {w}" for w in weeks]

    id_counters = defaultdict(int)
    temp_rows = []

    for type_name in employee_types_data.keys():
        for pattern_str in employee_types_data[type_name]["selected_patterns"]:
            for rest_week in weeks:
                # Usamos round() y luego int() por seguridad con los floats de PuLP
                num_empleados = int(round(results_vars[type_name][pattern_str][rest_week].value()))
                
                if num_empleados > 0:
                    for i in range(num_empleados):
                        id_counters[type_name] += 1
                        employee_index = id_counters[type_name]
                        
                        temp_rows.append({
                            "type_name": type_name,
                            "pattern_str": pattern_str,
                            "rest_week": rest_week,
                            "id": f"{type_name}-{employee_index}",
                            "sort_key": employee_index
                        })

    temp_rows.sort(key=lambda x: x["sort_key"])

    for emp in temp_rows:
        final_row = {
            "ID Empleado": emp["id"],
            "Tipo": f"Tipo {emp['type_name']}",
            "Patrón Asignado": emp["pattern_str"]
        }
        
        s, d, c = master_map[emp["pattern_str"]]["components"]
        
        work_weeks = [w for w in weeks if w != emp["rest_week"]]
        
        work_schedule = {}
        
        # --- Lógica de asignación determinística (DEBE SER IDÉNTICA A LA PRECALCULADA) ---
        weeks_for_c = work_weeks[:c]
        for wk in weeks_for_c:
            work_schedule[wk] = "Finde Completo"
        
        available_weeks = [w for w in work_weeks if w not in work_schedule][:s]
        for wk in available_weeks:
            work_schedule[wk] = "Sábado"

        available_weeks = [w for w in work_weeks if w not in work_schedule][:d]
        for wk in available_weeks:
            work_schedule[wk] = "Domingo"
        
        available_weeks = [w for w in work_weeks if w not in work_schedule]
        for wk in available_weeks:
            work_schedule[wk] = "Descanso" 
        # --- Fin de la lógica de asignación ---

        for w in weeks:
            col_name = f"Semana {w}"
            if w == emp["rest_week"]:
                final_row[col_name] = "Descanso (LIBRE)"
            else:
                final_row[col_name] = work_schedule[w]
        
        schedule_rows.append(final_row)

    if not schedule_rows:
        return pd.DataFrame()

    df = pd.DataFrame(schedule_rows)
    
    cols_order = ["ID Empleado", "Tipo", "Patrón Asignado"] + week_cols_final
    if not all(col in df.columns for col in cols_order):
        # Fallback si df está vacío o columnas no coinciden
        df = pd.DataFrame(columns=cols_order)
    else:
        df = df.reindex(columns=cols_order) 

    total_s_trab = {"ID Empleado": "TOTAL SÁB. TRABAJADOS (Semana)"}
    total_d_trab = {"ID Empleado": "TOTAL DOM. TRABAJADOS (Semana)"}
    total_finde_desc = {"ID Empleado": "TOTAL FINDES DESCANSO (Semana)"}
    
    for col_name in week_cols_final:
        if col_name in df:
            total_s_trab[col_name] = (df[col_name] == 'Sábado').sum() + (df[col_name] == 'Finde Completo').sum()
            total_d_trab[col_name] = (df[col_name] == 'Domingo').sum() + (df[col_name] == 'Finde Completo').sum()
            total_finde_desc[col_name] = (df[col_name] == 'Descanso').sum() + (df[col_name] == 'Descanso (LIBRE)').sum()
        else:
            total_s_trab[col_name] = 0; total_d_trab[col_name] = 0; total_finde_desc[col_name] = 0

    totals_df = pd.DataFrame([total_s_trab, total_d_trab, total_finde_desc])
    # Usamos concat en lugar de append (deprecated)
    df = pd.concat([df, totals_df], ignore_index=True)

    total_s_mes = sum(total_s_trab[col] for col in week_cols_final)
    total_d_mes = sum(total_d_trab[col] for col in week_cols_final)
    
    gt_s = {"ID Empleado": "GRAN TOTAL SÁBADOS (Mes)", f"Semana 1": total_s_mes}
    gt_d = {"ID Empleado": "GRAN TOTAL DOMINGOS (Mes)", f"Semana 1": total_d_mes}
    
    for col in week_cols_final[1:] + ["Tipo", "Patrón Asignado"]:
        if col not in gt_s: gt_s[col] = ""
        if col not in gt_d: gt_d[col] = ""

    gt_df = pd.DataFrame([gt_s, gt_d])
    df = pd.concat([df, gt_df], ignore_index=True)
    
    return df

# --- FUNCIÓN 3: NUEVA FUNCIÓN DE PRECÁLCULO (LA CORRECCIÓN CLAVE) ---
def precalculate_contributions(master_pattern_map, weeks_list):
    """
    Precalcula la contribución EXACTA (Sáb, Dom) para cada patrón,
    cada semana de descanso posible, y cada semana del mes.
    
    Usa la MISMA lógica de asignación que 'generate_schedule_df'.
    
    Devuelve: { pattern_str: { rest_week: { week: (s_contrib, d_contrib) } } }
    """
    contribution_map = {}
    
    for pattern_str, data in master_pattern_map.items():
        s, d, c = data["components"]
        contribution_map[pattern_str] = {}
        
        for rest_week in weeks_list:
            contribution_map[pattern_str][rest_week] = {}
            work_weeks = [w for w in weeks_list if w != rest_week]
            
            work_schedule = {} # {semana: "Sábado" | "Domingo" | "Finde Completo" | "Descanso"}
            
            # --- Lógica de asignación determinística (IDÉNTICA A LA DE generate_schedule_df) ---
            weeks_for_c = work_weeks[:c]
            for wk in weeks_for_c:
                work_schedule[wk] = "Finde Completo"
            
            available_weeks = [w for w in work_weeks if w not in work_schedule][:s]
            for wk in available_weeks:
                work_schedule[wk] = "Sábado"

            available_weeks = [w for w in work_weeks if w not in work_schedule][:d]
            for wk in available_weeks:
                work_schedule[wk] = "Domingo"
            
            available_weeks = [w for w in work_weeks if w not in work_schedule]
            for wk in available_weeks:
                work_schedule[wk] = "Descanso"
            # --- Fin de la lógica de asignación ---
            
            # Rellenar el mapa de contribución para las 4 semanas
            for w in weeks_list:
                if w == rest_week:
                    # Está descansando esta semana
                    contribution_map[pattern_str][rest_week][w] = (0, 0)
                else:
                    # Está trabajando, ver qué le toca
                    assignment = work_schedule[w]
                    s_contrib = 1 if (assignment == "Sábado" or assignment == "Finde Completo") else 0
                    d_contrib = 1 if (assignment == "Domingo" or assignment == "Finde Completo") else 0
                    contribution_map[pattern_str][rest_week][w] = (s_contrib, d_contrib)
                    
    return contribution_map

# --- FUNCIÓN 4: SIN CAMBIOS (antes 3) ---
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla_Turnos')
        worksheet = writer.sheets['Plantilla_Turnos']
        # Ajustar ancho de columnas
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            # Proteger contra columnas vacías que dan error en max()
            if pd.isna(column_len):
                column_len = len(col) + 2
            worksheet.column_dimensions[chr(65 + i)].width = column_len
    return output.getvalue()

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Optimizador de Plantilla", layout="wide")

st.markdown("""
    <style>
        [data-baseweb="tag"] {
            background-color: #0178D4 !important; color: white !important; border-radius: 8px !important;
        }
        [data-baseweb="tag"] span[role="button"] { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Optimizador de Plantilla de Fin de Semana (Cobertura Semanal)")
st.write("Esta herramienta calcula la plantilla mínima para cubrir la demanda **cada semana**, asumiendo que cada empleado rota un fin de semana libre al mes.")

# --- DATOS GLOBALES PARA EL MODELO (SECCIÓN MODIFICADA) ---
master_pattern_map = generate_3week_patterns()
WEEKS = [1, 2, 3, 4]
# Precalcular el mapa de contribución EXACTA
CONTRIBUTION_MAP = precalculate_contributions(master_pattern_map, WEEKS)

# --- ENTRADAS DEL USUARIO (SECCIÓN MODIFICADA) ---
config_expander = st.expander("Configuración de Demanda y Empleados", expanded=True)
with config_expander:
    st.header("Parámetros de Entrada")

    DEMANDA_SABADO = st.number_input("Plazas necesarias por Sábado (cada semana)", min_value=0, value=116, step=1)
    DEMANDA_DOMINGO = st.number_input("Plazas necesarias por Domingo (cada semana)", min_value=0, value=81, step=1)
    
    st.markdown("---")

    NUMERO_TIPO_EMPLEADOS = st.selectbox("Número de tipos de empleados", (1, 2, 3), index=1)

    employee_types_data = {}
    employee_type_names = [ chr(i+65) for i in range(NUMERO_TIPO_EMPLEADOS) ]

    for type_name in employee_type_names:
        st.markdown(f"### Configuración del Tipo {type_name}")
        max_employees = st.number_input(f"Nº Máximo de empleados del Tipo {type_name}", min_value=0, value=150, step=1, key=f"max_{type_name}")
        
        # --- Lógica de filtrado (SIN CAMBIOS) ---
        
        services_per_employee = st.number_input(
            f"Nº total de servicios/mes para el Tipo {type_name}",
            min_value=1, value=4, max_value=6, step=1,
            key=f"serv_{type_name}"
        )
        
        filtered_options = []
        for pattern_str, data in master_pattern_map.items():
            s, d, c = data["components"]
            total_services = s + d + (c * 2)
            if total_services == services_per_employee:
                filtered_options.append(pattern_str)
        
        if filtered_options:
            selected_display_options = st.multiselect(
                f"Distribuciones de {services_per_employee} servicios permitidas para el Tipo {type_name}",
                options=filtered_options,
                key=f"multi_{type_name}",
                default=filtered_options 
            )
        else:
            st.warning(f"No se encontraron patrones de 3 semanas que sumen {services_per_employee} servicios. Prueba con otro número.")
            selected_display_options = []
        
        # --- Fin de la lógica de filtrado ---

        employee_types_data[type_name] = {
            "max_employees": max_employees,
            "selected_patterns": selected_display_options,
        }

# --- BOTÓN DE CÁLCULO ---
if st.button("Calcular Plantilla Óptima", type="primary"):

    # Totales mensuales de demanda (para el resumen)
    TOTAL_DEMANDA_SABADO = DEMANDA_SABADO * 4
    TOTAL_DEMANDA_DOMINGO = DEMANDA_DOMINGO * 4

    model = pulp.LpProblem("Minimizar_Plantilla_Fin_de_Semana_Semanal", pulp.LpMinimize)

    # Variables (sin cambios)
    N_vars = pulp.LpVariable.dicts("TotalEmpleados", employee_type_names, lowBound=0, cat='Integer')

    x_vars = {}
    for type_name in employee_type_names:
        x_vars[type_name] = {}
        for pattern_str in employee_types_data[type_name]["selected_patterns"]:
            x_vars[type_name][pattern_str] = pulp.LpVariable.dicts(
                name=f"Empleados_{type_name}_{pattern_str[:10].replace(' ', '_')}",
                indices=WEEKS, 
                lowBound=0,
                cat='Integer'
            )

    # Objetivo (sin cambios)
    model += pulp.lpSum(N_vars), "Minimizar_Plantilla_Total"

    # -----------------------------------------------------------------
    # --- RESTRICCIONES (SECCIÓN CORREGIDA) ---
    # -----------------------------------------------------------------
    
    # Restricciones de cobertura (UNA POR CADA SEMANA Y DÍA)
    for w in WEEKS:
        # Cobertura de Sábados para la semana 'w'
        model += pulp.lpSum(
            # Sumar la contribución de este grupo
            x_vars[type_name][pattern_str][rest_week] * # Multiplicada por su contribución EXACTA en la semana 'w'
            CONTRIBUTION_MAP[pattern_str][rest_week][w][0] # [0] es Sábado
            
            for type_name in employee_type_names
            for pattern_str in employee_types_data[type_name]["selected_patterns"]
            for rest_week in WEEKS # Sumar sobre TODAS las semanas de descanso
        ) >= DEMANDA_SABADO, f"Cobertura_Sabado_Semana_{w}"

        # Cobertura de Domingos para la semana 'w'
        model += pulp.lpSum(
            x_vars[type_name][pattern_str][rest_week] * CONTRIBUTION_MAP[pattern_str][rest_week][w][1] # [1] es Domingo
            
            for type_name in employee_type_names
            for pattern_str in employee_types_data[type_name]["selected_patterns"]
            for rest_week in WEEKS
        ) >= DEMANDA_DOMINGO, f"Cobertura_Domingo_Semana_{w}"

    # Restricciones de vínculo y máximos (sin cambios)
    for type_name in employee_type_names:
        model += pulp.lpSum(
            x_vars[type_name][pattern_str][rest_week]
            for pattern_str in employee_types_data[type_name]["selected_patterns"]
            for rest_week in WEEKS
        ) == N_vars[type_name], f"Vinculo_Plantilla_{type_name}"
        
        model += N_vars[type_name] <= employee_types_data[type_name]["max_employees"], f"Maximo_Empleados_{type_name}"
    
    # -----------------------------------------------------------------
    # --- FIN DE LA CORRECCIÓN DE RESTRICCIONES ---
    # -----------------------------------------------------------------

    model.solve(pulp.PULP_CBC_CMD(msg=0))

    # --- MOSTRAR RESULTADOS (SECCIÓN CORREGIDA) ---
    st.header("Resultados de la Optimización")
    status = pulp.LpStatus[model.status]
    st.write(f"**Estado de la Solución:** {status}")

    if status == 'Optimal':
        total_empleados = pulp.value(model.objective)
        st.success(f"**Número Mínimo de Empleados Necesarios:** {math.ceil(total_empleados)}")

        st.subheader("Desglose Total por Tipo de Empleado")
        
        type_totals = {}
        # Controlar que el número de columnas sea al menos 1
        num_cols = max(1, NUMERO_TIPO_EMPLEADOS)
        cols = st.columns(num_cols)
        
        for i, type_name in enumerate(employee_type_names):
            total_tipo = N_vars[type_name].value()
            # Asegurarse de que total_tipo no sea None (si no hay empleados de ese tipo)
            total_tipo = total_tipo if total_tipo is not None else 0.0
            type_totals[type_name] = total_tipo
            with cols[i]:
                st.metric(
                    label=f"Total Empleados Tipo {type_name}",
                    value=int(round(total_tipo))
                )

        results_data = []
        total_sabados_cubiertos_mes = 0
        total_domingos_cubiertos_mes = 0

        # --- Lógica para obtener cobertura (SIN CAMBIOS, ya estaba corregida) ---
        # El valor de la cobertura (LHS) es el 'slack' (constraint.value()) + el lado derecho (RHS)
        # .value() devuelve el "slack" (LHS - RHS). Queremos el LHS.
        # LHS = constraint.value() + RHS
        for w in WEEKS:
            # Comprobar si la restricción existe antes de acceder
            if f"Cobertura_Sabado_Semana_{w}" in model.constraints:
                slack_s = model.constraints[f"Cobertura_Sabado_Semana_{w}"].value()
                total_sabados_cubiertos_mes += (slack_s + DEMANDA_SABADO)
            
            if f"Cobertura_Domingo_Semana_{w}" in model.constraints:
                slack_d = model.constraints[f"Cobertura_Domingo_Semana_{w}"].value()
                total_domingos_cubiertos_mes += (slack_d + DEMANDA_DOMINGO)
        # --- Fin de la lógica de cobertura ---

        for type_name in employee_type_names:
            total_tipo_empleado = type_totals.get(type_name, 0)
            
            for pattern_str in employee_types_data[type_name]["selected_patterns"]:
                # Sumamos los empleados de este patrón en sus 4 posibles semanas de descanso
                num_empleados_total_pattern = sum(x_vars[type_name][pattern_str][rest_week].value() for rest_week in WEEKS)
                
                if num_empleados_total_pattern > 0.001: 
                    
                    s, d, c = master_pattern_map[pattern_str]["components"]
                    servicios_mes_por_persona = s + d + (c * 2)
                    
                    # Contribución total al mes de este grupo de empleados
                    sabados_aportados_total = num_empleados_total_pattern * (s + c)
                    domingos_aportados_total = num_empleados_total_pattern * (d + c)
                    
                    pct_del_tipo = (num_empleados_total_pattern / total_tipo_empleado * 100) if total_tipo_empleado > 0 else 0
                    pct_del_total = (num_empleados_total_pattern / total_empleados * 100) if total_empleados > 0 else 0

                    results_data.append({
                        "Tipo": f"Tipo {type_name}",
                        "Partición": pattern_str,
                        "Servicios/Mes (total)": servicios_mes_por_persona,
                        "Nº Empleados": int(round(num_empleados_total_pattern)),
                        "% s/ Total Tipo": pct_del_tipo,
                        "% s/ Total Plantilla": pct_del_total,
                        "Sábados Cubiertos (Mes)": int(round(sabados_aportados_total)),
                        "Domingos Cubiertos (Mes)": int(round(domingos_aportados_total)),
                    })
        
        if results_data: 
            
            st.subheader("Resumen de Cobertura de Demanda (Total Mes)")
            col1, col2 = st.columns(2)
            with col1:
                total_s_int = int(round(total_sabados_cubiertos_mes))
                delta_s_int = total_s_int - TOTAL_DEMANDA_SABADO
                st.metric(
                    label="Turnos de Sábado Cubiertos (Total Mes)",
                    value=f"{total_s_int}",
                    delta=f"{delta_s_int} (Excedente)"
                )
                st.caption(f"Requeridos: {TOTAL_DEMANDA_SABADO} ({DEMANDA_SABADO}/sáb)")
            with col2:
                total_d_int = int(round(total_domingos_cubiertos_mes))
                delta_d_int = total_d_int - TOTAL_DEMANDA_DOMINGO
                st.metric(
                    label="Turnos de Domingo Cubiertos (Total Mes)",
                    value=f"{total_d_int}",
                    delta=f"{delta_d_int} (Excedente)"
                )
                st.caption(f"Requeridos: {TOTAL_DEMANDA_DOMINGO} ({DEMANDA_DOMINGO}/dom)")

            
            st.subheader("Asignación Detallada por Patrón (Resumen)")
            
            column_order = [
                "Tipo", "Partición", "Servicios/Mes (total)", "Nº Empleados",
                "% s/ Total Tipo", "% s/ Total Plantilla",
                "Sábados Cubiertos (Mes)", "Domingos Cubiertos (Mes)"
            ]
            df_summary = pd.DataFrame(results_data).reindex(columns=column_order)

            st.dataframe(
                df_summary,
                use_container_width=True,
                column_config={
                    "Servicios/Mes (total)": st.column_config.NumberColumn(format="%d servicios"),
                    "% s/ Total Tipo": st.column_config.NumberColumn(format="%.2f%%"),
                    "% s/ Total Plantilla": st.column_config.NumberColumn(format="%.2f%%")
                }
            )
            
            st.subheader("Descargar Plantilla de Turnos Semanal")
            
            df_plantilla = generate_schedule_df(x_vars, employee_types_data, master_pattern_map)
            
            if not df_plantilla.empty:
                excel_data = convert_df_to_excel(df_plantilla)
                
                st.download_button(
                    label="📥 Descargar Plantilla de Turnos (Excel)",
                    data=excel_data,
                    file_name="plantilla_turnos_semanal.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                with st.expander("Ver previsualización de la plantilla generada (Los totales semanales DEBEN cuadrar con la demanda)"):
                    st.dataframe(df_plantilla)
            else:
                st.info("No se generó plantilla (0 empleados asignados).")
            
        else:
            st.info("La solución óptima no requiere asignar ningún empleado.")

    elif status == 'Infeasible':
        st.error(
            "**El problema no tiene solución (Infactible).** Esto significa que es imposible "
            "cumplir con la demanda semanal con las restricciones actuales de personal. "
            "**Sugerencias:**\n"
            "- Aumentar el 'Nº Máximo de empleados' para uno o más tipos.\n"
            "- Permitir patrones de trabajo más flexibles (ej. '3 Findes Completos' es el más eficiente).\n"
            " - Revisar si las cifras de demanda son correctas."
        )
    else:
        st.warning(f"**El modelo no encontró una solución óptima.** Estado: {status}. Revise los parámetros de entrada.")
