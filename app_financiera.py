import pandas as pd
import numpy as np

# Configuración
anios = 5
meses = anios * 12
fecha_inicio = '2019-01-01'

# 1. Crear fechas
fechas = pd.date_range(start=fecha_inicio, periods=meses, freq='MS')

# 2. Crear componentes de la serie
# A. Tendencia: El negocio crece un poco cada mes
tendencia = np.linspace(10000, 25000, meses) 

# B. Estacionalidad: Patrón de ventas (Bajo en Enero, Alto en Diciembre)
# Multiplicadores para cada mes (Ene=0.8, ..., Dic=1.5)
patron_anual = [0.85, 0.80, 0.95, 1.0, 1.05, 1.0, 1.05, 1.1, 0.95, 1.1, 1.3, 1.6]
estacionalidad = np.tile(patron_anual, anios)

# C. Ruido (Aleatoriedad del mundo real)
ruido = np.random.normal(0, 500, meses)

# 3. Calcular Venta Final
ventas = (tendencia * estacionalidad) + ruido

# 4. Crear DataFrame y Exportar
df = pd.DataFrame({
    'Fecha': fechas,
    'Ventas Totales': ventas
})

nombre_archivo = "ventas_retail_sample.xlsx"
df.to_excel(nombre_archivo, index=False)

print(f"✅ ¡Archivo '{nombre_archivo}' generado con éxito!")
print(f"   Contiene {meses} meses de datos simulados.")
