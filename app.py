import streamlit as st
import pulp
import pandas as pd
import math

# --- FUNCIONES AUXILIARES ---

def generate_pattern_map(services_required):
    """
    Genera un mapa de patrones de trabajo posibles basado en combinaciones de
    días sueltos y fines de semana completos, respetando la regla de
    "máximo 3 fines de semana trabajados" (1 finde libre).
    
    Devuelve un diccionario:
    { "display_string": (total_sábados, total_domingos) }
    """
    pattern_map = {}
    # s = sábados solos, d = domingos solos, c = fines de semana completos
    for c in range(4): # 0, 1, 2, 3
        for s in range(4): # 0, 1, 2, 3
            for d in range(4): # 0, 1, 2, 3
                
                total_weekends_worked = s + d + c
                total_services = s + d + (2 * c)
                
                # Regla 1: Máximo 3 fines de semana trabajados
                # Regla 2: La suma de servicios debe ser la requerida
                if total_weekends_worked <= 3 and total_services == services_required:
                    
                    # El optimizador (PuLP) sigue necesitando el total de Sáb y Dom
                    pulp_tuple = (s + c, d + c) # (Total Sáb, Total Dom)
                    
                    # Crear el string legible para la UI
                    parts = []
                    if s > 0: parts.append(f"{s} Sáb. solo(s)")
                    if d > 0: parts.append(f"{d} Dom. solo(s)")
                    if c > 0: parts.append(f"{c} Finde(s) Completo(s)")
                    
                    display_str = ", ".join(parts)
                    
                    # Caso para 0 servicios
                    if not display_str and total_services == 0:
                        display_str = "0 servicios (Descanso)"

                    # Añadir al mapa (solo si es un patrón válido)
                    if display_str:
                        pattern_map[display_str] = pulp_tuple
                        
    return pattern_map


# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Optimizador de Plantilla", layout="wide")

# --- INICIO DE LA MODIFICACIÓN: ESTILOS CSS ---
# Inyectamos CSS para cambiar el color de las etiquetas del multiselect
st.markdown("""
    <style>
        /* Selector para la etiqueta (tag) dentro del multiselect */
        [data-baseweb="tag"] {
            background-color: #0178D4 !important; /* Color de fondo azul */
            color: white !important;             /* Color del texto */
            border-radius: 8px !important;       /* Bordes más suaves */
        }
        
        /* Opcional: Cambiar el color del botón 'x' para borrar */
        [data-baseweb="tag"] span[role="button"] {
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)
# --- FIN DE LA MODIFICACIÓN ---


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

    # --- RECOPILACIÓN DE DATOS POR TIPO DE EMPLEADO ---
    employee_types_data = {}
    employee_type_names = [ chr(i+65) for i in range(NUMERO_TIPO_EMPLEADOS) ]  # 'A', 'B', 'C', ...

    for type_name in employee_type_names:
        st.markdown(f"### Configuración del Tipo {type_name}")
        max_employees = st.number_input(f"Nº Máximo de empleados del Tipo {type_name}", min_value=0, value=150, step=1, key=f"max_{type_name}")
        services_per_employee = st.number_input(f"Nº de servicios de fin de semana que cubre el Tipo {type_name}", min_value=1, value=4, max_value=8, step=1, key=f"serv_{type_name}")
        
        # Generar el mapa de patrones basado en la nueva lógica
        master_map = generate_pattern_map(services_per_employee)
        pattern_options = list(master_map.keys())
        
        selected_display_options = st.multiselect(
            f"Particiones de turnos permitidas para el Tipo {type_name}",
            options=pattern_options,
            key=f"multi_{type_name}"
        )
        
        employee_types_data[type_name] = {
            "max_employees": max_employees,
            "master_map": master_map, # Guardamos el mapa completo {display_str: (s,d)}
            "selected_patterns": selected_display_options # Guardamos solo los strings seleccionados
        }

# --- BOTÓN DE CÁLCULO (FUERA DEL EXPANDER) ---
if st.button("Calcular Plantilla Óptima", type="primary"):

    TOTAL_DEMANDA_SABADO = DEMANDA_SABADO * NUM_FINES_DE_SEMANA_MES
    TOTAL_DEMANDA_DOMINGO = DEMANDA_DOMINGO * NUM_FINES_DE_SEMANA_MES

    model = pulp.LpProblem("Minimizar_Plantilla_Fin_de_Semana", pulp.LpMinimize)

    # N_vars: Número TOTAL de empleados de cada tipo (A, B, C...)
    N_vars = pulp.LpVariable.dicts("TotalEmpleados", employee_type_names, lowBound=0, cat='Integer')

    # x_vars: Las claves (índices) ahora son los strings legibles (ej: "1 Sáb. solo...")
    x_vars = {}
    for type_name in employee_type_names:
        x_vars[type_name] = pulp.LpVariable.dicts(
            name=f"Empleados_{type_name}",
            indices=employee_types_data[type_name]["selected_patterns"],
            lowBound=0,
            cat='Integer'
        )

    # Objetivo: Minimizar el número total de empleados
    model += pulp.lpSum(N_vars), "Minimizar_Plantilla_Total"

    # Restricción de Sábados
    model += pulp.lpSum(
        # x_vars[tipo][string_patrón] * (sábados de ese string)
        x_vars[type_name][pattern_str] * employee_types_data[type_name]["master_map"][pattern_str][0] 
        for type_name in employee_type_names
        for pattern_str in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_SABADO, "Cobertura_Demanda_Sabados"

    # Restricción de Domingos
    model += pulp.lpSum(
        # x_vars[tipo][string_patrón] * (domingos de ese string)
        x_vars[type_name][pattern_str] * employee_types_data[type_name]["master_map"][pattern_str][1]
        for type_name in employee_type_names
        for pattern_str in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_DOMINGO, "Cobertura_Demanda_Domingos"

    # Restricciones de vínculo y máximos
    for type_name in employee_type_names:
        model += pulp.lpSum(
            x_vars[type_name][pattern_str] for pattern_str in employee_types_data[type_name]["selected_patterns"]
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

        results_data = []
        total_sabados_cubiertos = 0
        total_domingos_cubiertos = 0

        for type_name in employee_type_names:
            total_tipo_empleado = type_totals.get(type_name, 0)
            master_map = employee_types_data[type_name]["master_map"]
            
            for pattern_str in employee_types_data[type_name]["selected_patterns"]:
                num_empleados = x_vars[type_name][pattern_str].value()
                
                if num_empleados > 0:
                    # Buscar la tupla (Sáb, Dom) correspondiente al string
                    pulp_tuple = master_map[pattern_str] 
                    
                    sabados_aportados = num_empleados * pulp_tuple[0]
                    domingos_aportados = num_empleados * pulp_tuple[1]
                    total_sabados_cubiertos += sabados_aportados
                    total_domingos_cubiertos += domingos_aportados
                    
                    servicios_mes = pulp_tuple[0] + pulp_tuple[1]
                    # 'particion_str' ya es el string legible que queremos
                    
                    pct_del_tipo = (num_empleados / total_tipo_empleado * 100) if total_tipo_empleado > 0 else 0
                    pct_del_total = (num_empleados / total_empleados * 100) if total_empleados > 0 else 0

                    results_data.append({
                        "Tipo": f"Tipo {type_name}",
                        "Partición": pattern_str, # ¡Listo!
                        "Servicios/Mes": servicios_mes,
                        "Nº Empleados": int(num_empleados),
                        "% s/ Total Tipo": pct_del_tipo,
                        "% s/ Total Plantilla": pct_del_total,
                        "Sábados Cubiertos": int(sabados_aportados),
                        "Domingos Cubiertos": int(domingos_aportados)
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

            
            st.subheader("Asignación Detallada por Patrón")
            df_results = pd.DataFrame(results_data)
            
            column_order = [
                "Tipo", "Partición", "Servicios/Mes", "Nº Empleados",
                "% s/ Total Tipo", "% s/ Total Plantilla",
                "Sábados Cubiertos", "Domingos Cubiertos"
            ]
            
            # Asegurarse de que las columnas existen antes de reordenar
            df_results = df_results.reindex(columns=column_order)

            st.dataframe(
                df_results,
                use_container_width=True,
                column_config={
                    "% s/ Total Tipo": st.column_config.NumberColumn(format="%.2f%%"),
                    "% s/ Total Plantilla": st.column_config.NumberColumn(format="%.2f%%")
                }
            )
            
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
