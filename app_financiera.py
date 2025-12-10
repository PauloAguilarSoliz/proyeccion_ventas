import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import io
import xlsxwriter
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Consola Financiera IA", layout="wide", page_icon="📈")

# --- FUNCIONES AUXILIARES ---

MAPA_MESES = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
    'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
}

def escanear_mes_en_hoja(df_preview, nombre_pestana):
    nombre_pestana_limpio = nombre_pestana.strip().upper()
    for mes_nombre, mes_num in MAPA_MESES.items():
        if mes_nombre in nombre_pestana_limpio:
            return mes_num
    contenido_texto = df_preview.to_string().upper()
    for mes_nombre, mes_num in MAPA_MESES.items():
        if mes_nombre in contenido_texto:
            return mes_num
    return None

def detectar_anio_archivo(nombre_archivo, anio_default):
    match = re.search(r'(20[2-3][0-9])', nombre_archivo)
    if match:
        return int(match.group(1)), True
    return anio_default, False

def procesar_multiples_excels(archivos_subidos, anio_default_usuario):
    lista_datos = []
    log_errores = []
    log_anios = []

    for archivo in archivos_subidos:
        try:
            anio_archivo, encontrado = detectar_anio_archivo(archivo.name, anio_default_usuario)
            origen_anio = "Detectado en nombre" if encontrado else "Usado por defecto"
            log_anios.append(f"📄 {archivo.name} -> Año {anio_archivo} ({origen_anio})")

            xls = pd.ExcelFile(archivo)
            for nombre_hoja in xls.sheet_names:
                df_preview = pd.read_excel(archivo, sheet_name=nombre_hoja, nrows=15, header=None)
                mes_numero = escanear_mes_en_hoja(df_preview, nombre_hoja)
                
                if mes_numero:
                    col_monto = None
                    fila_encabezado = -1
                    for i, row in df_preview.iterrows():
                        fila_texto = row.astype(str).str.upper().tolist()
                        if "MONTO" in fila_texto:
                            fila_encabezado = i
                            break
                    
                    if fila_encabezado != -1:
                        df_datos = pd.read_excel(archivo, sheet_name=nombre_hoja, header=fila_encabezado)
                        df_datos.columns = df_datos.columns.str.strip().str.upper()
                        
                        if 'MONTO' in df_datos.columns:
                            df_datos['MONTO'] = pd.to_numeric(df_datos['MONTO'], errors='coerce')
                            df_datos = df_datos.dropna(subset=['MONTO'])
                            col_primera = df_datos.columns[0]
                            df_datos = df_datos[~df_datos[col_primera].astype(str).str.upper().str.contains("TOTAL", na=False)]
                            
                            venta_mensual = df_datos['MONTO'].sum()
                            fecha_construida = pd.Timestamp(year=anio_archivo, month=mes_numero, day=1)
                            
                            lista_datos.append({
                                'Fecha': fecha_construida,
                                'Ventas': venta_mensual,
                                'Fuente': f"{archivo.name} ({anio_archivo})"
                            })
        except Exception as e:
            log_errores.append(f"Error en {archivo.name}: {str(e)}")

    if lista_datos:
        df_final = pd.DataFrame(lista_datos)
        df_final = df_final.groupby('Fecha').sum(numeric_only=True).sort_index()
        if not df_final.empty:
            idx_completo = pd.date_range(start=df_final.index.min(), end=df_final.index.max(), freq='MS')
            df_final = df_final.reindex(idx_completo).fillna(0)
            df_final.index.name = 'Fecha'
        return df_final, log_errores, log_anios
    else:
        return None, log_errores, log_anios

def convertir_df_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Proyeccion')
    return output.getvalue()

# --- FRONTEND ---

st.title("🤖 Consola de Inteligencia Financiera v7.2")
st.markdown("### Sistema Multi-Anual Inteligente (Modo Agresivo)")

# 1. INGESTA
st.sidebar.header("1. Carga de Datos")
anio_default = st.sidebar.number_input("📅 Año por defecto", min_value=2020, max_value=2030, value=2024)
uploaded_files = st.sidebar.file_uploader("Arrastra tus archivos", type=["xlsx", "xls"], accept_multiple_files=True)

if not uploaded_files:
    st.info("👋 Sube los archivos para comenzar.")
    st.stop()

with st.spinner('Analizando...'):
    df_ventas, errores, log_anios = procesar_multiples_excels(uploaded_files, anio_default)

with st.expander("✅ Auditoría de Archivos Detectados", expanded=False):
    for log in log_anios:
        st.write(log)

if errores:
    with st.expander("⚠️ Alertas de Lectura"):
        for e in errores:
            st.write(f"- {e}")

if df_ventas is None or df_ventas.empty:
    st.error("❌ No se pudieron extraer datos.")
    st.stop()

# 2. MOTOR IA
st.sidebar.divider()
st.sidebar.header("2. Motor IA")

modo_prueba = st.sidebar.checkbox("🧪 Auditoría (Backtesting)", value=False)
volatilidad_input = st.sidebar.slider("Riesgo (%)", 1, 50, 10)
factor_riesgo = volatilidad_input / 100
meses_proy = st.sidebar.slider("Meses a Proyectar", 3, 24, 6)

try:
    if modo_prueba:
        if len(df_ventas) <= meses_proy:
            st.error("❌ Datos insuficientes para la prueba.")
            st.stop()
        train = df_ventas['Ventas'].iloc[:-meses_proy]
        test = df_ventas['Ventas'].iloc[-meses_proy:]
        datos_modelo = train
    else:
        datos_modelo = df_ventas['Ventas']

    # --- CAMBIO CLAVE AQUÍ: Lógica "Forzada" ---
    
    # Intentamos forzar el modelo estacional primero (Plan A)
    # Bajamos el requisito mínimo de 24 a 12 meses.
    # Usamos initialization_method='estimated' para que sea más flexible.
    modelo_exitoso = False
    modelo = None
    
    try:
        if len(datos_modelo) >= 12: # Mínimo absoluto un año
            modelo = ExponentialSmoothing(
                datos_modelo, 
                trend='add', 
                seasonal='add', 
                seasonal_periods=12,
                initialization_method='estimated' # ¡ESTA ES LA LLAVE MAESTRA!
            ).fit()
            modelo_exitoso = True
            if modo_prueba:
                 st.caption("✅ Auditoría usando Modelo Estacional (Forzado).")
    except Exception as e_seasonal:
        # Si falla el forzado, capturamos el error silenciosamente y seguimos al Plan B
        pass
    
    # Plan B: Si falló el estacional o hay muy pocos datos, usamos Tendencia
    if not modelo_exitoso:
        modelo = ExponentialSmoothing(
            datos_modelo, 
            trend='add', 
            seasonal=None, 
            damped_trend=True,
            initialization_method='estimated'
        ).fit()
        st.warning(f"⚠️ Nota: Usando Tendencia simple (Datos insuficientes para patrón anual robusto). Historia disponible: {len(datos_modelo)} meses.")

    proyeccion = modelo.forecast(meses_proy)
    
    if modo_prueba:
        errores_abs = abs(test - proyeccion)
        mape = (errores_abs / test).mean() * 100
        titulo = f"Auditoría: Precisión {100-mape:.1f}% (MAPE: {mape:.1f}%)"
    else:
        opt = proyeccion * (1 + factor_riesgo)
        pes = proyeccion * (1 - factor_riesgo)
        titulo = f"Proyección Futura ({meses_proy} meses)"

except Exception as e:
    st.error(f"Error matemático irrecuperable: {e}")
    st.stop()

# 3. VISUALIZACIÓN
tab1, tab2, tab3 = st.tabs(["📊 Gráfico", "📋 Tabla Detallada", "🗂️ Histórico"])

with tab1:
    st.subheader(titulo)
    fig, ax = plt.subplots(figsize=(12, 5))
    plt.style.use('bmh')
    
    if modo_prueba:
        ax.plot(train.index, train, label='Entrenamiento', color='#2c3e50')
        ax.plot(test.index, test, label='Realidad', color='green', marker='o')
        ax.plot(proyeccion.index, proyeccion, label='IA (Auditada)', color='#e67e22', linestyle='--')
        ax.fill_between(proyeccion.index, proyeccion*0.95, proyeccion*1.05, color='#e67e22', alpha=0.1)
    else:
        ax.plot(df_ventas.index, df_ventas['Ventas'], label='Histórico', color='#2c3e50')
        ax.plot([df_ventas.index[-1], proyeccion.index[0]], [df_ventas['Ventas'].iloc[-1], proyeccion.iloc[0]], color='#e67e22', linestyle='--')
        ax.plot(proyeccion.index, proyeccion, label='Base', color='#e67e22', linestyle='--', marker='o')
        ax.fill_between(proyeccion.index, pes, opt, color='#f1c40f', alpha=0.2)

    ax.legend()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    st.pyplot(fig)

with tab2:
    if modo_prueba:
        df_comp = pd.DataFrame({
            "Realidad": test, 
            "IA": proyeccion, 
            "Diferencia": test - proyeccion
        })
        st.dataframe(df_comp.style.format("${:,.2f}"), use_container_width=True)
    else:
        df_det = pd.DataFrame({"Pesimista": pes, "Base": proyeccion, "Optimista": opt})
        st.dataframe(df_det.style.format("${:,.2f}"), use_container_width=True)
        st.download_button("📥 Descargar Excel", convertir_df_a_excel(df_det), "proyeccion.xlsx")

with tab3:
    st.dataframe(df_ventas.sort_index(ascending=False).style.format("${:,.2f}"), use_container_width=True)
