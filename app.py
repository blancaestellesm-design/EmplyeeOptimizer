import streamlit as st
import pulp
import pandas as pd
import math
import io
from collections import defaultdict

# --- FUNCIÓN 1: RESTAURADA Y MEJORADA ---
def generate_3week_patterns():
    """
    Genera TODOS los patrones de trabajo posibles que se pueden
    realizar en 3 semanas de trabajo (1 finde libre).
    
    Devuelve: { "display_str": {"pulp": (Sáb/sem, Dom/sem), "components": (s,d,c)} }
    """
    pattern_map = {}
    # s = sábados solos, d = domingos solos, c = fines de semana completos
    # Un empleado tiene 3 semanas para trabajar
    for c in range(4): # 0, 1, 2, 3
        for s in range(4): # 0, 1, 2, 3
            for d in range(4): # 0, 1, 2, 3
                
                total_weekends_worked = s + d + c
                
                # Regla: El patrón debe ocupar como máximo 3 fines de semana
                if total_weekends_worked > 0 and total_weekends_worked <= 3:
                    
                    # Aporte SEMANAL (promedio sobre las 3 semanas de trabajo)
                    # Esta es la "traducción" para el modelo semanal
                    avg_s = (s + c) / 3.0
                    avg_d = (d + c) / 3.0
                    
                    # El optimizador PuLP usará este aporte promedio
                    pulp_tuple = (avg_s, avg_d)
                    components = (s, d, c)
                    
                    parts = []
                    if s > 0: parts.append(f"{s} Sáb. solo(s)")
                    if d > 0: parts.append(f"{d} Dom. solo(s)")
                    if c > 0: parts.append(f"{c} Finde(s) Completo(s)")
                    
                    display_str = ", ".join(parts)

                    if display_str:
                        pattern_map[display_str] = {
                            "pulp": pulp_tuple,
                            "components": components,
                            "work_weeks": total_weekends_worked
                        }
                        
    return pattern_map

# --- FUNCIÓN 2: MODIFICADA ---
def generate_schedule_df(results_vars, employee_types_data, master_map):
    """
    Genera la plantilla de turnos detallada.
    ¡Esta función ahora es la más compleja!
    """
    schedule_rows = []
    weeks = [1, 2, 3, 4]
    week_cols_final = [f"Semana {w}" for w in weeks]

    id_counters = defaultdict(int)
    temp_rows = []

    # 1. Recopilar todas las asignaciones de empleados del modelo
    for type_name in employee_types_data.keys():
        for pattern_str in employee_types_data[type_name]["selected_patterns"]:
            for rest_week in weeks:
                num_empleados = int(results_vars[type_name][pattern_str][rest_week].value())
                
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

    # 2. Construir la fila final del DataFrame
    for emp in temp_rows:
        final_row = {
            "ID Empleado": emp["id"],
            "Tipo": f"Tipo {emp['type_name']}",
            "Patrón Asignado": emp["pattern_str"]
        }
        
        # Obtener los componentes (s,d,c) del patrón
        s, d, c = master_map[emp["pattern_str"]]["components"]
        
        # Semanas disponibles para trabajar
        work_weeks = [w for w in weeks if w != emp["rest_week"]]
        
        # Crear un horario base para las semanas de trabajo
        work_schedule = {}
        
        # Asignar Fines de Semana Completos
        weeks_for_c = work_weeks[:c]
        for wk in weeks_for_c:
            work_schedule[wk] = "Finde Completo"
        
        # Asignar Sábados solos
        available_weeks = [w for w in work_weeks if w not in work_schedule][:s]
        for wk in available_weeks:
            work_schedule[wk] = "Sábado"

        # Asignar Domingos solos
        available_weeks = [w for w in work_weeks if w not in work_schedule][:d]
        for wk in available_weeks:
            work_schedule[wk] = "Domingo"
        
        # Rellenar semanas de trabajo restantes (si s+d+c < 3)
        available_weeks = [w for w in work_weeks if w not in work_schedule]
        for wk in available_weeks:
            work_schedule[wk] = "Descanso" # Es una semana de trabajo, pero este patrón no la usa

        # Asignar al calendario final
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
    df = df.reindex(columns=cols_order) 

    # 3. Añadir Totales por Semana
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
    df = pd.concat([df, totals_df], ignore_index=True)

    # 4. Añadir GRAN TOTAL MENSUAL
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

# --- FUNCIÓN 3: SIN CAMBIOS ---
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla_Turnos')
        worksheet = writer.sheets['Plantilla_Turnos']
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
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

# --- DATOS GLOBALES PARA EL MODELO ---
# Generar el mapa maestro de patrones UNA SOLA VEZ
master_pattern_map = generate_3week_patterns()
pattern_options = list(master_pattern_map.keys())
WEEKS = [1, 2, 3, 4]

# --- ENTRADAS DEL USUARIO ---
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
        
        # --- INTERFAZ RESTAURADA ---
        selected_display_options = st.multiselect(
            f"Patrones de 3 semanas permitidos para el Tipo {type_name}",
            options=pattern_options,
            key=f"multi_{type_name}",
            default=[p for p in pattern_options if "3" in p] # Default a patrones de 3 servicios
        )
        
        employee_types_data[type_name] = {
            "max_employees": max_employees,
            "selected_patterns": selected_display_options,
        }

# --- BOTÓN DE CÁLCULO ---
if st.button("Calcular Plantilla Óptima", type="primary"):

    # Demanda total para el resumen
    TOTAL_DEMANDA_SABADO = DEMANDA_SABADO * 4
    TOTAL_DEMANDA_DOMINGO = DEMANDA_DOMINGO * 4

    model = pulp.LpProblem("Minimizar_Plantilla_Fin_de_Semana_Semanal", pulp.LpMinimize)

    # --- LÓGICA DE VARIABLES MODIFICADA ---
    
    N_vars = pulp.LpVariable.dicts("TotalEmpleados", employee_type_names, lowBound=0, cat='Integer')

    # x_vars: x[Tipo][Patrón_String][Semana_que_DESCANSA]
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

    model += pulp.lpSum(N_vars), "Minimizar_Plantilla_Total"

    # --- LÓGICA DE RESTRICCIONES MODIFICADA ---
    # Ahora es más complejo: el aporte de cada patrón debe ser calculado
    
    for w in WEEKS:
        # Semanas en las que la gente SÍ trabaja
        work_weeks = [wk for wk in WEEKS if wk != w]
        
        # Restricción Sábado, Semana 'w'
        model += pulp.lpSum(
            # Sumar a todos los que NO descansan esta semana
            x_vars[type_name][pattern_str][rest_week] * # Multiplicar por su aporte SEMANAL de Sábados
            master_pattern_map[pattern_str]["pulp"][0] 
            
            for type_name in employee_type_names
            for pattern_str in employee_types_data[type_name]["selected_patterns"]
            for rest_week in work_weeks 
        ) >= DEMANDA_SABADO, f"Cobertura_Sabado_Semana_{w}"

        # Restricción Domingo, Semana 'w'
        model += pulp.lpSum(
            x_vars[type_name][pattern_str][rest_week] *
            master_pattern_map[pattern_str]["pulp"][1] # Aporte SEMANAL de Domingos

            for type_name in employee_type_names
            for pattern_str in employee_types_data[type_name]["selected_patterns"]
            for rest_week in work_weeks
        ) >= DEMANDA_DOMINGO, f"Cobertura_Domingo_Semana_{w}"

    # Restricciones de vínculo y máximos
    for type_name in employee_type_names:
        model += pulp.lpSum(
            x_vars[type_name][pattern_str][rest_week]
            for pattern_str in employee_types_data[type_name]["selected_patterns"]
            for rest_week in WEEKS
        ) == N_vars[type_name], f"Vinculo_Plantilla_{type_name}"
        
        model += N_vars[type_name] <= employee_types_data[type_name]["max_employees"], f"Maximo_Empleados_{type_name}"

    # Resolver el modelo
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    # --- MOSTRAR RESULTADOS ---
    st.header("Resultados de la Optimización")
    status = pulp.LpStatus[model.status]
    st.write(f"**Estado de la Solución:** {status}")

    if status == 'Optimal':
        total_empleados = pulp.value(model.objective)
        st.success(f"**Número Mínimo de Empleados Necesarios:** {math.ceil(total_empleados)}")

        st.subheader("Desglose Total por Tipo de Empleado")
        
        type_totals = {}
        cols = st.columns(NUMERO_TIPO_EMPLEADOS)
        for i, type_name in enumerate(employee_type_names):
            total_tipo = N_vars[type_name].value()
            type_totals[type_name] = total_tipo
            with cols[i]:
                st.metric(
                    label=f"Total Empleados Tipo {type_name}",
                    value=int(total_tipo)
                )

        # --- LÓGICA DE RESULTADOS MODIFICADA ---
        results_data = []
        total_sabados_cubiertos_mes = 0
        total_domingos_cubiertos_mes = 0

        # Calcular cobertura total mensual (para los st.metric)
        for w in WEEKS:
            total_sabados_cubiertos_mes += pulp.value(model.constraints[f"Cobertura_Sabado_Semana_{w}"].expression())
            total_domingos_cubiertos_mes += pulp.value(model.constraints[f"Cobertura_Domingo_Semana_{w}"].expression())

        # Recopilar datos para la tabla resumen
        for type_name in employee_type_names:
            total_tipo_empleado = type_totals.get(type_name, 0)
            
            for pattern_str in employee_types_data[type_name]["selected_patterns"]:
                num_empleados_total_pattern = sum(x_vars[type_name][pattern_str][rest_week].value() for rest_week in WEEKS)
                
                if num_empleados_total_pattern > 0:
                    
                    s, d, c = master_pattern_map[pattern_str]["components"]
                    servicios_mes = (s + c) * 3 + (d + c) * 3 # Aporte mensual total de este grupo
                    sabados_aportados = num_empleados_total_pattern * (s + c)
                    domingos_aportados = num_empleados_total_pattern * (d + c)
                    
                    pct_del_tipo = (num_empleados_total_pattern / total_tipo_empleado * 100) if total_tipo_empleado > 0 else 0
                    pct_del_total = (num_empleados_total_pattern / total_empleados * 100) if total_empleados > 0 else 0

                    results_data.append({
                        "Tipo": f"Tipo {type_name}",
                        "Partición": pattern_str,
                        "Servicios/Mes (total)": s+d+(c*2), # Servicios por persona al mes
                        "Nº Empleados": int(num_empleados_total_pattern),
                        "% s/ Total Tipo": pct_del_tipo,
                        "% s/ Total Plantilla": pct_del_total,
                        "Sábados Cubiertos (Mes)": int(sabados_aportados),
                        "Domingos Cubiertos (Mes)": int(domingos_aportados),
                    })
        
        if results_data:  
            
            st.subheader("Resumen de Cobertura de Demanda (Total Mes)")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="Turnos de Sábado Cubiertos (Total Mes)",
                    value=f"{int(total_sabados_cubiertos_mes)}",
                    delta=f"{int(total_sabados_cubiertos_mes - TOTAL_DEMANDA_SABADO)} (Excedente)"
                )
                st.caption(f"Requeridos: {TOTAL_DEMANDA_SABADO} (Promedio: {DEMANDA_SABADO}/sáb)")
            with col2:
                st.metric(
                    label="Turnos de Domingo Cubiertos (Total Mes)",
                    value=f"{int(total_domingos_cubiertos_mes)}",
                    delta=f"{int(total_domingos_cubiertos_mes - TOTAL_DEMANDA_DOMINGO)} (Excedente)"
                )
                st.caption(f"Requeridos: {TOTAL_DEMANDA_DOMINGO} (Promedio: {DEMANDA_DOMINGO}/dom)")

            
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
            
            # --- BOTÓN DE DESCARGA (AHORA ES CORRECTO) ---
            st.subheader("Descargar Plantilla de Turnos Semanal")
            
            df_plantilla = generate_schedule_df(x_vars, employee_types_data, master_pattern_map)
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
            st.info("La solución óptima no requiere asignar ningún empleado.")

    elif status == 'Infeasible':
        st.error(
            "**El problema no tiene solución (Infactible).** Esto significa que es imposible "
            "cumplir con la demanda semanal con las restricciones actuales de personal. "
            "**Sugerencias:**\n"
            "- Aumentar el 'Nº Máximo de empleados' para uno o más tipos.\n"
            "- Permitir patrones de trabajo más flexibles (ej. '3 Findes Completos' es el más eficiente).\n"
            "- Revisar si las cifras de demanda son correctas."
        )
    else:
        st.warning(f"**El modelo no encontró una solución óptima.** Estado: {status}. Revise los parámetros de entrada.")
