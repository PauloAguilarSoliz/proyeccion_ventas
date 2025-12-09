import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import io
import xlsxwriter # Importante para que funcione la descarga

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Analítica Financiera Pro", layout="wide", page_icon="📈")

# --- FUNCIÓN DE LIMPIEZA AUTOMÁTICA (MEJORADA v2) ---
def limpiar_datos(df_raw):
    # 1. Limpieza de encabezados
    df_raw.columns = df_raw.columns.str.strip().str.lower()
    col_fecha = None
    col_ventas = None
    
    # 2. Detección inteligente de columnas
    for col in df_raw.columns:
        if 'fecha' in col or 'date' in col or 'periodo' in col:
            col_fecha = col
        if 'venta' in col or 'sale' in col or 'monto' in col or 'cantidad' in col:
            col_ventas = col
            
    if not col_fecha or not col_ventas:
        return None, "❌ Error: No encontré columnas de 'Fecha' o 'Ventas' claras."
    
    # 3. Renombrar y dar formato
    df_raw = df_raw.rename(columns={col_fecha: 'Fecha', col_ventas: 'Ventas'})
    
    try:
        df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'])
        df_raw = df_raw.sort_values('Fecha')
        df_raw = df_raw.set_index('Fecha')
        
        # --- CAMBIO CLAVE AQUÍ ---
        # En lugar de solo rellenar (asfreq), le decimos que SUME las ventas del mes.
        # 'MS' significa Month Start (Inicio de Mes).
        df_raw = df_raw.resample('MS').sum()
        
        # Si después de sumar quedan meses en 0 (porque no hubo ventas), 
        # reemplazamos con un valor pequeño o el promedio para no romper la IA
        # (Opcional: Holt-Winters maneja bien los datos pero prefiere no ceros)
        df_raw['Ventas'] = df_raw['Ventas'].replace(0, pd.NA).fillna(method='ffill')
        
    except Exception as e:
        return None, f"❌ Error al procesar las fechas: {e}"
        
    return df_raw, "✅ Datos procesados y Agrupados por Mes correctamente."
# --- FUNCIÓN PARA DESCARGAR EXCEL ---
def convertir_df_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Proyeccion')
    return output.getvalue()

# --- INTERFAZ DE USUARIO ---
st.title("📈 Plataforma de Proyección Financiera IA")

# --- 1. CARGADOR ---
st.sidebar.header("📁 Carga de Datos")
uploaded_file = st.sidebar.file_uploader("Sube tu Excel de Ventas aquí", type=["xlsx", "xls", "csv"])

if uploaded_file is None:
    st.info("👋 Sube un archivo Excel para comenzar.")
    st.stop()

# --- 2. PROCESAMIENTO ---
try:
    df_original = pd.read_excel(uploaded_file)
    df_ventas, mensaje_status = limpiar_datos(df_original)
    
    if df_ventas is None:
        st.error(mensaje_status)
        st.stop()
    else:
        st.sidebar.success(mensaje_status)

except Exception as e:
    st.error(f"Error crítico: {e}")
    st.stop()

# --- 3. CONTROLES ---
st.sidebar.divider()
st.sidebar.header("⚙️ Configuración")

# Opción de Backtesting (NUEVO)
modo_prueba = st.sidebar.checkbox("🧪 Activar Modo Prueba (Backtesting)", value=False, help="Oculta los últimos meses reales para verificar si la IA acierta.")

volatilidad_input = st.sidebar.slider("Nivel de Volatilidad", 1, 50, 10, format="%d%%")
factor_riesgo = volatilidad_input / 100

meses_input = st.sidebar.slider("Meses a Proyectar / Ocultar", 3, 24, 6)

# --- 4. MOTOR IA (LÓGICA DUAL) ---
with st.spinner('Procesando...'):
    
    if modo_prueba:
        # --- MODO BACKTESTING (Viaje al pasado) ---
        st.warning(f"⚠️ MODO PRUEBA ACTIVO: Ocultando los últimos {meses_input} meses reales para validar la IA.")
        
        # Cortamos los datos
        datos_entrenamiento = df_ventas.iloc[:-meses_input] # Todo MENOS los últimos X meses
        datos_reales_ocultos = df_ventas.iloc[-meses_input:] # Solo los últimos X meses (La Verdad)
        
        modelo = ExponentialSmoothing(
            datos_entrenamiento['Ventas'],
            trend='add',
            seasonal='add',
            seasonal_periods=12
        ).fit()
        
        # Predecimos el periodo oculto
        proyeccion = modelo.forecast(meses_input)
        
        # Calculamos el error (MAPE)
        errores = abs(datos_reales_ocultos['Ventas'] - proyeccion)
        mape = (errores / datos_reales_ocultos['Ventas']).mean() * 100
        precision = 100 - mape
        
    else:
        # --- MODO NORMAL (Hacia el futuro) ---
        modelo = ExponentialSmoothing(
            df_ventas['Ventas'],
            trend='add',
            seasonal='add',
            seasonal_periods=12
        ).fit()
        
        proyeccion = modelo.forecast(meses_input)
        precision = None # No sabemos la precisión del futuro aún

    # Escenarios de Riesgo
    escenario_optimista = proyeccion * (1 + factor_riesgo)
    escenario_pesimista = proyeccion * (1 - factor_riesgo)

# --- 5. VISUALIZACIÓN ---
tab1, tab2 = st.tabs(["📊 Tablero Analítico", "📋 Datos Detallados"])

with tab1:
    
    # TITULO DINÁMICO
    if modo_prueba:
        st.subheader(f"Resultado de la Prueba: Precisión del {precision:.1f}% (MAPE: {mape:.1f}%)")
    else:
        st.subheader(f"Proyección Futura a {meses_input} Meses")
    
    fig, ax = plt.subplots(figsize=(12, 5))
    plt.style.use('bmh')
    
    if modo_prueba:
        # GRAFICAR MODO PRUEBA
        # 1. Historia conocida
        ax.plot(datos_entrenamiento.index, datos_entrenamiento['Ventas'], label='Entrenamiento (Visible)', color='#2c3e50')
        # 2. Realidad oculta (La verdad)
        ax.plot(datos_reales_ocultos.index, datos_reales_ocultos['Ventas'], label='Realidad (Oculta)', color='green', linewidth=2, marker='x')
        # 3. Lo que dijo la IA
        ax.plot(proyeccion.index, proyeccion, label='Predicción IA', color='#e67e22', linestyle='--', marker='o')
        
    else:
        # GRAFICAR MODO FUTURO
        ax.plot(df_ventas.index, df_ventas['Ventas'], label='Histórico Real', color='#2c3e50', linewidth=2)
        # Conector
        ultimo_real = df_ventas['Ventas'].iloc[-1]
        ax.plot([df_ventas.index[-1], proyeccion.index[0]], [ultimo_real, proyeccion.iloc[0]], 
                color='#e67e22', linestyle='--', linewidth=2)
        # Proyección
        ax.plot(proyeccion.index, proyeccion, label='Proyección Base', color='#e67e22', linestyle='--', marker='o')
        ax.fill_between(proyeccion.index, escenario_pesimista, escenario_optimista, 
                        color='#f1c40f', alpha=0.2, label=f'Rango Riesgo (+/- {factor_riesgo*100:.0f}%)')
    
    ax.legend()
    st.pyplot(fig)
    
    # MÉTRICAS Y TABLAS
    st.divider()
    
    if modo_prueba:
        # En modo prueba mostramos la comparación Real vs IA
        df_comparativo = pd.DataFrame({
            "Realidad": datos_reales_ocultos['Ventas'],
            "Predicción IA": proyeccion,
            "Diferencia $": datos_reales_ocultos['Ventas'] - proyeccion,
            "Error %": ((abs(datos_reales_ocultos['Ventas'] - proyeccion) / datos_reales_ocultos['Ventas']) * 100)
        })
        st.write("🔎 **Comparativa: Realidad vs IA**")
        st.dataframe(df_comparativo.style.format({
            "Realidad": "${:,.2f}", 
            "Predicción IA": "${:,.2f}", 
            "Diferencia $": "${:,.2f}", 
            "Error %": "{:.2f}%"
        }))
        
    else:
        # En modo normal mostramos los escenarios
        c1, c2, c3 = st.columns(3)
        c1.metric("Pesimista", f"${escenario_pesimista.sum():,.2f}", delta="-Riesgo", delta_color="inverse")
        c2.metric("Esperado", f"${proyeccion.sum():,.2f}", delta="Base")
        c3.metric("Optimista", f"${escenario_optimista.sum():,.2f}", delta="+Oportunidad")
        
        st.subheader("📋 Detalle de Proyección")
        df_detalle = pd.DataFrame({
            "Pesimista": escenario_pesimista,
            "Base": proyeccion,
            "Optimista": escenario_optimista
        })
        st.dataframe(df_detalle.style.format("${:,.2f}"), use_container_width=True)
        
        # Botón Excel
        excel_data = convertir_df_a_excel(df_detalle)
        st.download_button(
            label="📥 Descargar Excel",
            data=excel_data,
            file_name='proyeccion_ia.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

with tab2:
    st.subheader("Auditoría de Datos")
    st.dataframe(df_ventas.sort_index(ascending=False).style.format("${:,.2f}"), use_container_width=True)

