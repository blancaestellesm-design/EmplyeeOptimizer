import streamlit as st
import pulp
import pandas as pd
import math
import io  # <-- AÑADIDO: Para manejar el archivo Excel en memoria
# Nota: Necesitarás instalar openpyxl: pip install openpyxl

# --- FUNCIÓN 1: MODIFICADA ---
def generate_pattern_map(services_required):
    """
    Genera un mapa de patrones de trabajo.
    Ahora devuelve un diccionario con los componentes (s, d, c)
    para poder generar la plantilla de turnos.
    """
    pattern_map = {}
    # s = sábados solos, d = domingos solos, c = fines de semana completos
    for c in range(4): # 0, 1, 2, 3
        for s in range(4): # 0, 1, 2, 3
            for d in range(4): # 0, 1, 2, 3
                
                total_weekends_worked = s + d + c
                total_services = s + d + (2 * c)
                
                if total_weekends_worked <= 3 and total_services == services_required:
                    
                    pulp_tuple = (s + c, d + c) # (Total Sáb, Total Dom)
                    components = (s, d, c)     # (Sáb_solos, Dom_solos, Fines_Completos)
                    
                    parts = []
                    if s > 0: parts.append(f"{s} Sáb. solo(s)")
                    if d > 0: parts.append(f"{d} Dom. solo(s)")
                    if c > 0: parts.append(f"{c} Finde(s) Completo(s)")
                    
                    display_str = ", ".join(parts)
                    if not display_str and total_services == 0:
                        display_str = "0 servicios (Descanso)"

                    if display_str:
                        # MODIFICADO: Guardar ambas piezas de información
                        pattern_map[display_str] = {
                            "pulp": pulp_tuple,
                            "components": components
                        }
                        
    return pattern_map

# --- FUNCIÓN 2: NUEVA ---
def generate_schedule_df(results_data):
    """
    Toma los resultados de la optimización y genera una plantilla
    de turnos plausible, repartiendo los descansos.
    """
    schedule_rows = []
    weeks = [1, 2, 3, 4]
    
    # Columnas para Sábado (S) y Domingo (D) de cada semana
    week_cols = [f"W{w}-{day}" for w in weeks for day in ['S', 'D']]
    
    # Iterar sobre cada grupo de empleados asignado
    for row in results_data:
        num_empleados = int(row["Nº Empleados"])
        s, d, c = row["Componentes"]
        
        # Generar una fila para cada empleado individual
        for i in range(num_empleados):
            employee_id = f"{row['Tipo_Raw']}-{i+1}"
            
            # Crear fila base con todo "Libre" (L)
            week_row = {col: 'L' for col in week_cols}
            week_row["ID Empleado"] = employee_id
            week_row["Tipo"] = row["Tipo"]
            week_row["Patrón Asignado"] = row["Partición"]

            # Asignar la semana de descanso rotativamente
            # Empleado 0 descansa W1, Empleado 1 descansa W2, ... Empleado 4 descansa W1
            week_to_rest = weeks[i % len(weeks)]
            work_weeks = [w for w in weeks if w != week_to_rest]
            
            # 1. Colocar Fines de Semana Completos (c)
            weeks_for_c = work_weeks[:c]
            for wk in weeks_for_c:
                week_row[f"W{wk}-S"] = 'S' # Sábado
                week_row[f"W{wk}-D"] = 'D' # Domingo
            
            # 2. Colocar Sábados solos (s)
            available_s_weeks = [w for w in work_weeks if week_row[f"W{w}-S"] == 'L'][:s]
            for wk in available_s_weeks:
                week_row[f"W{wk}-S"] = 'S'

            # 3. Colocar Domingos solos (d)
            available_d_weeks = [w for w in work_weeks if week_row[f"W{w}-D"] == 'L'][:d]
            for wk in available_d_weeks:
                week_row[f"W{wk}-D"] = 'D'
                
            schedule_rows.append(week_row)

    if not schedule_rows:
        return pd.DataFrame()

    # Crear el DataFrame final
    df = pd.DataFrame(schedule_rows)
    
    # Reordenar columnas
    cols_order = ["ID Empleado", "Tipo", "Patrón Asignado"] + week_cols
    df = df[cols_order]

    # Añadir filas de Totales
    total_s = {"ID Empleado": "TOTAL SÁBADOS"}
    total_d = {"ID Empleado": "TOTAL DOMINGOS"}
    total_l = {"ID Empleado": "TOTAL DESCANSOS"}
    
    for col in week_cols:
        total_s[col] = (df[col] == 'S').sum()
        total_d[col] = (df[col] == 'D').sum()
        total_l[col] = (df[col] == 'L').sum()

    # Usar pd.concat para añadir las filas de totales
    totals_df = pd.DataFrame([total_s, total_d, total_l])
    df = pd.concat([df, totals_df], ignore_index=True)
    
    return df

# --- FUNCIÓN 3: NUEVA ---
def convert_df_to_excel(df):
    """Convierte un DataFrame a un archivo Excel en memoria (bytes)."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla_Turnos')
        
        # Opcional: Auto-ajustar ancho de columnas
        worksheet = writer.sheets['Plantilla_Turnos']
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + i)].width = column_len
            
    processed_data = output.getvalue()
    return processed_data


# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Optimizador de Plantilla", layout="wide")

# Estilos CSS para los tags del multiselect
st.markdown("""
    <style>
        [data-baseweb="tag"] {
            background-color: #0178D4 !important; color: white !important; border-radius: 8px !important;
        }
        [data-baseweb="tag"] span[role="button"] { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Optimizador de Plantilla de Fin de Semana")
st.write("Esta herramienta calcula el número mínimo de empleados necesarios para cubrir la demanda de personal, respetando la regla de 1 fin de semana libre al mes.")

# --- ENTRADAS DEL USUARIO (DENTRO DE UN EXPANDER) ---
config_expander = st.expander("Configuración de Demanda y Empleados", expanded=True)
with config_expander:
    st.header("Parámetros de Entrada")
    st.write("Ajusta los valores y haz clic en 'Calcular' para ver el resultado.")

    DEMANDA_SABADO = st.number_input("Plazas necesarias por Sábado", min_value=0, value=116, step=1)
    st.markdown(F"(Total mensual: {DEMANDA_SABADO * 4} servicios)")
    DEMANDA_DOMINGO = st.number_input("Plazas necesarias por Domingo", min_value=0, value=81, step=1)
    st.markdown(F"(Total mensual: {DEMANDA_DOMINGO * 4} servicios)")
    NUM_FINES_DE_SEMANA_MES = 4

    st.markdown("---")

    NUMERO_TIPO_EMPLEADOS = st.selectbox("Número de tipos de empleados", (1, 2, 3), index=1)

    employee_types_data = {}
    employee_type_names = [ chr(i+65) for i in range(NUMERO_TIPO_EMPLEADOS) ]

    for type_name in employee_type_names:
        st.markdown(f"### Configuración del Tipo {type_name}")
        max_employees = st.number_input(f"Nº Máximo de empleados del Tipo {type_name}", min_value=0, value=150, step=1, key=f"max_{type_name}")
        services_per_employee = st.number_input(f"Nº de servicios de fin de semana que cubre el Tipo {type_name}", min_value=1, value=4, max_value=8, step=1, key=f"serv_{type_name}")
        
        master_map = generate_pattern_map(services_per_employee)
        pattern_options = list(master_map.keys())
        
        selected_display_options = st.multiselect(
            f"Particiones de turnos permitidas para el Tipo {type_name}",
            options=pattern_options,
            key=f"multi_{type_name}"
        )
        
        employee_types_data[type_name] = {
            "max_employees": max_employees,
            "master_map": master_map,
            "selected_patterns": selected_display_options
        }

# --- BOTÓN DE CÁLCULO ---
if st.button("Calcular Plantilla Óptima", type="primary"):

    TOTAL_DEMANDA_SABADO = DEMANDA_SABADO * NUM_FINES_DE_SEMANA_MES
    TOTAL_DEMANDA_DOMINGO = DEMANDA_DOMINGO * NUM_FINES_DE_SEMANA_MES

    model = pulp.LpProblem("Minimizar_Plantilla_Fin_de_Semana", pulp.LpMinimize)

    N_vars = pulp.LpVariable.dicts("TotalEmpleados", employee_type_names, lowBound=0, cat='Integer')

    x_vars = {}
    for type_name in employee_type_names:
        x_vars[type_name] = pulp.LpVariable.dicts(
            name=f"Empleados_{type_name}",
            indices=employee_types_data[type_name]["selected_patterns"],
            lowBound=0,
            cat='Integer'
        )

    model += pulp.lpSum(N_vars), "Minimizar_Plantilla_Total"

    # --- RESTRICCIONES (MODIFICADAS) ---
    # Ahora debe acceder al diccionario 'pulp' dentro del master_map
    model += pulp.lpSum(
        x_vars[type_name][pattern_str] * employee_types_data[type_name]["master_map"][pattern_str]['pulp'][0] 
        for type_name in employee_type_names
        for pattern_str in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_SABADO, "Cobertura_Demanda_Sabados"

    model += pulp.lpSum(
        x_vars[type_name][pattern_str] * employee_types_data[type_name]["master_map"][pattern_str]['pulp'][1]
        for type_name in employee_type_names
        for pattern_str in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_DOMINGO, "Cobertura_Demanda_Domingos"

    for type_name in employee_type_names:
        model += pulp.lpSum(
            x_vars[type_name][pattern_str] for pattern_str in employee_types_data[type_name]["selected_patterns"]
        ) == N_vars[type_name], f"Vinculo_Plantilla_{type_name}"
        
        model += N_vars[type_name] <= employee_types_data[type_name]["max_employees"], f"Maximo_Empleados_{type_name}"

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

        results_data = [] # Esta lista la usaremos para AMBAS tablas
        total_sabados_cubiertos = 0
        total_domingos_cubiertos = 0

        for type_name in employee_type_names:
            total_tipo_empleado = type_totals.get(type_name, 0)
            master_map = employee_types_data[type_name]["master_map"]
            
            for pattern_str in employee_types_data[type_name]["selected_patterns"]:
                num_empleados = x_vars[type_name][pattern_str].value()
                
                if num_empleados > 0:
                    pulp_tuple = master_map[pattern_str]['pulp']
                    components = master_map[pattern_str]['components']
                    
                    sabados_aportados = num_empleados * pulp_tuple[0]
                    domingos_aportados = num_empleados * pulp_tuple[1]
                    total_sabados_cubiertos += sabados_aportados
                    total_domingos_cubiertos += domingos_aportados
                    
                    servicios_mes = pulp_tuple[0] + pulp_tuple[1]
                    pct_del_tipo = (num_empleados / total_tipo_empleado * 100) if total_tipo_empleado > 0 else 0
                    pct_del_total = (num_empleados / total_empleados * 100) if total_empleados > 0 else 0

                    # --- MODIFICACIÓN 4: Añadir datos "raw" para la plantilla ---
                    results_data.append({
                        "Tipo": f"Tipo {type_name}",
                        "Partición": pattern_str,
                        "Servicios/Mes": servicios_mes,
                        "Nº Empleados": int(num_empleados),
                        "% s/ Total Tipo": pct_del_tipo,
                        "% s/ Total Plantilla": pct_del_total,
                        "Sábados Cubiertos": int(sabados_aportados),
                        "Domingos Cubiertos": int(domingos_aportados),
                        # --- Datos "internos" para la función de plantilla ---
                        "Tipo_Raw": type_name,
                        "Componentes": components
                    })
        
        if results_data:  
            
            st.subheader("Resumen de Cobertura de Demanda (Total Mes)")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="Turnos de Sábado Cubiertos",
                    value=f"{int(total_sabados_cubiertos)}",
                    delta=f"{int(total_sabados_cubiertos - TOTAL_DEMANDA_SABADO)} (Excedente)"
                )
                st.caption(f"Requeridos: {TOTAL_DEMANDA_SABADO} (Promedio: {DEMANDA_SABADO}/sáb)")
            with col2:
                st.metric(
                    label="Turnos de Domingo Cubiertos",
                    value=f"{int(total_domingos_cubiertos)}",
                    delta=f"{int(total_domingos_cubiertos - TOTAL_DEMANDA_DOMINGO)} (Excedente)"
                )
                st.caption(f"Requeridos: {TOTAL_DEMANDA_DOMINGO} (Promedio: {DEMANDA_DOMINGO}/dom)")

            
            st.subheader("Asignación Detallada por Patrón (Resumen)")
            
            # Crear un DataFrame solo para la tabla de resumen (sin datos internos)
            column_order = [
                "Tipo", "Partición", "Servicios/Mes", "Nº Empleados",
                "% s/ Total Tipo", "% s/ Total Plantilla",
                "Sábados Cubiertos", "Domingos Cubiertos"
            ]
            df_summary = pd.DataFrame(results_data)[column_order]

            st.dataframe(
                df_summary,
                use_container_width=True,
                column_config={
                    "% s/ Total Tipo": st.column_config.NumberColumn(format="%.2f%%"),
                    "% s/ Total Plantilla": st.column_config.NumberColumn(format="%.2f%%")
                }
            )
            
            # --- AÑADIDO: Lógica del botón de descarga ---
            st.subheader("Descargar Plantilla de Turnos")
            
            # 1. Generar el DataFrame de la plantilla
            df_plantilla = generate_schedule_df(results_data)
            
            # 2. Convertir a archivo Excel en memoria
            excel_data = convert_df_to_excel(df_plantilla)
            
            # 3. Mostrar el botón
            st.download_button(
                label="📥 Descargar Plantilla de Turnos (Excel)",
                data=excel_data,
                file_name="plantilla_turnos_optimizada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            with st.expander("Ver previsualización de la plantilla generada"):
                st.dataframe(df_plantilla)
            
        else:
            st.info("La solución óptima no requiere asignar ningún empleado.")

    elif status == 'Infeasible':
        st.error(
            "**El problema no tiene solución (Infactible).** Esto significa que es imposible "
            "cumplir con la demanda especificada con las restricciones actuales de personal. "
            "**Sugerencias:**\n"
            "- Aumentar el 'Nº Máximo de empleados' para uno o más tipos.\n"
            "- Permitir patrones de trabajo más flexibles (más combinaciones de turnos).\n"
            "- Revisar si las cifras de demanda son correctas."
        )
    else:
        st.warning(f"**El modelo no encontró una solución óptima.** Estado: {status}. Revise los parámetros de entrada.")
