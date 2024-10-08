from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import requests
import folium
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from datetime import datetime
import random

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

# Fungsi untuk menghasilkan volume sampah berdasarkan hari
def get_daily_demands(day):
    """
    Fungsi ini menghasilkan volume sampah berdasarkan hari dalam seminggu.
    Hari Senin (day=0) lebih penuh, dan akhir pekan (day=5, 6) lebih ringan.
    
    day: Integer yang merepresentasikan hari dalam seminggu (0: Senin, 1: Selasa, ..., 6: Minggu)
    
    Return:
    - List demands yang berisi volume sampah per lokasi.
    """
    if day == 0:  # Senin, volume sampah lebih tinggi
        demands = [random.randint(5, 10) for _ in range(7)]  # Volume sampah lebih banyak
    elif day == 5 or day == 6:  # Sabtu dan Minggu, volume sampah lebih rendah
        demands = [random.randint(1, 3) for _ in range(7)]  # Volume sampah lebih sedikit
    else:  # Hari biasa, volume sampah sedang
        demands = [random.randint(2, 5) for _ in range(7)]
    
    demands.insert(0, 0)  # Tambahkan 0 untuk depot (lokasi awal truk)
    return demands

# Fungsi untuk membuat data model
def create_data_model(current_day):
    """
    Fungsi untuk membuat data model untuk routing. 
    Sekarang menambahkan variasi volume sampah berdasarkan hari.
    
    current_day: Hari saat ini (0: Senin, 1: Selasa, dst.)
    """
    data = {}
    data['locations'] = [
        [-6.2088, 106.8456],  # Depot (lokasi awal truk) di Jakarta
        [-6.2154, 106.8424],  # Lokasi tempat sampah 1
        [-6.2202, 106.8500],  # Lokasi tempat sampah 2
        [-6.2255, 106.8433],  # Lokasi tempat sampah 3
        [-6.2308, 106.8477],  # Lokasi tempat sampah 4
        [-6.2356, 106.8508],  # Lokasi tempat sampah 5
        [-6.2402, 106.8430],  # Lokasi tempat sampah 6
        [-6.2451, 106.8462],  # Lokasi tempat sampah 7
    ]

    # Panggil get_daily_demands untuk mendapatkan demands berdasarkan hari
    data['demands'] = get_daily_demands(current_day)
    
    data['vehicle_capacities'] = [25]  # Kapasitas truk
    data['num_vehicles'] = 1
    data['depot'] = 0

    # Menambahkan informasi jadwal (hari) untuk setiap lokasi
    data['pickup_schedule'] = [0, 1, 2, 0, 1, 2, 0, 1]  # Jadwal pengambilan sampah per lokasi
    
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
                origin = f"{from_node[1]},{from_node[0]}"  # OSRM expects [lng, lat]
                destination = f"{to_node[1]},{to_node[0]}"  # OSRM expects [lng, lat]
                
                # Handle cases where the OSRM API fails or returns invalid routes
                distance = get_route(origin, destination)
                if distance == float('inf'):  # When route is invalid
                    print(f"Warning: No valid route found from {origin} to {destination}")
                distances[from_counter][to_counter] = distance if distance != float('inf') else 1e6  # Penalize with large distance if invalid
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
        origin = f"{locations[route[i]][1]},{locations[route[i]][0]}"  
        destination = f"{locations[route[i + 1]][1]},{locations[route[i + 1]][0]}"  
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

# Fungsi untuk memfilter lokasi berdasarkan hari saat ini
def filter_locations_by_day(data, current_day):
    """
    Memfilter lokasi yang harus diambil sampahnya berdasarkan jadwal dan hari saat ini.
    
    current_day: Hari saat ini (0: Senin, 1: Selasa, dst.)
    """
    filtered_locations = []
    filtered_demands = []
    filtered_schedule = []
    
    for i in range(len(data['locations'])):
        # Jika jadwal adalah setiap hari (0) atau jadwal sesuai dengan current_day
        if data['pickup_schedule'][i] == 0 or current_day % data['pickup_schedule'][i] == 0:
            filtered_locations.append(data['locations'][i])
            filtered_demands.append(data['demands'][i])
            filtered_schedule.append(data['pickup_schedule'][i])
    
    # Mengupdate data model dengan lokasi dan permintaan yang difilter
    data['locations'] = filtered_locations
    data['demands'] = filtered_demands
    data['pickup_schedule'] = filtered_schedule

    return data

# Fungsi untuk menghitung rute berdasarkan data yang ada
def calculate_route(data):
    """
    Fungsi ini menghitung rute optimal berdasarkan data lokasi dan kapasitas kendaraan.

    Parameter:
    - data: dict berisi data lokasi, permintaan, kapasitas kendaraan, dll.

    Return:
    - route: urutan indeks lokasi yang dilalui
    - total_distance: total jarak yang ditempuh
    """
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
        data['vehicle_capacities'],  
        True,  
        'Capacity'
    )

    # Setting parameter pencarian
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    # Memecahkan masalah
    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        total_distance = 0
        route = []
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            route_distance = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route.append(node_index)
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            total_distance += route_distance

        return route, total_distance
    else:
        return None, 0  # Tidak ditemukan solusi

# Memecahkan masalah VRP dengan rencana pengambilan berkala
def main():
    # Tentukan hari saat ini (0: Senin, 1: Selasa, ..., 6: Minggu)
    current_day = datetime.now().weekday()

    # Membuat data model berdasarkan hari saat ini
    data = create_data_model(current_day)

    # Filter lokasi yang harus diambil berdasarkan jadwal dan hari saat ini
    data = filter_locations_by_day(data, current_day)

    # Pastikan ada lokasi yang harus diambil
    if len(data['locations']) <= 1:
        print(f"Tidak ada lokasi yang perlu diambil sampahnya pada hari ini (Day {current_day}).")
        return

    # Menghitung rute
    route, total_distance = calculate_route(data)

    if route:
        print('Rute ditemukan.')
        print(f"Total distance: {total_distance} m")

        # Visualisasi rute menggunakan Folium
        visualize_route(data['locations'], route, total_distance)
    else:
        print('No solution found!')

if __name__ == '__main__':
    main()

