from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import requests
import folium
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# Fungsi untuk mengambil rute menggunakan OSRM API
def get_route(origin, destination):
    base_url = "http://router.project-osrm.org/route/v1/driving/"
    url = f"{base_url}{origin};{destination}?overview=false"

    response = requests.get(url)

    if response.status_code == 200:
        route_info = response.json()
        distance = route_info['routes'][0]['distance']  # Dalam meter
        return distance
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return float('inf')  # Mengembalikan nilai tak terhingga jika ada kesalahan

# Fungsi untuk membuat data model
def create_data_model():
    data = {}
    data['locations'] = [
        [52.5200, 13.4050],  # Depot (lokasi awal truk) di Berlin
        [52.5250, 13.4050],  # Lokasi tempat sampah 1
        [52.5250, 13.4150],  # Lokasi tempat sampah 2
        [52.5300, 13.4250],  # Lokasi tempat sampah 3
        [52.5300, 13.4350],  # Lokasi tempat sampah 4
        [52.5350, 13.4450],  # Lokasi tempat sampah 5
        [52.5400, 13.4550],  # Lokasi tempat sampah 6
        [52.5450, 13.4650],  # Lokasi tempat sampah 7
    ]
    
    data['demands'] = [0, 1, 1, 2, 4, 2, 4, 8]  # Depot punya demand 0
    data['vehicle_capacities'] = [25]  # Kapasitas truk
    data['num_vehicles'] = 1
    data['depot'] = 0

    return data

# Fungsi untuk membuat matriks jarak menggunakan OSRM API
def create_distance_matrix(data):
    distances = {}
    for from_counter, from_node in enumerate(data['locations']):
        distances[from_counter] = {}
        for to_counter, to_node in enumerate(data['locations']):
            if from_counter == to_counter:
                distances[from_counter][to_counter] = 0
            else:
                origin = f"{from_node[1]},{from_node[0]}"  # OSRM expects [lng,lat]
                destination = f"{to_node[1]},{to_node[0]}"  # OSRM expects [lng,lat]
                distance = get_route(origin, destination)
                distances[from_counter][to_counter] = distance
    return distances

# Fungsi untuk mendapatkan koordinat rute dari OSRM API
def get_route_coordinates(origin, destination):
    base_url = "http://router.project-osrm.org/route/v1/driving/"
    url = f"{base_url}{origin};{destination}?overview=full&geometries=geojson"

    response = requests.get(url)

    if response.status_code == 200:
        route_info = response.json()
        if 'routes' in route_info and len(route_info['routes']) > 0:
            coordinates = route_info['routes'][0]['geometry']['coordinates']
            # Format koordinat dari [lng, lat] ke [lat, lng] agar sesuai dengan Folium
            route_coordinates = [[coord[1], coord[0]] for coord in coordinates]
            return route_coordinates
        else:
            print(f"No routes found for origin {origin} and destination {destination}.")
            return []
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return []

# Fungsi visualisasi rute di peta menggunakan Folium
def visualize_route(locations, route, total_distance):
    depot_location = locations[0]
    m = folium.Map(location=depot_location, zoom_start=14)

    # Tambahkan marker untuk depot dan setiap tempat sampah
    for i, location in enumerate(locations):
        folium.Marker(location=location, popup=f'Lokasi {i}').add_to(m)

    # Mendapatkan koordinat rute dari OSRM API
    route_coordinates = []
    for i in range(len(route) - 1):
        origin = f"{locations[route[i]][1]},{locations[route[i]][0]}"  # OSRM expects [lng,lat]
        destination = f"{locations[route[i + 1]][1]},{locations[route[i + 1]][0]}"  # OSRM expects [lng,lat]
        temp_coordinates = get_route_coordinates(origin, destination)
        if temp_coordinates:
            route_coordinates.extend(temp_coordinates)

    # Tambahkan rute ke peta jika ada koordinat yang valid
    if route_coordinates:
        folium.PolyLine(route_coordinates, color='blue', weight=2.5, opacity=1).add_to(m)

    # Tambahkan informasi jarak ke peta
    folium.Marker(location=depot_location, 
                  popup=f'Total distance: {total_distance/1000} km',
                  icon=folium.Icon(color='green')).add_to(m)

    # Simpan peta ke file HTML
    m.save('route_map.html')
    print("Peta rute disimpan sebagai 'route_map.html'.")

# Fungsi untuk melatih model prediksi volume sampah
def train_volume_prediction_model():
    # Contoh data historis
    data = {
        'hari': [1, 2, 3, 4, 5],
        'jumlah_pengunjung': [100, 150, 120, 200, 180],
        'volume_sampah': [10, 15, 12, 25, 20]  # Volume sampah dalam unit
    }

    df = pd.DataFrame(data)

    # Fitur dan target
    X = df[['hari', 'jumlah_pengunjung']]
    y = df['volume_sampah']

    # Pembagian data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Model Random Forest
    model = RandomForestRegressor()
    model.fit(X_train, y_train)

    return model

# Memecahkan masalah VRP
def main():
    # Membuat data model
    data = create_data_model()

    # Membuat matriks jarak menggunakan OSRM
    distance_matrix = create_distance_matrix(data)

    # Membuat manajer index untuk routing
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), data['num_vehicles'], data['depot'])

    # Membuat model routing
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Set biaya (cost) ke jarak
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Menambahkan constraint kapasitas kendaraan
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # Tidak ada slack
        data['vehicle_capacities'],  # Kapasitas kendaraan
        True,  # Apakah kapasitas dimulai dari nol
        'Capacity'
    )

    # Setting parameter pencarian
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    # Memecahkan masalah
    solution = routing.SolveWithParameters(search_parameters)

    # Visualisasi hasil
    if solution:
        print('Objective: {}'.format(solution.ObjectiveValue()))
        total_distance = 0
        total_load = 0
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            plan_output = 'Route for vehicle {}:\n'.format(vehicle_id)
            route_distance = 0
            route_load = 0
            route = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += data['demands'][node_index]
                plan_output += ' {0} Load({1}) -> '.format(node_index, route_load)
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
                route.append(node_index)
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            plan_output += ' {0} Load({1})\n'.format(node_index, route_load)
            plan_output += 'Distance of the route: {}m\n'.format(route_distance)
            plan_output += 'Load of the route: {}\n'.format(route_load)
            print(plan_output)
            total_distance += route_distance
            total_load += route_load

            # Visualisasi rute menggunakan Folium
            visualize_route(data['locations'], route, total_distance)

        print('Total distance of all routes: {}m'.format(total_distance))
        print('Total load of all routes: {}'.format(total_load))
    else:
        print('No solution found!')

if __name__ == '__main__':
    main()


