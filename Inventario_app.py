<<<<<<< HEAD
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import os
import json

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Control de Inventario - Almacén Central",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# 2. CONEXIÓN CON GOOGLE SHEETS (Híbrida: Local o Cloud)
# ==========================================
@st.cache_resource
def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # Escenario A: Corriendo en Streamlit Cloud (leyendo desde st.secrets)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # Escenario B: Corriendo localmente (leyendo el archivo credentials.json)
        elif os.path.exists("credentials.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        else:
            st.error("No se encontraron credenciales válidas (ni en st.secrets ni en credentials.json).")
            return None
            
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error al autenticar con la cuenta de servicio: {e}")
        return None

client = init_connection()
SPREADSHEET_NAME = "Sistema de Control de Inventario y KPI - Almacén Central"

# ==========================================
# 3. CARGA DE DATOS DESDE GOOGLE SHEETS (MAESTRO)
# ==========================================
@st.cache_data(ttl=60)
def cargar_datos_maestro():
    if client:
        try:
            sheet_maestro = client.open(SPREADSHEET_NAME).worksheet("MAESTRO_SKU")
            data = sheet_maestro.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error al cargar la hoja MAESTRO_SKU: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

df_maestro = cargar_datos_maestro()

# ==========================================
# 4. INTERFAZ DE USUARIO (SIDEBAR Y MENÚ)
# ==========================================
st.sidebar.title("🗂️ Menú Principal")
menu = st.sidebar.selectbox(
    "Seleccione una opción",
    ["📊 Dashboard y KPIs", "📝 Registrar Movimientos", "📦 Maestro de SKUs"]
)

st.sidebar.markdown("---")
st.sidebar.info("Conectado de forma segura mediante Cuenta de Servicio a Google Sheets.")

# ==========================================
# 5. MÓDULO: DASHBOARD Y KPIS
# ==========================================
if menu == "📊 Dashboard y KPIs":
    st.title("📊 Dashboard General de Inventario")
    st.markdown("Indicadores clave de rendimiento y estado actual del almacén.")
    
    if not df_maestro.empty:
        total_skus = len(df_maestro)
        skus_activos = len(df_maestro[df_maestro["Estado"] == "Activo"]) if "Estado" in df_maestro.columns else total_skus
        
        skus_criticos = 0
        if "Estatus" in df_maestro.columns:
            skus_criticos = len(df_maestro[(df_maestro["Estatus"] == "Crítico") & (df_maestro["Estado"] == "Activo")])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Catálogo SKUs", total_skus)
        col2.metric("SKUs Activos", skus_activos)
        col3.metric("SKUs en Estado Crítico", skus_criticos, delta_color="inverse")
        
        st.markdown("---")
        st.subheader("📋 Resumen del Inventario Activo")
        if "Estado" in df_maestro.columns:
            df_activos = df_maestro[df_maestro["Estado"] == "Activo"]
            st.dataframe(df_activos, use_container_width=True)
        else:
            st.dataframe(df_maestro, use_container_width=True)
    else:
        st.warning("Cargando información del maestro o verifique la conexión con la hoja.")

# ==========================================
# 6. MÓDULO: REGISTRAR MOVIMIENTOS (Entradas/Salidas)
# ==========================================
elif menu == "📝 Registrar Movimientos":
    st.title("📝 Registro de Entradas y Salidas")
    st.markdown("Seleccione el SKU activo, el tipo de movimiento e ingrese la cantidad.")
    
    if not df_maestro.empty and "Estado" in df_maestro.columns:
        df_activos = df_maestro[df_maestro["Estado"] == "Activo"]
        lista_skus = df_activos["Código"].tolist() if "Código" in df_activos.columns else []
        
        if lista_skus:
            # Fecha automática del día (informativa / ineditable)
            fecha_hoy = datetime.date.today().strftime('%d/%m/%Y')
            st.markdown(f"📅 **Fecha del Movimiento:** `{fecha_hoy}` *(Generada automáticamente)*")
            st.markdown("---")
            
            # Selectores con index=None para que inicien completamente en blanco
            tipo_mov = st.selectbox(
                "Tipo de Movimiento", 
                ["ENTRADA", "SALIDA"], 
                index=None, 
                placeholder="Seleccione ENTRADA o SALIDA..."
            )
            
            sku_elegido = st.selectbox(
                "Seleccione el SKU Activo", 
                lista_skus, 
                index=None, 
                placeholder="Seleccione el código de SKU..."
            )
            
            # Solo mostrar información y formulario si el usuario ya seleccionó un SKU
            if sku_elegido:
                sku_info = df_activos[df_activos["Código"] == sku_elegido].iloc[0]
                existencia_actual = float(sku_info.get('Existencia Actual', 0))
                unidad_medida = str(sku_info.get('Unidad de Medida', ''))
                descripcion_sku = str(sku_info.get('Descripción', 'N/A'))
                categoria_sku = str(sku_info.get('Categoría', ''))
                ubicacion_sku = str(sku_info.get('Ubicación', ''))
                stock_minimo = float(sku_info.get('Stock Mínimo', 0))
                
                if existencia_actual <= 0:
                    st.error(f"⚠️ **Descripción:** {descripcion_sku} | **Existencia Actual:** {existencia_actual} {unidad_medida} (¡Stock Crítico/Negativo!)")
                else:
                    st.info(f"**Descripción:** {descripcion_sku} | **Existencia Actual:** {existencia_actual} {unidad_medida}")
                
                with st.form("form_inputs_movimiento", clear_on_submit=True):
                    label_cantidad = f"Cantidad a Movilizar ({unidad_medida})" if unidad_medida else "Cantidad a Movilizar"
                    cantidad = st.number_input(label_cantidad, min_value=0.00, value=0.00, step=1.0, format="%.2f")
                    destino = st.text_input("Destino / Proveedor / Responsable")
                    
                    submitted = st.form_submit_button("Guardar Movimiento en Google Sheets")
                    
                    if submitted:
                        if client:
                            try:
                                # Validaciones
                                if not tipo_mov:
                                    st.warning("⚠️ Debe seleccionar el tipo de movimiento (ENTRADA o SALIDA).")
                                    st.stop()
                                    
                                if cantidad <= 0:
                                    st.warning("⚠️ Debe ingresar una cantidad mayor a 0 para registrar el movimiento.")
                                    st.stop()
                                    
                                if tipo_mov == "SALIDA":
                                    if cantidad > existencia_actual:
                                        st.error(f"❌ Error de Validación: La cantidad solicitada ({cantidad}) supera la existencia actual en stock ({existencia_actual}).")
                                        st.stop()
                                    
                                    inventario_resultante = existencia_actual - cantidad
                                    if inventario_resultante < stock_minimo:
                                        st.error(f"❌ Error de Validación: Esta salida dejaría el inventario en **{inventario_resultante}**, lo cual viola el **Stock Mínimo de Seguridad ({stock_minimo})** establecido para este SKU.")
                                        st.stop()
                                
                                prefijo = "ENT" if tipo_mov == "ENTRADA" else "SAL"
                                sufijo = pd.Timestamp.now().strftime('%Y%m%d-%H%M%S')
                                nuevo_id = f"{prefijo}-{sufijo}"
                                
                                sheet_mov = client.open(SPREADSHEET_NAME).worksheet("REGISTRO_MOVIMIENTOS")
                                
                                nueva_fila = [
                                    nuevo_id,
                                    fecha_hoy,
                                    sku_elegido,
                                    categoria_sku,
                                    descripcion_sku,
                                    tipo_mov,
                                    float(cantidad),
                                    ubicacion_sku,
                                    destino
                                ]
                                
                                sheet_mov.append_row(nueva_fila)
                                
                                st.success(f"¡Movimiento registrado con éxito! ID: **{nuevo_id}**")
                                st.balloons()
                                st.cache_data.clear()
                                
                            except Exception as e:
                                st.error(f"Error al registrar el movimiento en Google Sheets: {e}")
                        else:
                            st.error("No hay conexión activa con Google Sheets.")
            else:
                st.info("👆 Por favor seleccione un SKU de la lista para continuar.")
        else:
            st.warning("No hay SKUs activos en el catálogo.")
    else:
        st.warning("No se pudieron cargar los datos del maestro.")

# ==========================================
# 7. MÓDULO: MAESTRO DE SKUS
# ==========================================
elif menu == "📦 Maestro de SKUs":
    st.title("🗂️ Catálogo Maestro de Artículos")
    st.markdown("Visualización completa del inventario, stock mínimo y existencias.")
    
    if not df_maestro.empty:
        busqueda = st.text_input("🔍 Buscar SKU o Descripción")
        
        if busqueda:
            df_filtrado = df_maestro[
                df_maestro.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)
            ]
            st.dataframe(df_filtrado, use_container_width=True)
        else:
            st.dataframe(df_maestro, use_container_width=True)
    else:
=======
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import os
import json

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Control de Inventario - Almacén Central",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# 2. CONEXIÓN CON GOOGLE SHEETS (Híbrida: Local o Cloud)
# ==========================================
@st.cache_resource
def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # Escenario A: Corriendo en Streamlit Cloud (leyendo desde st.secrets)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # Escenario B: Corriendo localmente (leyendo el archivo credentials.json)
        elif os.path.exists("credentials.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        else:
            st.error("No se encontraron credenciales válidas (ni en st.secrets ni en credentials.json).")
            return None
            
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error al autenticar con la cuenta de servicio: {e}")
        return None

client = init_connection()
SPREADSHEET_NAME = "Sistema de Control de Inventario y KPI - Almacén Central"

# ==========================================
# 3. CARGA DE DATOS DESDE GOOGLE SHEETS (MAESTRO)
# ==========================================
@st.cache_data(ttl=60)
def cargar_datos_maestro():
    if client:
        try:
            sheet_maestro = client.open(SPREADSHEET_NAME).worksheet("MAESTRO_SKU")
            data = sheet_maestro.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error al cargar la hoja MAESTRO_SKU: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

df_maestro = cargar_datos_maestro()

# ==========================================
# 4. INTERFAZ DE USUARIO (SIDEBAR Y MENÚ)
# ==========================================
st.sidebar.title("🗂️ Menú Principal")
menu = st.sidebar.selectbox(
    "Seleccione una opción",
    ["📊 Dashboard y KPIs", "📝 Registrar Movimientos", "📦 Maestro de SKUs"]
)

st.sidebar.markdown("---")
st.sidebar.info("Conectado de forma segura mediante Cuenta de Servicio a Google Sheets.")

# ==========================================
# 5. MÓDULO: DASHBOARD Y KPIS
# ==========================================
if menu == "📊 Dashboard y KPIs":
    st.title("📊 Dashboard General de Inventario")
    st.markdown("Indicadores clave de rendimiento y estado actual del almacén.")
    
    if not df_maestro.empty:
        total_skus = len(df_maestro)
        skus_activos = len(df_maestro[df_maestro["Estado"] == "Activo"]) if "Estado" in df_maestro.columns else total_skus
        
        skus_criticos = 0
        if "Estatus" in df_maestro.columns:
            skus_criticos = len(df_maestro[(df_maestro["Estatus"] == "Crítico") & (df_maestro["Estado"] == "Activo")])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Catálogo SKUs", total_skus)
        col2.metric("SKUs Activos", skus_activos)
        col3.metric("SKUs en Estado Crítico", skus_criticos, delta_color="inverse")
        
        st.markdown("---")
        st.subheader("📋 Resumen del Inventario Activo")
        if "Estado" in df_maestro.columns:
            df_activos = df_maestro[df_maestro["Estado"] == "Activo"]
            st.dataframe(df_activos, use_container_width=True)
        else:
            st.dataframe(df_maestro, use_container_width=True)
    else:
        st.warning("Cargando información del maestro o verifique la conexión con la hoja.")

# ==========================================
# 6. MÓDULO: REGISTRAR MOVIMIENTOS (Entradas/Salidas)
# ==========================================
elif menu == "📝 Registrar Movimientos":
    st.title("📝 Registro de Entradas y Salidas")
    st.markdown("Seleccione el SKU activo, el tipo de movimiento e ingrese la cantidad.")
    
    if not df_maestro.empty and "Estado" in df_maestro.columns:
        df_activos = df_maestro[df_maestro["Estado"] == "Activo"]
        lista_skus = df_activos["Código"].tolist() if "Código" in df_activos.columns else []
        
        if lista_skus:
            tipo_mov = st.selectbox("Tipo de Movimiento", ["ENTRADA", "SALIDA"])
            sku_elegido = st.selectbox("Seleccione el SKU Activo", lista_skus)
            
            sku_info = df_activos[df_activos["Código"] == sku_elegido].iloc[0]
            existencia_actual = float(sku_info.get('Existencia Actual', 0))
            unidad_medida = str(sku_info.get('Unidad de Medida', ''))
            descripcion_sku = str(sku_info.get('Descripción', 'N/A'))
            categoria_sku = str(sku_info.get('Categoría', ''))
            ubicacion_sku = str(sku_info.get('Ubicación', ''))
            stock_minimo = float(sku_info.get('Stock Mínimo', 0))
            
            if existencia_actual <= 0:
                st.error(f"⚠️ **Descripción:** {descripcion_sku} | **Existencia Actual:** {existencia_actual} {unidad_medida} (¡Stock Crítico/Negativo!)")
            else:
                st.info(f"**Descripción:** {descripcion_sku} | **Existencia Actual:** {existencia_actual} {unidad_medida}")
            
            with st.form("form_inputs_movimiento", clear_on_submit=True):
                label_cantidad = f"Cantidad a Movilizar ({unidad_medida})" if unidad_medida else "Cantidad a Movilizar"
                cantidad = st.number_input(label_cantidad, min_value=0.00, value=0.00, step=1.0, format="%.2f")
                destino = st.text_input("Destino / Proveedor / Responsable")
                
                submitted = st.form_submit_button("Guardar Movimiento en Google Sheets")
                
                if submitted:
                    if client:
                        try:
                            if cantidad <= 0:
                                st.warning("⚠️ Debe ingresar una cantidad mayor a 0 para registrar el movimiento.")
                                st.stop()
                                
                            if tipo_mov == "SALIDA":
                                if cantidad > existencia_actual:
                                    st.error(f"❌ Error de Validación: La cantidad solicitada ({cantidad}) supera la existencia actual en stock ({existencia_actual}).")
                                    st.stop()
                                
                                inventario_resultante = existencia_actual - cantidad
                                if inventario_resultante < stock_minimo:
                                    st.error(f"❌ Error de Validación: Esta salida dejaría el inventario en **{inventario_resultante}**, lo cual viola el **Stock Mínimo de Seguridad ({stock_minimo})** establecido para este SKU.")
                                    st.stop()
                            
                            prefijo = "ENT" if tipo_mov == "ENTRADA" else "SAL"
                            sufijo = pd.Timestamp.now().strftime('%Y%m%d-%H%M%S')
                            nuevo_id = f"{prefijo}-{sufijo}"
                            fecha_hoy = datetime.date.today().strftime('%d/%m/%Y')
                            
                            sheet_mov = client.open(SPREADSHEET_NAME).worksheet("REGISTRO_MOVIMIENTOS")
                            
                            nueva_fila = [
                                nuevo_id,
                                fecha_hoy,
                                sku_elegido,
                                categoria_sku,
                                descripcion_sku,
                                tipo_mov,
                                float(cantidad),
                                ubicacion_sku,
                                destino
                            ]
                            
                            sheet_mov.append_row(nueva_fila)
                            
                            st.success(f"¡Movimiento registrado con éxito! ID: **{nuevo_id}**")
                            st.balloons()
                            st.cache_data.clear()
                            
                        except Exception as e:
                            st.error(f"Error al registrar el movimiento en Google Sheets: {e}")
                    else:
                        st.error("No hay conexión activa con Google Sheets.")
        else:
            st.warning("No hay SKUs activos en el catálogo.")
    else:
        st.warning("No se pudieron cargar los datos del maestro.")

# ==========================================
# 7. MÓDULO: MAESTRO DE SKUS
# ==========================================
elif menu == "📦 Maestro de SKUs":
    st.title("🗂️ Catálogo Maestro de Artículos")
    st.markdown("Visualización completa del inventario, stock mínimo y existencias.")
    
    if not df_maestro.empty:
        busqueda = st.text_input("🔍 Buscar SKU o Descripción")
        
        if busqueda:
            df_filtrado = df_maestro[
                df_maestro.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)
            ]
            st.dataframe(df_filtrado, use_container_width=True)
        else:
            st.dataframe(df_maestro, use_container_width=True)
    else:
>>>>>>> fc12252552b74155b8e5f4451e72b11423dab0df
        st.warning("El catálogo maestro está vacío o no se pudo cargar.")