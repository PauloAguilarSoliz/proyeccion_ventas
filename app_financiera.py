import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Analítica Financiera Pro", layout="wide", page_icon="📈")

# --- FUNCIÓN DE LIMPIEZA AUTOMÁTICA (La "Lavadora") ---
def limpiar_datos(df_raw):
    """
    Esta función recibe el Excel crudo y lo transforma
    al formato que necesita la IA, sin importar nombres raros.
    """
    # 1. Estandarizar nombres de columnas (Quitar espacios, mayúsculas)
    df_raw.columns = df_raw.columns.str.strip().str.lower()
    
    # 2. Buscador inteligente de columnas
    # Buscamos cual columna parece ser 'fecha' y cual 'ventas'
    col_fecha = None
    col_ventas = None
    
    for col in df_raw.columns:
        if 'fecha' in col or 'date' in col or 'periodo' in col:
            col_fecha = col
        if 'venta' in col or 'sale' in col or 'monto' in col or 'cantidad' in col:
            col_ventas = col
            
    if not col_fecha or not col_ventas:
        return None, "❌ Error: No encontré columnas de 'Fecha' o 'Ventas' claras en el Excel."
    
    # 3. Renombrar para que el motor funcione siempre
    df_raw = df_raw.rename(columns={col_fecha: 'Fecha', col_ventas: 'Ventas'})
    
    # 4. Convertir fechas y ordenar
    try:
        df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'])
        df_raw = df_raw.sort_values('Fecha')
        df_raw = df_raw.set_index('Fecha')
        # Rellenar huecos si es mensual (frecuencia Mensual Start 'MS')
        df_raw = df_raw.asfreq('MS').fillna(method='ffill')
    except Exception as e:
        return None, f"❌ Error en formato de fechas: {e}"
        
    return df_raw, "✅ Datos procesados correctamente."

# --- INTERFAZ DE USUARIO (Frontend) ---
st.title("📈 Plataforma de Proyección Financiera IA")
st.markdown("""
**Instrucciones:**
1. Descarga el reporte de ventas del sistema.
2. Arrástralo al recuadro de abajo.
3. La IA limpiará los datos y generará la proyección.
""")

# --- 1. CARGADOR DE ARCHIVOS (Drag & Drop) ---
st.sidebar.header("📁 Carga de Datos")
uploaded_file = st.sidebar.file_uploader("Sube tu Excel de Ventas aquí", type=["xlsx", "xls", "csv"])

if uploaded_file is None:
    st.info("👋 ¡Hola! Por favor sube un archivo Excel para comenzar el análisis.")
    st.stop() # Detiene la app hasta que haya archivo

# --- 2. PROCESAMIENTO ---
try:
    # Leemos el archivo subido (ya no la ruta C:/...)
    df_original = pd.read_excel(uploaded_file)
    
    # Aplicamos la limpieza automática
    df_ventas, mensaje_status = limpiar_datos(df_original)
    
    if df_ventas is None:
        st.error(mensaje_status)
        st.stop()
    else:
        st.sidebar.success(mensaje_status)

except Exception as e:
    st.error(f"Error crítico al leer el archivo: {e}")
    st.stop()

# --- 3. CONTROLES DE ESCENARIOS ---
st.sidebar.divider()
st.sidebar.header("⚙️ Configuración de Riesgo")

volatilidad_input = st.sidebar.slider("Nivel de Volatilidad", 1, 50, 10, format="%d%%")
factor_riesgo = volatilidad_input / 100
dias_proyeccion = st.sidebar.slider("Meses a Proyectar", 3, 24, 6)

# --- 4. MOTOR IA ---
with st.spinner('Entrenando modelo matemático...'):
    modelo = ExponentialSmoothing(
        df_ventas['Ventas'],
        trend='add',
        seasonal='add',
        seasonal_periods=12
    ).fit()
    
    proyeccion = modelo.forecast(dias_proyeccion)
    
    # Escenarios
    escenario_optimista = proyeccion * (1 + factor_riesgo)
    escenario_pesimista = proyeccion * (1 - factor_riesgo)

# --- 5. VISUALIZACIÓN ---
tab1, tab2 = st.tabs(["📊 Gráfico de Proyección", "📋 Histórico de Ventas"])

with tab1:
    st.subheader(f"Proyección a {dias_proyeccion} Meses (Volatilidad: {volatilidad_input}%)")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    plt.style.use('bmh')
    
    # Histórico
    ax.plot(df_ventas.index, df_ventas['Ventas'], label='Histórico Real', color='#2c3e50', linewidth=2)
    
    # Conexión
    ultimo_real = df_ventas['Ventas'].iloc[-1]
    ax.plot([df_ventas.index[-1], proyeccion.index[0]], [ultimo_real, proyeccion.iloc[0]], 
            color='#e67e22', linestyle='--', linewidth=2)
    
    # Proyección
    ax.plot(proyeccion.index, proyeccion, label='Tendencia Base', color='#e67e22', linestyle='--', marker='o')
    ax.fill_between(proyeccion.index, escenario_pesimista, escenario_optimista, 
                    color='#f1c40f', alpha=0.2, label=f'Rango Riesgo (+/- {factor_riesgo*100:.0f}%)')
    
    ax.set_title("Túnel de Incertidumbre de Ventas")
    ax.legend()
    st.pyplot(fig)
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Pesimista (Total)", f"${escenario_pesimista.sum():,.2f}", delta="-Riesgo", delta_color="inverse")
    c2.metric("Esperado (Total)", f"${proyeccion.sum():,.2f}", delta="Base")
    c3.metric("Optimista (Total)", f"${escenario_optimista.sum():,.2f}", delta="+Oportunidad")

with tab2:
    st.subheader("Auditoría de Datos Históricos")
    st.markdown("Esta tabla muestra los datos reales que se usaron para entrenar al modelo.")
    # Mostramos los datos ordenados del más reciente al más antiguo
    st.dataframe(df_ventas.sort_index(ascending=False).style.format("${:,.2f}"))