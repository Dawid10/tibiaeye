#!/usr/bin/env python3
"""
Find Closest Waypoint - Detecta sua posição atual e encontra o waypoint mais próximo.

Uso:
    python find_closest_waypoint.py routes/rotworm_cave.json
    python find_closest_waypoint.py routes/rotworm_cave.json --continuous
    python find_closest_waypoint.py routes/rotworm_cave.json --top 5

Opções:
    --continuous, -c    Atualiza continuamente (a cada 1 segundo)
    --top N, -t N       Mostra os N waypoints mais próximos (default: 3)
"""
import sys
import os
import json
import argparse
import math
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_waypoints(filepath: str) -> list:
    """Carrega waypoints de um arquivo JSON."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get('waypoints', [])


def calculate_distance(coord1: tuple, coord2: tuple) -> float:
    """
    Calcula distância 3D entre duas coordenadas.

    Penaliza muito a diferença de floor (z) porque mudar de andar
    requer escadas/rope/shovel.
    """
    x1, y1, z1 = coord1
    x2, y2, z2 = coord2

    # Distância euclidiana no plano XY
    xy_distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # Penaliza mudança de floor (cada floor = 100 tiles de "distância")
    floor_penalty = abs(z2 - z1) * 100

    return xy_distance + floor_penalty


def get_current_coordinate(debug: bool = False) -> tuple:
    """Obtém a coordenada atual do jogador via radar/minimap."""
    from src.core import get_screen_capture
    from src.repositories.radar import get_coordinate, get_floor_level
    from src.repositories.radar.locators import clear_all_radar_caches, get_radar_tools_position
    from src.repositories.radar.extractors import get_radar_image
    from src.repositories.radar.config import (
        coordinates as coord_cache,
        floorsImgs,
        floorsConfidence,
        dimensions,
        COORDINATE_OFFSET_X,
        COORDINATE_OFFSET_Y,
    )
    import cv2

    # Limpa TODOS os caches para garantir detecção fresh
    clear_all_radar_caches()
    coord_cache.clear()

    screen = get_screen_capture()
    img = screen.capture()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if debug:
        # Mostra informações de debug
        tools_pos = get_radar_tools_position(gray, use_cache=False)
        print(f"[DEBUG] Radar tools position: {tools_pos}")

        if tools_pos:
            radar_img = get_radar_image(gray, tools_pos)
            if radar_img is not None:
                print(f"[DEBUG] Radar image shape: {radar_img.shape}")

                # Detecta floor e mostra confiança do match
                floor = get_floor_level(gray)
                print(f"[DEBUG] Floor level detected: {floor}")

                if floor is not None:
                    floor_img = floorsImgs[floor]
                    if floor_img is not None:
                        # Mascara posição do jogador (como no get_coordinate)
                        radar_copy = radar_img.copy()
                        radar_copy[52, 53] = 128
                        radar_copy[52, 54] = 128
                        radar_copy[53, 53] = 128
                        radar_copy[53, 54] = 128
                        radar_copy[54, 51] = 128
                        radar_copy[54, 52] = 128
                        radar_copy[55, 51] = 128
                        radar_copy[55, 52] = 128
                        radar_copy[54, 53] = 128
                        radar_copy[54, 54] = 128
                        radar_copy[55, 53] = 128
                        radar_copy[55, 54] = 128
                        radar_copy[54, 55] = 128
                        radar_copy[54, 56] = 128
                        radar_copy[55, 55] = 128
                        radar_copy[55, 56] = 128
                        radar_copy[56, 53] = 128
                        radar_copy[56, 54] = 128
                        radar_copy[57, 53] = 128
                        radar_copy[57, 54] = 128

                        # Faz template matching e mostra confiança
                        result = cv2.matchTemplate(floor_img, radar_copy, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(result)
                        print(f"[DEBUG] Match confidence: {max_val:.4f} (threshold: {floorsConfidence[floor]})")
                        print(f"[DEBUG] Match location (pixel): {max_loc}")

                        # Converte para coordenada
                        x_pixel = max_loc[0] + dimensions['halfWidth']
                        y_pixel = max_loc[1] + dimensions['halfHeight']
                        calc_coord = (x_pixel + COORDINATE_OFFSET_X, y_pixel + COORDINATE_OFFSET_Y, floor)
                        print(f"[DEBUG] Calculated coordinate: {calc_coord}")

    coord = get_coordinate(gray)
    return coord


def find_closest_waypoints(waypoints: list, current_coord: tuple, top_n: int = 3) -> list:
    """
    Encontra os N waypoints mais próximos da posição atual.

    Retorna lista de tuplas: (waypoint, distance)
    """
    if current_coord is None:
        return []

    results = []

    for wp in waypoints:
        wp_coord = tuple(wp['coordinate'])
        distance = calculate_distance(current_coord, wp_coord)
        results.append((wp, distance))

    # Ordena por distância
    results.sort(key=lambda x: x[1])

    return results[:top_n]


def format_waypoint(wp: dict, distance: float, current_coord: tuple) -> str:
    """Formata um waypoint para exibição."""
    wp_coord = wp['coordinate']
    wp_type = wp['type']
    wp_id = wp['id']
    label = wp.get('label', '')

    # Indica se está no mesmo floor
    same_floor = "✓" if wp_coord[2] == current_coord[2] else f"floor {wp_coord[2]}"

    # Label se existir
    label_str = f" [{label}]" if label else ""

    return f"  ID {wp_id:3d} | {wp_type:10s} | ({wp_coord[0]}, {wp_coord[1]}, {wp_coord[2]}) | dist: {distance:6.1f} | {same_floor}{label_str}"


def main():
    parser = argparse.ArgumentParser(description='Encontra o waypoint mais próximo da sua posição atual')
    parser.add_argument('waypoints_file', type=str, help='Arquivo JSON com waypoints')
    parser.add_argument('--continuous', '-c', action='store_true', help='Atualiza continuamente')
    parser.add_argument('--top', '-t', type=int, default=3, help='Mostra os N mais próximos (default: 3)')
    parser.add_argument('--debug', '-d', action='store_true', help='Mostra informações de debug')
    args = parser.parse_args()

    # Carrega waypoints
    if not os.path.exists(args.waypoints_file):
        print(f"Erro: Arquivo não encontrado: {args.waypoints_file}")
        sys.exit(1)

    waypoints = load_waypoints(args.waypoints_file)
    print(f"Carregados {len(waypoints)} waypoints de {args.waypoints_file}")
    print()

    def update():
        # Obtém coordenada atual
        try:
            coord = get_current_coordinate(debug=args.debug)
        except Exception as e:
            print(f"Erro ao detectar coordenada: {e}")
            import traceback
            traceback.print_exc()
            return None

        if coord is None:
            print("Não foi possível detectar a coordenada. Verifique se:")
            print("  1. O Tibia está rodando")
            print("  2. O minimap está visível")
            print("  3. O zoom do minimap está no padrão (clique no botão central)")
            return None

        print(f"Sua posição atual: ({coord[0]}, {coord[1]}, {coord[2]})")
        print()

        # Encontra waypoints mais próximos
        closest = find_closest_waypoints(waypoints, coord, args.top)

        if not closest:
            print("Nenhum waypoint encontrado.")
            return None

        print(f"Top {len(closest)} waypoints mais próximos:")
        print("-" * 80)

        for wp, distance in closest:
            print(format_waypoint(wp, distance, coord))

        print("-" * 80)
        print()

        # Retorna o ID do mais próximo
        best_wp = closest[0][0]
        best_dist = closest[0][1]

        print(f">>> WAYPOINT MAIS PRÓXIMO: ID {best_wp['id']} (distância: {best_dist:.1f})")
        print()
        print(f"Para iniciar do waypoint mais próximo, use:")
        print(f"  python main.py --waypoints {args.waypoints_file} --start-waypoint {best_wp['id']}")

        return best_wp['id']

    if args.continuous:
        print("Modo contínuo ativado. Pressione Ctrl+C para sair.")
        print("=" * 80)

        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                print(f"=== FIND CLOSEST WAYPOINT === (atualizado: {time.strftime('%H:%M:%S')})")
                print()
                update()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nEncerrado.")
    else:
        update()


if __name__ == "__main__":
    main()
