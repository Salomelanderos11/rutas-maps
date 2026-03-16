#%%
import requests
import math
from ipyleaflet import Map, Marker, FullScreenControl, LayerGroup, Polyline
import ipywidgets as widgets
from IPython.display import display

sur = 24.796998
oeste = -107.401461
norte = 24.812974
este = -107.387524

def extraer_nodos_sector(south, west, north, east):
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:60];
    (way["highway"~"primary|secondary|tertiary|residential"]({south},{west},{north},{east}););
    out body; >; out skel qt;
    """
    r = requests.post(url, data={'data': query})
    if r.status_code == 200:
        return r.json().get('elements', [])
    return []

data = extraer_nodos_sector(sur, oeste, norte, este)
nodos_coords = {e['id']: (e['lat'], e['lon']) for e in data if e['type'] == 'node'}

def calcular_distancia(p1, p2):
    lat1, lon1 = p1
    lat2, lon2 = p2
    radio_tierra = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return radio_tierra * c

def obtener_id_mas_cercano(lat_clic, lon_clic, nodos_dict):
    distancia_minima = float('inf')
    id_mas_cercano = None
    for nodo_id, coords in nodos_dict.items():
        dist = calcular_distancia((lat_clic, lon_clic), coords)
        if dist < distancia_minima:
            distancia_minima = dist
            id_mas_cercano = nodo_id
    return id_mas_cercano, distancia_minima

def construir_grafo(data):
    grafo = {}
    nodos_c = {e['id']: (e['lat'], e['lon']) for e in data if e['type'] == 'node'}
    for ele in data:
        if ele['type'] == 'way':
            nodos_en_calle = ele.get('nodes', [])
            for i in range(len(nodos_en_calle) - 1):
                u = nodos_en_calle[i]
                v = nodos_en_calle[i+1]
                if u in nodos_c and v in nodos_c:
                    dist = calcular_distancia(nodos_c[u], nodos_c[v])
                    if u not in grafo:
                        grafo[u] = {'lat': nodos_c[u][0], 'lon': nodos_c[u][1], 'vecinos': []}
                    if v not in grafo:
                        grafo[v] = {'lat': nodos_c[v][0], 'lon': nodos_c[v][1], 'vecinos': []}
                    grafo[u]['vecinos'].append({'id': v, 'peso': dist})
                    grafo[v]['vecinos'].append({'id': u, 'peso': dist})
    return grafo

grafocompleto = construir_grafo(data)


def buscar_ruta_bfs(grafo, inicio_id, meta_id):
  
    # 1. Cola para BFS: guarda el (nodo_actual, camino_recorrido)
    cola = deque([(inicio_id, [inicio_id])])
    
    # 2. Conjunto de visitados para evitar ciclos infinitos
    visitados = {inicio_id}

    while cola:
        (nodo_actual, camino) = cola.popleft()

        # ¿Llegamos a la meta?
        if nodo_actual == meta_id:
            print("bfs exito")
            return camino

        # Explorar vecinos
        # VALIDACIÓN 3: Verificar que el nodo actual tenga la llave 'vecinos'
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                
                # VALIDACIÓN 4: Solo procesar el vecino si existe en el grafo
                # Esto evita el KeyError si el vecino está fuera del sector (Bounding Box)
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    
                    # Creamos el nuevo camino (forma eficiente de copiar lista)
                    nuevo_camino = camino + [vecino_id]
                    cola.append((vecino_id, nuevo_camino))

    print("No se encontró una ruta entre los nodos seleccionados.")
    return None



def buscar_ruta_dfs(grafo, inicio_id, meta_id):
  
    # 1. pila para BFS: guarda el (nodo_actual, camino_recorrido)
    stack = [(inicio_id, [inicio_id], 0)]
    
    # 2. Conjunto de visitados para evitar ciclos infinitos
    visitados = {inicio_id}

    while stack:
        (nodo_actual, camino, profundidad) = stack.pop()

        # ¿Llegamos a la meta?
        if nodo_actual == meta_id:
            print("dfs exito")
            return camino

        # Explorar vecinos
        # VALIDACIÓN 3: Verificar que el nodo actual tenga la llave 'vecinos'
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                
                # VALIDACIÓN 4: Solo procesar el vecino si existe en el grafo
                # Esto evita el KeyError si el vecino está fuera del sector (Bounding Box)
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    
                    # Creamos el nuevo camino (forma eficiente de copiar lista)
                    nuevo_camino = camino + [vecino_id]
                    nueva_profundidad = profundidad + 1
                    stack.append((vecino_id, nuevo_camino, nueva_profundidad))

    print("No se encontró una ruta entre los nodos seleccionados.")
    return None






def buscar_ruta_ldfs(grafo, inicio_id, meta_id, limite_profundidad=50):
    
    # 1. Pila: guarda (nodo_actual, camino_recorrido, profundidad_actual)
    stack = [(inicio_id, [inicio_id], 0)]
    
    # 2. Conjunto de visitados para evitar ciclos
    visitados = {inicio_id}

    while stack:
        (nodo_actual, camino, profundidad) = stack.pop()

        # ¿Llegamos a la meta?
        if nodo_actual == meta_id:
            print(f"✅ LDFS éxito — profundidad: {profundidad}")
            return camino

        # 🔑 DIFERENCIA CLAVE: si ya alcanzamos el límite, no expandir este nodo
        if profundidad >= limite_profundidad:
            continue

        # Explorar vecinos
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    nuevo_camino = camino + [vecino_id]
                    stack.append((vecino_id, nuevo_camino, profundidad + 1))

    print(f"❌ No se encontró ruta con límite de profundidad {limite_profundidad}.")
    return None


# ─── MAPA Y ESTADO (UNA SOLA VEZ) ───────────────────────────────────────────
m = Map(center=(24.805, -107.394), zoom=15)
m.add_control(FullScreenControl())

capa_interactiva = LayerGroup()
capa_ruta = LayerGroup()          # ← capa exclusiva para la polilínea
m.add_layer(capa_interactiva)
m.add_layer(capa_ruta)

puntos_seleccionados = []
nodos_id_ruta = {"inicio": None, "meta": None}

# ─── CALLBACKS ───────────────────────────────────────────────────────────────
def al_presionar_dfs(b):
    try:
        if not (nodos_id_ruta["inicio"] and nodos_id_ruta["meta"]):
            print("⚠️ Selecciona dos puntos en el mapa primero.")
            return

        inicio = nodos_id_ruta["inicio"]
        meta   = nodos_id_ruta["meta"]

        if inicio not in grafocompleto:
            print(f"❌ El nodo de inicio ({inicio}) no está en el grafo.")
            return
        if meta not in grafocompleto:
            print(f"❌ El nodo meta ({meta}) no está en el grafo.")
            return

        print(f"🔍 Buscando ruta DFS entre {inicio} y {meta}...")
        camino = buscar_ruta_ldfs(grafocompleto, inicio, meta,30)

        if camino:
            print(f"✅ Ruta encontrada con {len(camino)} nodos.")
            print(f"📍 Camino (IDs): {camino}")

            coordenadas_ruta = [
                [grafocompleto[nid]['lat'], grafocompleto[nid]['lon']]
                for nid in camino
                if nid in grafocompleto
            ]
            capa_ruta.clear_layers()
            linea = Polyline(
                locations=coordenadas_ruta,
                color="blue",
                weight=4,
                opacity=0.8
            )
            capa_ruta.add_layer(linea)
        else:
            print("❌ No se encontró ruta entre los nodos seleccionados.")

    except Exception as e:
        print(f"💥 ERROR: {type(e).__name__}: {e}")
        
def limpiar(b):
    puntos_seleccionados.clear()
    capa_interactiva.clear_layers()
    capa_ruta.clear_layers()          # ← también limpiar la ruta
    nodos_id_ruta["inicio"] = None
    nodos_id_ruta["meta"]   = None
    print("🧹 Mapa limpio.")

def manejar_clic(**kwargs):
    if kwargs.get('type') == 'click':
        latlon = kwargs.get('coordinates')
        if len(puntos_seleccionados) < 2:
            puntos_seleccionados.append(latlon)
            nodo_id, _ = obtener_id_mas_cercano(latlon[0], latlon[1], nodos_coords)

            if len(puntos_seleccionados) == 1:
                tipo  = "INICIO"
                nodos_id_ruta["inicio"] = nodo_id
            else:
                tipo  = "META"
                nodos_id_ruta["meta"] = nodo_id

            marcador = Marker(location=latlon, draggable=False, title=f"{tipo}: {nodo_id}")
            capa_interactiva.add_layer(marcador)
            print(f"✅ {tipo} capturado. ID Nodo OSM: {nodo_id}")

            if len(puntos_seleccionados) == 2:
                print(f"\n🚀 LISTO — Origen: {nodos_id_ruta['inicio']}  |  Destino: {nodos_id_ruta['meta']}")

m.on_interaction(manejar_clic)

# ─── BOTONES ─────────────────────────────────────────────────────────────────
btn_dfs   = widgets.Button(description="Ejecutar DFS",  button_style='primary')
btn_reset = widgets.Button(description="Limpiar",        button_style='danger')
btn_dfs.on_click(al_presionar_dfs)
btn_reset.on_click(limpiar)

display(m)
display(widgets.HBox([btn_dfs, btn_reset]))
# %%
