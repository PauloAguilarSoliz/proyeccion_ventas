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
