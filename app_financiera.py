import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import io

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Analítica Financiera Pro", layout="wide", page_icon="📈")

# --- FUNCIÓN DE LIMPIEZA AUTOMÁTICA ---
def limpiar_datos(df_raw):
    df_raw.columns = df_raw.columns.str.strip().str.lower()
    col_fecha = None
    col_ventas = None
    
    for col in df_raw.columns:
        if 'fecha' in col or 'date' in col or 'periodo' in col:
            col_fecha = col
        if 'venta' in col or 'sale' in col or 'monto' in col or 'cantidad' in col:
            col_ventas = col
            
    if not col_fecha or not col_ventas:
        return None, "❌ Error: No encontré columnas de 'Fecha' o 'Ventas' claras."
    
    df_raw = df_raw.rename(columns={col_fecha: 'Fecha', col_ventas: 'Ventas'})
    
    try:
        df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'])
        df_raw = df_raw.sort_values('Fecha')
        df_raw = df_raw.set_index('Fecha')
        df_raw = df_raw.asfreq('MS').fillna(method='ffill')
    except Exception as e:
        return None, f"❌ Error en formato de fechas: {e}"
        
    return df_raw, "✅ Datos procesados correctamente."

# --- FUNCIÓN PARA DESCARGAR EXCEL ---
def convertir_df_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Proyeccion')
    return output.getvalue()

# --- INTERFAZ DE USUARIO ---
st.title("📈 Plataforma de Proyección Financiera IA")
st.markdown("""
**Instrucciones:** Sube tu histórico de ventas y ajusta los escenarios de riesgo.
""")

# --- 1. CARGADOR ---
st.sidebar.header("📁 Carga de Datos")
uploaded_file = st.sidebar.file_uploader("Sube tu Excel de Ventas aquí", type=["xlsx", "xls", "csv"])

if uploaded_file is None:
    st.info("👋 Por favor sube un archivo Excel para comenzar.")
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
st.sidebar.header("⚙️ Configuración de Riesgo")

volatilidad_input = st.sidebar.slider("Nivel de Volatilidad", 1, 50, 10, format="%d%%")
factor_riesgo = volatilidad_input / 100
dias_proyeccion = st.sidebar.slider("Meses a Proyectar", 3, 24, 6)

# --- 4. MOTOR IA ---
with st.spinner('Calculando escenarios...'):
    modelo = ExponentialSmoothing(
        df_ventas['Ventas'],
        trend='add',
        seasonal='add',
        seasonal_periods=12
    ).fit()
    
    proyeccion = modelo.forecast(dias_proyeccion)
    
    escenario_optimista = proyeccion * (1 + factor_riesgo)
    escenario_pesimista = proyeccion * (1 - factor_riesgo)

# --- 5. VISUALIZACIÓN ---
tab1, tab2 = st.tabs(["📊 Tablero de Control", "📋 Datos Históricos"])

with tab1:
    st.subheader(f"Proyección a {dias_proyeccion} Meses (Volatilidad: {volatilidad_input}%)")
    
    # A. GRÁFICO
    fig, ax = plt.subplots(figsize=(12, 5))
    plt.style.use('bmh')
    
    ax.plot(df_ventas.index, df_ventas['Ventas'], label='Histórico', color='#2c3e50', linewidth=2)
    
    ultimo_real = df_ventas['Ventas'].iloc[-1]
    ax.plot([df_ventas.index[-1], proyeccion.index[0]], [ultimo_real, proyeccion.iloc[0]], 
            color='#e67e22', linestyle='--', linewidth=2)
    
    ax.plot(proyeccion.index, proyeccion, label='Proyección Base', color='#e67e22', linestyle='--', marker='o')
    ax.fill_between(proyeccion.index, escenario_pesimista, escenario_optimista, 
                    color='#f1c40f', alpha=0.2, label=f'Rango Riesgo (+/- {factor_riesgo*100:.0f}%)')
    
    ax.legend()
    st.pyplot(fig)
    
    # B. MÉTRICAS
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Pesimista (Total)", f"${escenario_pesimista.sum():,.2f}", delta="-Riesgo", delta_color="inverse")
    c2.metric("Esperado (Total)", f"${proyeccion.sum():,.2f}", delta="Base")
    c3.metric("Optimista (Total)", f"${escenario_optimista.sum():,.2f}", delta="+Oportunidad")
    
    # C. TABLA DETALLADA (LO QUE PEDISTE)
    st.divider()
    st.subheader("📋 Detalle Mensual de Proyección")
    
    # Creamos un DataFrame limpio para mostrar
    df_detalle = pd.DataFrame({
        "Escenario Pesimista": escenario_pesimista,
        "Proyección Base": proyeccion,
        "Escenario Optimista": escenario_optimista
    })
    
    # Mostramos la tabla con formato de dinero
    st.dataframe(
        df_detalle.style.format("${:,.2f}"), 
        use_container_width=True
    )
    
    # D. BOTÓN DE DESCARGA
    excel_data = convertir_df_a_excel(df_detalle)
    st.download_button(
        label="📥 Descargar Proyección en Excel",
        data=excel_data,
        file_name='proyeccion_ventas_ia.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

with tab2:
    st.subheader("Auditoría de Datos Históricos")
    st.dataframe(df_ventas.sort_index(ascending=False).style.format("${:,.2f}"), use_container_width=True)
