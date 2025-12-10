import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import io
import xlsxwriter

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Consola Financiera IA", layout="wide", page_icon="📊")

# --- MAPA DE MESES (DICCIONARIO) ---
# Usamos esto para convertir texto a número
MAPA_MESES = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
    'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
}

# --- FUNCIÓN INTELIGENTE: ESCÁNER DE MES ---
def escanear_mes_en_hoja(df_preview, nombre_pestana):
    """
    1. Busca en el nombre de la pestaña.
    2. Si no encuentra, busca dentro de las primeras filas del Excel (Títulos).
    """
    # ESTRATEGIA 1: Nombre de la pestaña (Rápido)
    nombre_pestana_limpio = nombre_pestana.strip().upper()
    for mes_nombre, mes_num in MAPA_MESES.items():
        if mes_nombre in nombre_pestana_limpio:
            return mes_num

    # ESTRATEGIA 2: Escaneo de Contenido (Profundo)
    # Convertimos las primeras filas a un solo texto gigante en mayúsculas
    # df_preview son solo las primeras 10 filas leídas sin encabezado
    contenido_texto = df_preview.to_string().upper()
    
    for mes_nombre, mes_num in MAPA_MESES.items():
        # Buscamos "ENERO", "FEBRERO" en el texto de las celdas
        # Agregamos espacios para evitar falsos positivos (ej: que no detecte MAYO en "MAYORISTA")
        # Buscamos el mes tal cual.
        if mes_nombre in contenido_texto:
            return mes_num
            
    return None # No se encontró nada

# --- FUNCIÓN DE LIMPIEZA AVANZADA (EL COSECHADOR v2) ---
def procesar_multiples_excels(archivos_subidos, anio_seleccionado):
    lista_datos = []
    log_errores = []

    for archivo in archivos_subidos:
        try:
            xls = pd.ExcelFile(archivo)
            
            for nombre_hoja in xls.sheet_names:
                # PASO 1: LEER PRELIMINAR (Solo 15 filas, sin encabezado)
                # Esto es para "espiar" el contenido y buscar el título del mes
                df_preview = pd.read_excel(archivo, sheet_name=nombre_hoja, nrows=15, header=None)
                
                # PASO 2: DETECTAR MES (Usando Pestaña O Contenido)
                mes_numero = escanear_mes_en_hoja(df_preview, nombre_hoja)
                
                if mes_numero:
                    # PASO 3: ENCONTRAR LA TABLA REAL (Buscando "MONTO")
                    col_monto = None
                    fila_encabezado = -1
                    
                    # Usamos el mismo df_preview para buscar la fila "MONTO"
                    for i, row in df_preview.iterrows():
                        fila_texto = row.astype(str).str.upper().tolist()
                        # Buscamos coincidencia exacta o parcial segura
                        if "MONTO" in fila_texto:
                            fila_encabezado = i
                            break
                    
                    if fila_encabezado != -1:
                        # Recargamos la hoja, pero ahora saltando las filas hasta el encabezado correcto
                        df_datos = pd.read_excel(archivo, sheet_name=nombre_hoja, header=fila_encabezado)
                        df_datos.columns = df_datos.columns.str.strip().str.upper()
                        
                        if 'MONTO' in df_datos.columns:
                            # Limpieza de datos
                            df_datos['MONTO'] = pd.to_numeric(df_datos['MONTO'], errors='coerce')
                            df_datos = df_datos.dropna(subset=['MONTO'])
                            
                            # Filtro anti-totales (Evitar duplicar con la fila 'TOTAL')
                            col_primera = df_datos.columns[0]
                            df_datos = df_datos[~df_datos[col_primera].astype(str).str.upper().str.contains("TOTAL", na=False)]
                            
                            venta_mensual = df_datos['MONTO'].sum()
                            
                            # Construir fecha final
                            fecha_construida = pd.Timestamp(year=anio_seleccionado, month=mes_numero, day=1)
                            
                            lista_datos.append({
                                'Fecha': fecha_construida,
                                'Ventas': venta_mensual,
                                'Fuente': f"{archivo.name} | {nombre_hoja}"
                            })
                        else:
                            log_errores.append(f"Encontré mes {mes_numero} en '{nombre_hoja}' pero no la columna 'MONTO'.")
                    else:
                        log_errores.append(f"En '{nombre_hoja}' detecté el mes, pero no la fila de encabezados 'MONTO'.")
                else:
                    # Si no encuentra mes ni en pestaña ni en contenido, ignora la hoja.
                    pass

        except Exception as e:
            log_errores.append(f"Error crítico en archivo {archivo.name}: {str(e)}")

    if lista_datos:
        df_final = pd.DataFrame(lista_datos)
        # Sumamos por fecha (por si hay dos archivos del mismo mes, los consolida)
        df_final = df_final.groupby('Fecha').sum().sort_index()
        
        # Relleno de meses faltantes
        idx_completo = pd.date_range(start=df_final.index.min(), end=df_final.index.max(), freq='MS')
        df_final = df_final.reindex(idx_completo).fillna(0)
        df_final.index.name = 'Fecha'
        return df_final, log_errores
    else:
        return None, log_errores

# --- UI PRINCIPAL ---
st.title("🤖 Consola de Inteligencia Financiera")
st.markdown("### 📂 Ingesta Inteligente (Multiformato)")
st.info("El sistema buscará el mes en el nombre de la pestaña O dentro del título del reporte (ej: 'INFORME DE FEBRERO').")

st.sidebar.header("1. Configuración")

# A. SELECTOR DE AÑO
anio_input = st.sidebar.number_input("📅 Año Correspondiente", min_value=2020, max_value=2030, value=2024)

# B. CARGADOR
uploaded_files = st.sidebar.file_uploader(
    "Arrastra tus archivos Excel aquí", 
    type=["xlsx", "xls"], 
    accept_multiple_files=True
)

if not uploaded_files:
    st.warning("👋 Sube los reportes para iniciar.")
    st.stop()

# --- PROCESAMIENTO ---
with st.spinner('🔍 Escaneando contenido de los archivos...'):
    df_ventas, errores = procesar_multiples_excels(uploaded_files, anio_input)

if errores:
    with st.expander("⚠️ Reporte de Lectura (Detalles técnicos)"):
        for e in errores:
            st.write(f"- {e}")

if df_ventas is None:
    st.error("❌ No pude detectar meses ni montos. Verifica que los archivos tengan títulos como 'INFORME DE ENERO' y columna 'MONTO'.")
    st.stop()

st.sidebar.success(f"✅ ¡Éxito! Procesados {len(df_ventas)} meses.")

# --- VISUALIZACIÓN ---
st.sidebar.divider()
st.sidebar.header("2. Proyección IA")
volatilidad = st.sidebar.slider("Nivel de Riesgo", 1, 50, 10) / 100
meses_proy = st.sidebar.slider("Meses a Proyectar", 3, 24, 6)

# Modelo IA
modelo = ExponentialSmoothing(
    df_ventas['Ventas'], trend='add', seasonal='add', seasonal_periods=min(len(df_ventas), 12)
).fit() if len(df_ventas) >= 12 else ExponentialSmoothing(df_ventas['Ventas'], trend='add').fit()

proyeccion = modelo.forecast(meses_proy)
opt = proyeccion * (1 + volatilidad)
pes = proyeccion * (1 - volatilidad)

# TABS
tab1, tab2 = st.tabs(["📈 Tablero de Mando", "📋 Datos Crudos"])

with tab1:
    st.subheader(f"Proyección Consolidada {anio_input}")
    fig, ax = plt.subplots(figsize=(12, 5))
    plt.style.use('bmh')
    
    ax.plot(df_ventas.index, df_ventas['Ventas'], label='Histórico Detectado', color='#2c3e50', marker='o')
    ax.plot(proyeccion.index, proyeccion, label='Tendencia IA', color='#e67e22', linestyle='--')
    ax.fill_between(proyeccion.index, pes, opt, color='#f1c40f', alpha=0.2)
    
    ax.legend()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    st.pyplot(fig)
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Cierre Proyectado (Pesimista)", f"${pes.sum():,.0f}")
    c2.metric("Cierre Proyectado (Base)", f"${proyeccion.sum():,.0f}")
    c3.metric("Cierre Proyectado (Optimista)", f"${opt.sum():,.0f}")

with tab2:
    st.write("Datos extraídos automáticamente de los reportes:")
    st.dataframe(df_ventas.style.format("${:,.2f}"), use_container_width=True)
