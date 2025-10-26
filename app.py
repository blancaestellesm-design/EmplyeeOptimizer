import streamlit as st
import pulp
import pandas as pd
import math

# --- FUNCIONES AUXILIARES ---

def generate_possible_combinations(services_required):
    """
    Genera todas las combinaciones numéricas posibles de turnos de sábado y domingo
    para un número total de servicios dado.
    Devuelve una lista de tuplas (sabados, domingos).
    """
    combinations = []
    # Límite de 4 sábados o 4 domingos por mes
    max_days_per_type = 4 
    for sabados_trabajados in range(max_days_per_type + 1):
        domingos_trabajados = services_required - sabados_trabajados
        if 0 <= domingos_trabajados <= max_days_per_type:
            combinations.append((sabados_trabajados, domingos_trabajados))
    return combinations

def create_display_map(combinations):
    """
    Crea un diccionario para mapear tuplas numéricas a cadenas de texto legibles.
    """
    return {
        combo: f"{combo[0]} Sábado(s), {combo[1]} Domingo(s)"
        for combo in combinations
    }

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Optimizador de Plantilla", layout="wide")
st.title("Optimizador de Plantilla de Fin de Semana")
st.write("Esta herramienta calcula el número mínimo de empleados necesarios para cubrir la demanda de personal de los fines de semana, basándose en diferentes tipos de empleados y sus patrones de trabajo permitidos.")

# --- ENTRADAS DEL USUARIO EN LA BARRA LATERAL ---
st.sidebar.header("Parámetros de Entrada")
st.sidebar.write("Ajusta los valores y haz clic en 'Calcular' para ver el resultado.")

DEMANDA_SABADO = st.sidebar.number_input("Plazas necesarias por Sábado", min_value=0, value=116, step=1)
st.sidebar.markdown(F"(Total mensual: {DEMANDA_SABADO * 4} servicios)")
DEMANDA_DOMINGO = st.sidebar.number_input("Plazas necesarias por Domingo", min_value=0, value=81, step=1)
st.sidebar.markdown(F"(Total mensual: {DEMANDA_DOMINGO * 4} servicios)")
NUM_FINES_DE_SEMANA_MES = 4

st.sidebar.markdown("---")

NUMERO_TIPO_EMPLEADOS = st.sidebar.selectbox("Número de tipos de empleados", (1, 2, 3), index=1)

# --- RECOPILACIÓN DE DATOS POR TIPO DE EMPLEADO ---
employee_types_data = {}
employee_type_names = [ chr(i+65) for i in range(NUMERO_TIPO_EMPLEADOS) ]  # 'A', 'B', 'C', ...

for type_name in employee_type_names:
    st.sidebar.markdown(f"### Configuración del Tipo {type_name}")
    max_employees = st.sidebar.number_input(f"Nº Máximo de empleados del Tipo {type_name}", min_value=0, value=150, step=1, key=f"max_{type_name}")
    services_per_employee = st.sidebar.number_input(f"Nº de servicios de fin de semana que cubre el Tipo {type_name}", min_value=1, value=4, max_value=8, step=1, key=f"serv_{type_name}")
    
    possible_combos = generate_possible_combinations(services_per_employee)
    display_map = create_display_map(possible_combos)
    
    selected_display_options = st.sidebar.multiselect(
        f"Combinaciones de turnos permitidas para el Tipo {type_name}",
        options=list(display_map.values()),
        key=f"multi_{type_name}"
    )
    
    reverse_display_map = {v: k for k, v in display_map.items()}
    selected_combos_tuples = [reverse_display_map[option] for option in selected_display_options]
    
    # --- MODIFICACIÓN 1: Guardar el display_map ---
    employee_types_data[type_name] = {
        "max_employees": max_employees,
        "selected_patterns": selected_combos_tuples,
        "display_map": display_map  # <-- Guardamos el mapa para usarlo en los resultados
    }
    # --- FIN MODIFICACIÓN 1 ---

# --- BOTÓN DE CÁLCULO Y LÓGICA DE OPTIMIZACIÓN ---
if st.sidebar.button("Calcular Plantilla Óptima"):

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

    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern[0]
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_SABADO, "Cobertura_Demanda_Sabados"

    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern[1]
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_DOMINGO, "Cobertura_Demanda_Domingos"

    for type_name in employee_type_names:
        model += pulp.lpSum(
            x_vars[type_name][pattern] for pattern in employee_types_data[type_name]["selected_patterns"]
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

        # --- MODIFICACIÓN 2: Pre-calcular totales ---
        st.subheader("Desglose Total por Tipo de Empleado")
        
        type_totals = {} # Diccionario para guardar los totales por tipo
        cols = st.columns(NUMERO_TIPO_EMPLEADOS)
        for i, type_name in enumerate(employee_type_names):
            total_tipo = N_vars[type_name].value()
            type_totals[type_name] = total_tipo  # Guardamos el total para usarlo luego
            with cols[i]:
                st.metric(
                    label=f"Total Empleados Tipo {type_name}",
                    value=int(total_tipo)
                )
        # --- FIN MODIFICACIÓN 2 ---

        results_data = []
        total_sabados_cubiertos = 0
        total_domingos_cubiertos = 0

        for type_name in employee_type_names:
            # Recuperar el total de este tipo, que ya calculamos
            total_tipo_empleado = type_totals.get(type_name, 0)
            
            for pattern in employee_types_data[type_name]["selected_patterns"]:
                num_empleados = x_vars[type_name][pattern].value()
                
                if num_empleados > 0:
                    sabados_aportados = num_empleados * pattern[0]
                    domingos_aportados = num_empleados * pattern[1]
                    total_sabados_cubiertos += sabados_aportados
                    total_domingos_cubiertos += domingos_aportados
                    
                    # --- MODIFICACIÓN 3: Crear nuevas columnas ---
                    
                    # Req 1: Días por finde (servicios/mes)
                    servicios_mes = pattern[0] + pattern[1]
                    
                    # Req 2: Partición "fancy"
                    # Recuperamos el display_map de este tipo
                    display_map = employee_types_data[type_name]["display_map"] 
                    particion_str = display_map.get(pattern, str(pattern)) # Usar string legible
                    
                    # Req 3: Porcentajes (con control de división por cero)
                    pct_del_tipo = (num_empleados / total_tipo_empleado * 100) if total_tipo_empleado > 0 else 0
                    pct_del_total = (num_empleados / total_empleados * 100) if total_empleados > 0 else 0

                    results_data.append({
                        "Tipo": f"Tipo {type_name}",
                        "Partición": particion_str,         # Req 2
                        "Servicios/Mes": servicios_mes,     # Req 1
                        "Nº Empleados": int(num_empleados),
                        "% s/ Total Tipo": pct_del_tipo,    # Req 3
                        "% s/ Total Plantilla": pct_del_total, # Req 3
                        "Sábados Cubiertos": int(sabados_aportados),
                        "Domingos Cubiertos": int(domingos_aportados)
                    })
                    # --- FIN MODIFICACIÓN 3 ---
        
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

            
            st.subheader("Asignación Detallada por Patrón")
            df_results = pd.DataFrame(results_data)

            # --- MODIFICACIÓN 4: Reordenar y formatear la tabla ---
            
            # Definir el orden deseado de las columnas
            column_order = [
                "Tipo", "Partición", "Servicios/Mes", "Nº Empleados",
                "% s/ Total Tipo", "% s/ Total Plantilla",
                "Sábados Cubiertos", "Domingos Cubiertos"
            ]
            
            # Reordenar el DataFrame
            df_results = df_results[column_order]

            st.dataframe(
                df_results,
                use_container_width=True,
                column_config={
                    # Formatear las columnas de porcentaje
                    "% s/ Total Tipo": st.column_config.NumberColumn(format="%.2f%%"),
                    "% s/ Total Plantilla": st.column_config.NumberColumn(format="%.2f%%")
                }
            )
            # --- FIN MODIFICACIÓN 4 ---
            
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
