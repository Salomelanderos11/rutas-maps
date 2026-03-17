#%%
# importamos las librerias necesarias para el proyecto
# requests: para hacer peticiones a la api de openstreetmap
# math: para calculos matematicos como seno coseno y raiz cuadrada
# ipyleaflet: para mostrar el mapa interactivo en jupyter
# ipywidgets: para crear los botones y el panel de salida
# heapq: para la cola de prioridad que usa a estrella
# deque: para la cola de bfs y la lista tabu
# random: para el numero aleatorio que usa recocido simulado
import requests
import math
from ipyleaflet import Map, Marker, FullScreenControl, LayerGroup, Polyline
import ipywidgets as widgets
from IPython.display import display
import heapq
from collections import deque  
import random

# definimos el area geografica que vamos a trabajar
# son las coordenadas de un sector de culiacan sinaloa
# sur y norte definen el rango de latitud
# oeste y este definen el rango de longitud
sur = 24.796998
oeste = -107.401461
norte = 24.812974
este = -107.387524

# esta funcion se conecta a overpass api que es el servicio de openstreetmap
# le mandamos las coordenadas del sector y nos regresa todos los nodos y calles
# que hay dentro de esa area geografica
# solo pedimos calles primarias secundarias terciarias y residenciales
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

# llamamos a la funcion para obtener los datos del sector
data = extraer_nodos_sector(sur, oeste, norte, este)

# de todos los datos que regreso la api separamos solo los nodos
# un nodo es un punto geografico con latitud y longitud
# guardamos cada nodo en un diccionario usando su id como llave
# ejemplo: {123456: (24.80, -107.39), 789012: (24.81, -107.40)}
nodos_coords = {}
for e in data:
    if e['type'] == 'node':
        nodos_coords[e['id']] = (e['lat'], e['lon'])

# esta funcion calcula la distancia real en metros entre dos puntos geograficos
# usamos la formula de haversine porque la tierra es redonda
# si usaramos una formula normal de distancia euclidiana el resultado seria incorrecto
# porque las coordenadas geograficas no forman una cuadricula plana
# p1 y p2 son tuplas con (latitud longitud)
def calcular_distancia(p1, p2):
    lat1, lon1 = p1
    lat2, lon2 = p2
    # radio de la tierra en metros
    radio_tierra = 6371000
    # convertimos los grados a radianes porque math.sin y math.cos usan radianes
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    # formula de haversine
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    # multiplicamos por el radio para obtener metros
    return radio_tierra * c

# cuando el usuario da clic en el mapa necesitamos saber a que nodo del grafo
# corresponde ese clic porque el clic puede caer en medio de la calle
# esta funcion recorre todos los nodos y regresa el id del que esta mas cerca
# del punto donde dio clic el usuario
def obtener_id_mas_cercano(lat_clic, lon_clic, nodos_dict):
    distancia_minima = float('inf')
    id_mas_cercano = None
    for nodo_id, coords in nodos_dict.items():
        dist = calcular_distancia((lat_clic, lon_clic), coords)
        if dist < distancia_minima:
            distancia_minima = dist
            id_mas_cercano = nodo_id
    return id_mas_cercano, distancia_minima

# esta funcion convierte los datos crudos de openstreetmap en un grafo
# un grafo es una estructura de datos donde cada nodo tiene una lista de vecinos
# cada vecino tiene un id y un peso que es la distancia en metros hasta ese vecino
# el grafo se ve asi:
# {
#   123456: {lat: 24.80, lon: -107.39, vecinos: [{id: 789012, peso: 45.3}, ...]},
#   789012: {lat: 24.81, lon: -107.40, vecinos: [{id: 123456, peso: 45.3}, ...]},
# }
# las calles son bidireccionales por eso cada conexion se agrega en ambos sentidos
def construir_grafo(data):
    grafo = {}
    nodos_c = {e['id']: (e['lat'], e['lon']) for e in data if e['type'] == 'node'}
    for ele in data:
        if ele['type'] == 'way':
            nodos_en_calle = ele.get('nodes', [])
            # conecta cada par de nodos consecutivos en la calle
            for i in range(len(nodos_en_calle) - 1):
                u = nodos_en_calle[i]
                v = nodos_en_calle[i+1]
                if u in nodos_c and v in nodos_c:
                    dist = calcular_distancia(nodos_c[u], nodos_c[v])
                    if u not in grafo:
                        grafo[u] = {'lat': nodos_c[u][0], 'lon': nodos_c[u][1], 'vecinos': []}
                    if v not in grafo:
                        grafo[v] = {'lat': nodos_c[v][0], 'lon': nodos_c[v][1], 'vecinos': []}
                    # conexion en ambas direcciones porque las calles son bidireccionales
                    grafo[u]['vecinos'].append({'id': v, 'peso': dist})
                    grafo[v]['vecinos'].append({'id': u, 'peso': dist})
    return grafo

# construimos el grafo con todos los datos que descargamos
grafocompleto = construir_grafo(data)

# la heuristica es una estimacion de que tan lejos estamos de la meta
# la usan los algoritmos informados (voraz a estrella tabu recocido) para
# decidir hacia que nodo moverse primero
# usamos la distancia en linea recta entre el nodo actual y la meta
# es una heuristica admisible porque nunca sobreestima la distancia real
def heuristica(grafo, nodo_id, meta_id):
    lat_actual = grafo[nodo_id]['lat']
    lon_actual = grafo[nodo_id]['lon']
    lat_meta   = grafo[meta_id]['lat']
    lon_meta   = grafo[meta_id]['lon']
    return calcular_distancia((lat_actual, lon_actual), (lat_meta, lon_meta))

# algoritmo bfs (busqueda por amplitud)
# explora todos los nodos nivel por nivel usando una cola (fifo)
# garantiza encontrar el camino con menos nodos intermedios
# no garantiza el camino mas corto en metros
# visitados evita que el algoritmo entre en ciclos infinitos
def buscar_ruta_bfs(grafo, inicio_id, meta_id):
    # la cola guarda tuplas de (nodo actual, camino recorrido hasta ese nodo)
    cola = deque([(inicio_id, [inicio_id])])
    visitados = {inicio_id}
    paso = 0
    while cola:
        # popleft saca el primer elemento de la cola (el mas antiguo)
        nodo_actual, camino = cola.popleft()
        paso = paso + 1
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | nodos en camino: " + str(len(camino)))

        if nodo_actual == meta_id:
            print("BFS exito, nodos: " + str(len(camino)))
            return camino
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    nuevo_camino = camino + [vecino_id]
                    cola.append((vecino_id, nuevo_camino))
    print("BFS: No se encontro ruta.")
    return None

# algoritmo dfs (busqueda por profundidad)
# explora tan profundo como puede antes de retroceder usando una pila (lifo)
# no garantiza el camino con menos nodos ni el mas corto en metros
# puede encontrar una solucion rapido si tiene suerte con la direccion
def buscar_ruta_dfs(grafo, inicio_id, meta_id):
    # la pila guarda tuplas de (nodo actual, camino recorrido, profundidad actual)
    stack = [(inicio_id, [inicio_id], 0)]
    visitados = {inicio_id}
    paso = 0
    while stack:
        # pop saca el ultimo elemento de la pila (el mas reciente)
        nodo_actual, camino, profundidad = stack.pop()
        paso = paso + 1
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | profundidad: " + str(profundidad) + " | nodos en camino: " + str(len(camino)))

        if nodo_actual == meta_id:
            print("DFS exito, nodos: " + str(len(camino)))
            return camino
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    nuevo_camino = camino + [vecino_id]
                    nueva_profundidad = profundidad + 1
                    stack.append((vecino_id, nuevo_camino, nueva_profundidad))
    print("DFS: No se encontro ruta.")
    return None

# algoritmo ldfs (dfs con limite de profundidad)
# igual que dfs pero deja de explorar una rama cuando llega al limite
# esto evita que el algoritmo se vaya demasiado lejos en una direccion equivocada
# si el limite es muy bajo puede no encontrar la ruta aunque exista
def buscar_ruta_ldfs(grafo, inicio_id, meta_id, limite_profundidad=50):
    stack = [(inicio_id, [inicio_id], 0)]
    visitados = {inicio_id}
    paso = 0
    while stack:
        nodo_actual, camino, profundidad = stack.pop()
        paso = paso + 1
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | profundidad: " + str(profundidad) + "/" + str(limite_profundidad))

        if nodo_actual == meta_id:
            print("LDFS exito, nodos: " + str(len(camino)) + ", profundidad: " + str(profundidad))
            return camino
        # si llego al limite no expande este nodo y pasa al siguiente en la pila
        if profundidad >= limite_profundidad:
            print("paso " + str(paso) + " - limite alcanzado en nodo " + str(nodo_actual) + " no se expande")
            continue
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    nuevo_camino = camino + [vecino_id]
                    stack.append((vecino_id, nuevo_camino, profundidad + 1))
    print("LDFS: No se encontro ruta con limite " + str(limite_profundidad))
    return None

# algoritmo voraz (greedy best first search)
# es un algoritmo informado que usa la heuristica para decidir a donde ir
# siempre elige el vecino que parece estar mas cerca de la meta
# es rapido pero no garantiza la ruta optima porque puede tomar atajos equivocados
# la diferencia con bfs y dfs es que usa la heuristica para ordenar los candidatos
def buscar_ruta_voraz(grafo, inicio_id, meta_id):
    stack = [(inicio_id, [inicio_id])]
    visitados = {inicio_id}
    paso = 0
    while stack:
        nodo_actual, camino = stack.pop()
        paso = paso + 1
        h = heuristica(grafo, nodo_actual, meta_id)
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | distancia a meta: " + str(round(h, 1)) + "m")

        if nodo_actual == meta_id:
            print("Voraz exito, nodos: " + str(len(camino)))
            return camino
        if 'vecinos' in grafo[nodo_actual]:
            candidatos = []
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    h = heuristica(grafo, vecino_id, meta_id)
                    candidatos.append((vecino_id, camino + [vecino_id], h))
            # ordena descendente porque stack.pop() saca el ultimo
            # entonces el mejor (menor h) queda hasta el final de la lista
            candidatos.sort(key=lambda x: x[2], reverse=True)
            for vecino_id, nuevo_camino, h in candidatos:
                stack.append((vecino_id, nuevo_camino))
    print("Voraz: No se encontro ruta.")
    return None

# algoritmo a estrella (a*)
# es el algoritmo mas completo de todos los que implementamos
# combina el costo real del camino recorrido (g) con la heuristica (h)
# f = g + h donde f es el valor total que determina que nodo explorar primero
# a diferencia del voraz que solo usa h este tambien considera el costo real
# garantiza encontrar la ruta mas corta en metros si la heuristica es admisible
# usa un heap (cola de prioridad) para siempre sacar el nodo con menor f
def buscar_ruta_a_star(grafo, inicio_id, meta_id):
    # el open set guarda tuplas de (f score, g score, nodo actual, camino)
    # f = g + h  donde g es la distancia recorrida y h es la distancia estimada
    open_set = [(heuristica(grafo, inicio_id, meta_id), 0, inicio_id, [inicio_id])]
    # mejor_g guarda la menor distancia conocida para llegar a cada nodo
    mejor_g = {inicio_id: 0}
    nodos_explorados = 0
    while open_set:
        # heappop saca el nodo con menor f score (el mas prometedor)
        f_score, g_score, nodo_actual, camino = heapq.heappop(open_set)
        nodos_explorados = nodos_explorados + 1
        print("paso " + str(nodos_explorados) + " - visitando nodo " + str(nodo_actual) + " | g: " + str(round(g_score, 1)) + "m | f: " + str(round(f_score, 1)) + "m")

        if nodo_actual == meta_id:
            print("A* exito, nodos: " + str(len(camino)) + ", explorados: " + str(nodos_explorados) + ", distancia: " + str(round(g_score, 1)) + "m")
            return camino
        # puede pasar que un nodo entre al heap varias veces con diferentes g scores
        # si ya procesamos este nodo con un g score menor lo ignoramos
        if g_score > mejor_g.get(nodo_actual, float('inf')):
            print("  nodo " + str(nodo_actual) + " ignorado porque ya existe un camino mejor")
            continue
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                peso = vecino_info['peso']
                if vecino_id not in grafo:
                    continue
                nuevo_g = g_score + peso
                # solo agrega al open set si encontramos un camino mas corto a este vecino
                if nuevo_g < mejor_g.get(vecino_id, float('inf')):
                    mejor_g[vecino_id] = nuevo_g
                    nuevo_f = nuevo_g + heuristica(grafo, vecino_id, meta_id)
                    nuevo_camino = camino + [vecino_id]
                    heapq.heappush(open_set, (nuevo_f, nuevo_g, vecino_id, nuevo_camino))
                    print("  agregando vecino " + str(vecino_id) + " con f: " + str(round(nuevo_f, 1)) + "m")
    print("A*: No se encontro ruta. Explorados: " + str(nodos_explorados))
    return None

# algoritmo de busqueda tabu
# es una metaheuristica que mejora al voraz agregando memoria
# la lista tabu guarda los ultimos nodos visitados para evitar revisitarlos
# esto le permite escapar de ciclos aunque no garantiza la solucion optima
# tabu_size controla cuantos nodos recuerda si es muy grande puede atascarse
# si es muy pequeno puede volver a visitar nodos recientes
def buscar_ruta_tabu(grafo, inicio_id, meta_id, tabu_size=20, max_iteraciones=10000):
    current = inicio_id
    camino = [inicio_id]
    # usamos deque para poder eliminar el elemento mas antiguo facilmente con popleft
    tabu_list = deque()
    # usamos set para verificar rapido si un nodo esta en tabu (O(1) vs O(n) de lista)
    tabu_set = set()
    iteraciones = 0
    while current != meta_id:
        if iteraciones >= max_iteraciones:
            print("Tabu: Limite de iteraciones alcanzado " + str(max_iteraciones))
            return None
        iteraciones = iteraciones + 1
        h = heuristica(grafo, current, meta_id)
        print("iteracion " + str(iteraciones) + " - nodo actual " + str(current) + " | distancia a meta: " + str(round(h, 1)) + "m | tabu size: " + str(len(tabu_list)))

        # solo considera vecinos que no esten en la lista tabu
        candidatos = []
        if 'vecinos' in grafo[current]:
            for vecino_info in grafo[current]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in tabu_set:
                    h = heuristica(grafo, vecino_id, meta_id)
                    candidatos.append((vecino_id, h))
        if not candidatos:
            print("Tabu: Sin movimientos disponibles en iteracion " + str(iteraciones))
            return None
        # elige el mejor candidato segun la heuristica igual que el voraz
        candidatos.sort(key=lambda x: x[1])
        siguiente_id = candidatos[0][0]
        print("  moviendose a nodo " + str(siguiente_id) + " | candidatos disponibles: " + str(len(candidatos)))

        # agrega el nodo actual a tabu antes de moverse al siguiente
        tabu_list.append(current)
        tabu_set.add(current)
        # si la lista supera el limite elimina el nodo mas antiguo
        if len(tabu_list) > tabu_size:
            nodo_viejo = tabu_list.popleft()
            tabu_set.discard(nodo_viejo)
            print("  nodo " + str(nodo_viejo) + " eliminado de la lista tabu")
        current = siguiente_id
        camino.append(current)
    print("Tabu exito, nodos: " + str(len(camino)) + ", iteraciones: " + str(iteraciones))
    return camino

# algoritmo de recocido simulado (simulated annealing)
# es una metaheuristica inspirada en el proceso de enfriamiento de metales
# al igual que tabu mejora al voraz pero de manera diferente
# en vez de usar memoria acepta movimientos malos con cierta probabilidad
# al inicio con temperatura alta acepta casi cualquier movimiento (explora mucho)
# conforme la temperatura baja se vuelve mas selectivo (explora menos)
# esto le permite escapar de minimos locales que atraparian a un voraz normal
# delta es la diferencia entre la heuristica del siguiente nodo y la del actual
# si delta es negativo el movimiento mejora y siempre se acepta
# si delta es positivo el movimiento empeora y se acepta con probabilidad e^(-delta/temp)
def buscar_ruta_recocido(grafo, inicio_id, meta_id, temp_inicial=1000, tasa_enfriamiento=0.995, max_iteraciones=10000):
    current = inicio_id
    camino = [inicio_id]
    temp = temp_inicial
    iteraciones = 0
    while current != meta_id and temp > 0.1:
        if iteraciones >= max_iteraciones:
            print("Recocido: Limite de iteraciones alcanzado " + str(max_iteraciones))
            return None
        iteraciones = iteraciones + 1
        print("iteracion " + str(iteraciones) + " - nodo actual " + str(current) + " | temperatura: " + str(round(temp, 2)))

        candidatos = []
        if 'vecinos' in grafo[current]:
            for vecino_info in grafo[current]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo:
                    h = heuristica(grafo, vecino_id, meta_id)
                    candidatos.append((vecino_id, h))
        if not candidatos:
            print("Recocido: Sin movimientos disponibles.")
            return None
        candidatos.sort(key=lambda x: x[1])
        siguiente_id = candidatos[0][0]
        h_siguiente = candidatos[0][1]
        h_actual = heuristica(grafo, current, meta_id)
        # delta positivo significa que el movimiento nos aleja de la meta
        delta = h_siguiente - h_actual
        # acepta el movimiento si mejora o con probabilidad e^(-delta/temp)
        if delta < 0 or random.random() < math.exp(-delta / temp):
            print("  movimiento aceptado hacia nodo " + str(siguiente_id) + " | delta: " + str(round(delta, 1)))
            current = siguiente_id
            camino.append(current)
        else:
            print("  movimiento rechazado hacia nodo " + str(siguiente_id) + " | delta: " + str(round(delta, 1)))
        # multiplicamos la temperatura por la tasa de enfriamiento en cada iteracion
        temp = temp * tasa_enfriamiento
    if current == meta_id:
        print("Recocido exito, nodos: " + str(len(camino)) + ", iteraciones: " + str(iteraciones))
        return camino
    print("Recocido: Temperatura agotada, no se llego a la meta.")
    return None

# creamos el mapa centrado en el sector de culiacan
m = Map(center=(24.805, -107.394), zoom=15)
m.add_control(FullScreenControl())

# capa_interactiva: guarda los marcadores de inicio y meta que pone el usuario
# capa_ruta: guarda la linea azul del camino encontrado
# las capas nos permiten limpiar solo lo que necesitamos sin borrar todo el mapa
capa_interactiva = LayerGroup()
capa_ruta = LayerGroup()
m.add_layer(capa_interactiva)
m.add_layer(capa_ruta)

# puntos_seleccionados: lista con las coordenadas de los clics del usuario
# nodos_id_ruta: diccionario con los ids de los nodos de inicio y meta
# out: widget donde se muestran todos los prints de los algoritmos
# ejecutando: bandera para evitar que el usuario ejecute dos algoritmos al mismo tiempo
puntos_seleccionados = []
nodos_id_ruta = {"inicio": None, "meta": None}
out = widgets.Output()
ejecutando = False

# recibe el camino como lista de ids de nodos
# convierte esos ids a coordenadas y dibuja una linea en el mapa
def dibujar_ruta(camino):
    if camino != None:
        print("Camino (IDs): " + str(camino))
        coords = []
        for nid in camino:
            if nid in grafocompleto:
                lat = grafocompleto[nid]['lat']
                lon = grafocompleto[nid]['lon']
                coords.append([lat, lon])
        capa_ruta.clear_layers()
        linea = Polyline(locations=coords, color="blue", weight=4, opacity=0.8)
        capa_ruta.add_layer(linea)
    else:
        print("No se encontro ruta.")

# antes de ejecutar cualquier algoritmo verificamos que el usuario
# haya seleccionado los dos puntos y que ambos existan en el grafo
# si algo falla regresa None None y el callback cancela la ejecucion
def validar_puntos():
    if nodos_id_ruta["inicio"] == None or nodos_id_ruta["meta"] == None:
        print("Selecciona dos puntos en el mapa primero.")
        return None, None
    inicio = nodos_id_ruta["inicio"]
    meta = nodos_id_ruta["meta"]
    if inicio not in grafocompleto:
        print("El nodo de inicio no esta en el grafo.")
        return None, None
    if meta not in grafocompleto:
        print("El nodo meta no esta en el grafo.")
        return None, None
    return inicio, meta

# ejecuta bfs cuando el usuario presiona el boton
# ejecutando evita que se ejecuten dos algoritmos al mismo tiempo
def on_bfs(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando BFS...")
            camino = buscar_ruta_bfs(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta dfs cuando el usuario presiona el boton
def on_dfs(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando DFS...")
            camino = buscar_ruta_dfs(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta ldfs cuando el usuario presiona el boton
def on_ldfs(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando LDFS...")
            camino = buscar_ruta_ldfs(grafocompleto, inicio, meta, limite_profundidad=50)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta voraz cuando el usuario presiona el boton
def on_voraz(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando Voraz...")
            camino = buscar_ruta_voraz(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta a star cuando el usuario presiona el boton
def on_astar(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando A*...")
            camino = buscar_ruta_a_star(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta tabu cuando el usuario presiona el boton
def on_tabu(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando Tabu...")
            camino = buscar_ruta_tabu(grafocompleto, inicio, meta, tabu_size=20, max_iteraciones=10000)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta recocido simulado cuando el usuario presiona el boton
def on_recocido(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando Recocido Simulado...")
            camino = buscar_ruta_recocido(grafocompleto, inicio, meta, temp_inicial=1000, tasa_enfriamiento=0.995)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# limpia el mapa y reinicia todas las variables de estado
# borra los marcadores de inicio y meta y la linea de la ruta
def limpiar(b):
    puntos_seleccionados.clear()
    capa_interactiva.clear_layers()
    capa_ruta.clear_layers()
    nodos_id_ruta["inicio"] = None
    nodos_id_ruta["meta"] = None
    out.clear_output(wait=True)
    with out:
        print("Mapa limpio.")

# esta funcion se ejecuta cada vez que el usuario da clic en el mapa
# el primer clic define el nodo de inicio y el segundo define la meta
# busca el nodo del grafo mas cercano al punto donde dio clic
# y pone un marcador en el mapa para que el usuario vea donde quedo
def manejar_clic(**kwargs):
    if kwargs.get('type') == 'click':
        latlon = kwargs.get('coordinates')
        if len(puntos_seleccionados) < 2:
            puntos_seleccionados.append(latlon)
            nodo_id, distancia = obtener_id_mas_cercano(latlon[0], latlon[1], nodos_coords)
            if len(puntos_seleccionados) == 1:
                tipo = "INICIO"
                nodos_id_ruta["inicio"] = nodo_id
            else:
                tipo = "META"
                nodos_id_ruta["meta"] = nodo_id
            marcador = Marker(location=latlon, draggable=False, title=tipo + ": " + str(nodo_id))
            capa_interactiva.add_layer(marcador)
            print(tipo + " capturado. ID Nodo OSM: " + str(nodo_id))
            if len(puntos_seleccionados) == 2:
                print("LISTO - Origen: " + str(nodos_id_ruta['inicio']) + " | Destino: " + str(nodos_id_ruta['meta']))

# remove=True evita que se acumulen listeners si se re-ejecuta la celda
m.on_interaction(manejar_clic, remove=True)
m.on_interaction(manejar_clic)

# %%
# celda 2 - se puede re-ejecutar sin problemas porque solo crea botones nuevos
out.clear_output()

btn_bfs      = widgets.Button(description="BFS",      button_style='primary')
btn_dfs      = widgets.Button(description="DFS",      button_style='primary')
btn_ldfs     = widgets.Button(description="LDFS",     button_style='primary')
btn_voraz    = widgets.Button(description="Voraz",    button_style='info')
btn_astar    = widgets.Button(description="A*",       button_style='info')
btn_tabu     = widgets.Button(description="Tabu",     button_style='warning')
btn_recocido = widgets.Button(description="Recocido", button_style='warning')
btn_reset    = widgets.Button(description="Limpiar",  button_style='danger')

btn_bfs.on_click(on_bfs)
btn_dfs.on_click(on_dfs)
btn_ldfs.on_click(on_ldfs)
btn_voraz.on_click(on_voraz)
btn_astar.on_click(on_astar)
btn_tabu.on_click(on_tabu)
btn_recocido.on_click(on_recocido)
btn_reset.on_click(limpiar)

display(m)
display(widgets.HBox([btn_bfs, btn_dfs, btn_ldfs, btn_voraz]))
display(widgets.HBox([btn_astar, btn_tabu, btn_recocido, btn_reset]))
display(out)
# %%