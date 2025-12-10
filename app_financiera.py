import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import io
import xlsxwriter

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Consola Financiera IA", layout="wide", page_icon="📈")

# --- FUNCIONES AUXILIARES (INGENIERÍA DE DATOS) ---

MAPA_MESES = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
    'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
}

def escanear_mes_en_hoja(df_preview, nombre_pestana):
    """Busca el mes en la pestaña O en el contenido de las primeras filas."""
    nombre_pestana_limpio = nombre_pestana.strip().upper()
    # 1. Búsqueda rápida en pestaña
    for mes_nombre, mes_num in MAPA_MESES.items():
        if mes_nombre in nombre_pestana_limpio:
            return mes_num
    # 2. Búsqueda profunda en contenido
    contenido_texto = df_preview.to_string().upper()
    for mes_nombre, mes_num in MAPA_MESES.items():
        if mes_nombre in contenido_texto:
            return mes_num
    return None

def procesar_multiples_excels(archivos_subidos, anio_seleccionado):
    """Motor de ingesta inteligente para múltiples archivos y formatos."""
    lista_datos = []
    log_errores = []

    for archivo in archivos_subidos:
        try:
            xls = pd.ExcelFile(archivo)
            for nombre_hoja in xls.sheet_names:
                # Leemos preliminar para detectar mes y estructura
                df_preview = pd.read_excel(archivo, sheet_name=nombre_hoja, nrows=15, header=None)
                mes_numero = escanear_mes_en_hoja(df_preview, nombre_hoja)
                
                if mes_numero:
                    # Buscamos la fila "MONTO"
                    col_monto = None
                    fila_encabezado = -1
                    for i, row in df_preview.iterrows():
                        fila_texto = row.astype(str).str.upper().tolist()
                        if "MONTO" in fila_texto:
                            fila_encabezado = i
                            break
                    
                    if fila_encabezado != -1:
                        # Leemos la tabla real
                        df_datos = pd.read_excel(archivo, sheet_name=nombre_hoja, header=fila_encabezado)
                        df_datos.columns = df_datos.columns.str.strip().str.upper()
                        
                        if 'MONTO' in df_datos.columns:
                            df_datos['MONTO'] = pd.to_numeric(df_datos['MONTO'], errors='coerce')
                            df_datos = df_datos.dropna(subset=['MONTO'])
                            
                            # Filtro anti-totales
                            col_primera = df_datos.columns[0]
                            df_datos = df_datos[~df_datos[col_primera].astype(str).str.upper().str.contains("TOTAL", na=False)]
                            
                            venta_mensual = df_datos['MONTO'].sum()
                            fecha_construida = pd.Timestamp(year=anio_seleccionado, month=mes_numero, day=1)
                            
                            lista_datos.append({
                                'Fecha': fecha_construida,
                                'Ventas': venta_mensual,
                                'Fuente': f"{archivo.name} | {nombre_hoja}"
                            })
                        else:
                            log_errores.append(f"Mes detectado en '{nombre_hoja}', pero falta columna MONTO.")
                    else:
                        log_errores.append(f"Mes detectado en '{nombre_hoja}', pero no encontré encabezados.")
        except Exception as e:
            log_errores.append(f"Error en archivo {archivo.name}: {str(e)}")

    if lista_datos:
        df_final = pd.DataFrame(lista_datos)
        df_final = df_final.groupby('Fecha').sum(numeric_only=True).sort_index()
        # Rellenar meses faltantes con 0
        if not df_final.empty:
            idx_completo = pd.date_range(start=df_final.index.min(), end=df_final.index.max(), freq='MS')
            df_final = df_final.reindex(idx_completo).fillna(0)
            df_final.index.name = 'Fecha'
        return df_final, log_errores
    else:
        return None, log_errores

def convertir_df_a_excel(df):
    """Genera el binario de Excel para descarga."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Proyeccion')
    return output.getvalue()

# --- INTERFAZ GRÁFICA (FRONTEND) ---

st.title("🤖 Consola de Inteligencia Financiera v6.0")
st.markdown("### Sistema de Proyección y Auditoría")

# --- 1. BARRA LATERAL: INGESTA ---
st.sidebar.header("1. Carga de Datos")
anio_input = st.sidebar.number_input("📅 Año de los Reportes", min_value=2020, max_value=2030, value=2024)
uploaded_files = st.sidebar.file_uploader("Arrastra tus archivos Excel", type=["xlsx", "xls"], accept_multiple_files=True)

if not uploaded_files:
    st.info("👋 Sube tus reportes mensuales para iniciar.")
    st.stop()

# Procesamiento
with st.spinner('Procesando estructuras complejas...'):
    df_ventas, errores = procesar_multiples_excels(uploaded_files, anio_input)

if errores:
    with st.expander("⚠️ Alertas de Lectura (Hojas ignoradas)"):
        for e in errores:
            st.write(f"- {e}")

if df_ventas is None or df_ventas.empty:
    st.error("❌ No se pudieron extraer datos. Verifica títulos ('INFORME DE...') y columna 'MONTO'.")
    st.stop()

st.sidebar.success(f"✅ Datos cargados: {len(df_ventas)} meses.")

# --- 2. BARRA LATERAL: CONFIGURACIÓN IA ---
st.sidebar.divider()
st.sidebar.header("2. Motor de Inteligencia")

# ¡AQUÍ ESTÁ DE VUELTA! La opción de auditoría
modo_prueba = st.sidebar.checkbox("🧪 Activar Auditoría (Backtesting)", value=False, help="Oculta los últimos meses para verificar si la IA acierta.")

volatilidad_input = st.sidebar.slider("Nivel de Riesgo (%)", 1, 50, 10)
factor_riesgo = volatilidad_input / 100
meses_proy = st.sidebar.slider("Meses a Proyectar / Probar", 3, 24, 6)

# --- 3. LÓGICA DE MODELADO (FUSIÓN) ---
try:
    if modo_prueba:
        # LÓGICA DE AUDITORÍA (BACKTESTING)
        if len(df_ventas) <= meses_proy:
            st.error(f"❌ No tienes suficientes datos históricos ({len(df_ventas)}) para ocultar {meses_proy} meses.")
            st.stop()
            
        train = df_ventas.iloc[:-meses_proy]
        test = df_ventas.iloc[-meses_proy:]
        
        modelo = ExponentialSmoothing(train['Ventas'], trend='add', seasonal='add', seasonal_periods=min(len(train), 12)).fit()
        proyeccion = modelo.forecast(meses_proy)
        
        # Métricas de error
        errores_abs = abs(test['Ventas'] - proyeccion)
        mape = (errores_abs / test['Ventas']).mean() * 100
        precision = 100 - mape
        
        titulo_grafico = f"Resultado de Auditoría: Precisión {precision:.1f}% (MAPE: {mape:.1f}%)"
        
    else:
        # LÓGICA DE FUTURO (PROYECCIÓN NORMAL)
        modelo = ExponentialSmoothing(df_ventas['Ventas'], trend='add', seasonal='add', seasonal_periods=min(len(df_ventas), 12)).fit()
        proyeccion = modelo.forecast(meses_proy)
        
        # Escenarios
        opt = proyeccion * (1 + factor_riesgo)
        pes = proyeccion * (1 - factor_riesgo)
        
        titulo_grafico = f"Proyección Futura a {meses_proy} Meses"

except Exception as e:
    st.error(f"Error matemático en el modelo: {e}. Intenta subir más meses de historia.")
    st.stop()

# --- 4. VISUALIZACIÓN (TABS RESTAURADOS) ---
tab1, tab2, tab3 = st.tabs(["📊 Gráfico Principal", "📋 Tabla de Proyección", "🗂️ Datos Históricos"])

# TAB 1: GRÁFICO
with tab1:
    st.subheader(titulo_grafico)
    fig, ax = plt.subplots(figsize=(12, 5))
    plt.style.use('bmh')
    
    if modo_prueba:
        # Pintar Auditoría
        ax.plot(train.index, train['Ventas'], label='Entrenamiento', color='#2c3e50')
        ax.plot(test.index, test['Ventas'], label='Realidad (Oculta)', color='green', marker='o')
        ax.plot(proyeccion.index, proyeccion, label='Predicción IA', color='#e67e22', linestyle='--')
        ax.fill_between(proyeccion.index, proyeccion*0.95, proyeccion*1.05, color='#e67e22', alpha=0.1)
    else:
        # Pintar Futuro
        ax.plot(df_ventas.index, df_ventas['Ventas'], label='Histórico', color='#2c3e50')
        # Conector visual
        ax.plot([df_ventas.index[-1], proyeccion.index[0]], [df_ventas['Ventas'].iloc[-1], proyeccion.iloc[0]], color='#e67e22', linestyle='--')
        ax.plot(proyeccion.index, proyeccion, label='Base', color='#e67e22', linestyle='--', marker='o')
        ax.fill_between(proyeccion.index, pes, opt, color='#f1c40f', alpha=0.2, label=f'Riesgo +/-{volatilidad_input}%')

    ax.legend()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    st.pyplot(fig)

# TAB 2: TABLA DE PROYECCIÓN (RESTAURADA)
with tab2:
    st.subheader("Detalle Numérico")
    if modo_prueba:
        # Tabla comparativa Real vs IA
        df_comp = pd.DataFrame({
            "Realidad": test['Ventas'],
            "Predicción IA": proyeccion,
            "Diferencia": test['Ventas'] - proyeccion
        })
        st.dataframe(df_comp.style.format("${:,.2f}"), use_container_width=True)
    else:
        # Tabla de escenarios futuros
        df_detalle = pd.DataFrame({
            "Pesimista": pes,
            "Base (Esperado)": proyeccion,
            "Optimista": opt
        })
        st.dataframe(df_detalle.style.format("${:,.2f}"), use_container_width=True)
        
        # Botón de Descarga
        excel_data = convertir_df_a_excel(df_detalle)
        st.download_button(
            label="📥 Descargar Proyección en Excel",
            data=excel_data,
            file_name='proyeccion_ia.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

# TAB 3: DATOS HISTÓRICOS (RESTAURADA)
with tab3:
    st.subheader("Auditoría de Datos Extraídos")
    st.write(f"Se consolidaron {len(df_ventas)} meses a partir de los archivos subidos.")
    st.dataframe(df_ventas.sort_index(ascending=False).style.format("${:,.2f}"), use_container_width=True)
