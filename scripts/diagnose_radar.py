"""
Diagnose radar coordinate detection.

Captures a frame from the capture card and traces through the entire
get_coordinate() pipeline, reporting confidence scores at each step.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
import numpy as np

def main():
    # Usage: diagnose_radar.py [device_index | image_path]
    arg = sys.argv[1] if len(sys.argv) > 1 else "1"

    # 1. Get frame - either from file or capture device
    if os.path.isfile(arg):
        print(f"[1] Loading from file: {arg}")
        frame = cv2.imread(arg)
        if frame is None:
            print("FAILED to load image!")
            return
    else:
        device_index = int(arg)
        print(f"[1] Capturing from device {device_index} (via capture module)...")
        from src.hardware import capture
        if not capture.connect(device_index):
            print("FAILED to connect capture device!")
            return
        for _ in range(10):
            capture.capture_frame()
        frame = capture.capture_frame()
        capture.disconnect()
        if frame is None:
            print("FAILED to capture frame!")
            return

    w, h = frame.shape[1], frame.shape[0]
    print(f"   Frame: {w}x{h}")
    cv2.imwrite("debug_full_frame.png", frame)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 2. Find radar tools
    from src.repositories.radar import config as cfg
    cfg._ensure_loaded()

    template = cfg.images.get('tools')
    if template is None:
        print("[2] FAILED: radarTools template is None!")
        return

    print(f"[2] Radar tools template: {template.shape[1]}x{template.shape[0]}")
    result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    print(f"   Match score: {max_val:.4f} at {max_loc}")

    if max_val < 0.70:
        print("   FAILED: radarTools confidence too low!")
        return

    tools_pos = (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    print(f"   Radar tools: {tools_pos}")

    # 3. Extract radar image
    from src.repositories.radar.config import dimensions
    tools_x, tools_y, tools_w, tools_h = tools_pos

    x0 = tools_x - dimensions['width'] - 11
    x1 = x0 + dimensions['width']
    y0 = tools_y - 50
    y1 = y0 + dimensions['height']

    print(f"[3] Radar region: ({x0},{y0}) -> ({x1},{y1}) = {x1-x0}x{y1-y0}")

    if x0 < 0 or y0 < 0 or y1 > gray.shape[0] or x1 > gray.shape[1]:
        print("   FAILED: radar region out of bounds!")
        return

    radar_image = gray[y0:y1, x0:x1].copy()
    print(f"   Radar image shape: {radar_image.shape}")
    cv2.imwrite("debug_radar_extracted.png", radar_image)
    print("   Saved debug_radar_extracted.png")

    # 4. Floor level detection
    from src.repositories.radar.core import get_floor_level
    floor = get_floor_level(gray)
    print(f"[4] Floor level: {floor}")

    if floor is None:
        print("   FAILED: floor detection!")
        return

    # 5. Mask player position (same as core.py)
    radar_image[52, 53] = 128
    radar_image[52, 54] = 128
    radar_image[53, 53] = 128
    radar_image[53, 54] = 128
    radar_image[54, 51] = 128
    radar_image[54, 52] = 128
    radar_image[55, 51] = 128
    radar_image[55, 52] = 128
    radar_image[54, 53] = 128
    radar_image[54, 54] = 128
    radar_image[55, 53] = 128
    radar_image[55, 54] = 128
    radar_image[54, 55] = 128
    radar_image[54, 56] = 128
    radar_image[55, 55] = 128
    radar_image[55, 56] = 128
    radar_image[56, 53] = 128
    radar_image[56, 54] = 128
    radar_image[57, 53] = 128
    radar_image[57, 54] = 128
    cv2.imwrite("debug_radar_masked.png", radar_image)
    print("[5] Saved debug_radar_masked.png (with player mask)")

    # 6. Template match against floor image
    floor_img = cfg.floorsImgs[floor]
    if floor_img is None:
        print(f"[6] FAILED: floor image {floor} is None!")
        return

    print(f"[6] Floor {floor} image: {floor_img.shape[1]}x{floor_img.shape[0]}")

    result = cv2.matchTemplate(floor_img, radar_image, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    confidence_threshold = cfg.floorsConfidence[floor]
    print(f"   Match score: {max_val:.6f}")
    print(f"   Threshold:   {confidence_threshold}")
    print(f"   Result:      {'PASS' if max_val >= confidence_threshold else 'FAIL'}")
    print(f"   Match loc:   {max_loc}")

    if max_val >= confidence_threshold:
        x_pixel = max_loc[0] + dimensions['halfWidth']
        y_pixel = max_loc[1] + dimensions['halfHeight']
        COORDINATE_OFFSET_X = 31744
        COORDINATE_OFFSET_Y = 30976
        coord = (x_pixel + COORDINATE_OFFSET_X, y_pixel + COORDINATE_OFFSET_Y, floor)
        print(f"   Coordinate:  {coord}")

    # 7. Pixel stats
    print(f"\n[7] Pixel stats:")
    print(f"   Radar image: min={radar_image.min()}, max={radar_image.max()}, mean={radar_image.mean():.1f}, std={radar_image.std():.1f}")

    # Show unique pixel values (terrain colors)
    unique_radar = np.unique(radar_image)
    print(f"   Unique values in radar: {len(unique_radar)}")
    print(f"   Values: {unique_radar}")

    # Expected terrain colors from floor map
    terrain_colors = np.array([0, 1, 60, 76, 93, 102, 106, 111, 120, 136, 207, 213, 226, 240, 255])
    print(f"   Expected terrain palette: {terrain_colors}")

    # 8. Quantize radar to terrain palette (fix capture card color shift)
    print(f"\n[8] Color quantization approach:")

    # Build LUT: for each 0-255 value, map to nearest terrain color
    lut = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        distances = np.abs(terrain_colors.astype(int) - i)
        lut[i] = terrain_colors[np.argmin(distances)]

    radar_quantized = cv2.LUT(radar_image, lut)
    cv2.imwrite("debug_radar_quantized.png", radar_quantized)
    print("   Saved debug_radar_quantized.png")

    unique_quantized = np.unique(radar_quantized)
    print(f"   Unique values after quantization: {unique_quantized}")

    # Match quantized radar against floor image
    result_q = cv2.matchTemplate(floor_img, radar_quantized, cv2.TM_CCOEFF_NORMED)
    _, max_val_q, _, max_loc_q = cv2.minMaxLoc(result_q)
    print(f"   Quantized match score: {max_val_q:.6f} at {max_loc_q}")
    print(f"   Threshold: {confidence_threshold}")
    print(f"   Result: {'PASS' if max_val_q >= confidence_threshold else 'FAIL'}")

    if max_val_q >= 0.50:
        xp = max_loc_q[0] + dimensions['halfWidth']
        yp = max_loc_q[1] + dimensions['halfHeight']
        coord_q = (xp + 31744, yp + 30976, floor)
        print(f"   Coordinate: {coord_q}")

    # 9. Edge-based matching
    print(f"\n[9] Edge-based matching:")
    radar_edges = cv2.Canny(radar_image, 30, 100)
    floor_edges = cv2.Canny(floor_img, 30, 100)
    cv2.imwrite("debug_radar_edges.png", radar_edges)

    result_e = cv2.matchTemplate(floor_edges, radar_edges, cv2.TM_CCOEFF_NORMED)
    _, max_val_e, _, max_loc_e = cv2.minMaxLoc(result_e)
    print(f"   Edge match score: {max_val_e:.6f} at {max_loc_e}")

    if max_val_e >= 0.30:
        xp = max_loc_e[0] + dimensions['halfWidth']
        yp = max_loc_e[1] + dimensions['halfHeight']
        coord_e = (xp + 31744, yp + 30976, floor)
        print(f"   Coordinate: {coord_e}")

    # 10. Histogram equalization approach
    print(f"\n[10] Histogram equalization:")
    radar_eq = cv2.equalizeHist(radar_image)
    floor_eq = cv2.equalizeHist(floor_img)

    result_h = cv2.matchTemplate(floor_eq, radar_eq, cv2.TM_CCOEFF_NORMED)
    _, max_val_h, _, max_loc_h = cv2.minMaxLoc(result_h)
    print(f"   Equalized match score: {max_val_h:.6f} at {max_loc_h}")

    if max_val_h >= 0.30:
        xp = max_loc_h[0] + dimensions['halfWidth']
        yp = max_loc_h[1] + dimensions['halfHeight']
        coord_h = (xp + 31744, yp + 30976, floor)
        print(f"   Coordinate: {coord_h}")

    # 11. Limited range correction (NV12/capture card: 16-235 → 0-255)
    print(f"\n[11] Limited range LUT correction (16-235 -> 0-255):")
    lut_limited = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        lut_limited[i] = np.clip(round((i - 16) * 255.0 / 219.0), 0, 255)
    radar_corrected = cv2.LUT(radar_image, lut_limited)
    cv2.imwrite("debug_radar_lut_corrected.png", radar_corrected)
    print(f"   Corrected range: {radar_corrected.min()}-{radar_corrected.max()}")
    print(f"   Unique values: {len(np.unique(radar_corrected))}")

    result_lut = cv2.matchTemplate(floor_img, radar_corrected, cv2.TM_CCOEFF_NORMED)
    _, max_val_lut, _, max_loc_lut = cv2.minMaxLoc(result_lut)
    print(f"   LUT corrected match: {max_val_lut:.6f} at {max_loc_lut}")

    # Also try quantizing after LUT correction
    radar_lut_quantized = cv2.LUT(radar_corrected, lut)
    result_lq = cv2.matchTemplate(floor_img, radar_lut_quantized, cv2.TM_CCOEFF_NORMED)
    _, max_val_lq, _, max_loc_lq = cv2.minMaxLoc(result_lq)
    print(f"   LUT + quantized match: {max_val_lq:.6f} at {max_loc_lq}")
    cv2.imwrite("debug_radar_lut_quantized.png", radar_lut_quantized)

    if max_val_lq >= 0.50:
        xp = max_loc_lq[0] + dimensions['halfWidth']
        yp = max_loc_lq[1] + dimensions['halfHeight']
        coord_lq = (xp + 31744, yp + 30976, floor)
        print(f"   Coordinate: {coord_lq}")

    # 12. Reduce to N bins (coarse matching)
    print(f"\n[12] Coarse bin matching:")
    for n_bins in [4, 8, 16, 32]:
        bin_size = 256.0 / n_bins
        radar_binned = (radar_image / bin_size).astype(np.uint8)
        floor_binned = (floor_img / bin_size).astype(np.uint8)
        result_b = cv2.matchTemplate(floor_binned, radar_binned, cv2.TM_CCOEFF_NORMED)
        _, mv_b, _, ml_b = cv2.minMaxLoc(result_b)
        print(f"   {n_bins:2d} bins: score={mv_b:.6f} at {ml_b}")

    # 13. Process floor map to simulate capture card (apply limited range encoding)
    print(f"\n[13] Simulated capture card floor map:")
    lut_encode = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        lut_encode[i] = np.clip(round(16 + i * 219.0 / 255.0), 0, 255)
    floor_encoded = cv2.LUT(floor_img, lut_encode)
    cv2.imwrite("debug_floor_encoded.png", floor_encoded[0:500, 0:500])

    result_enc = cv2.matchTemplate(floor_encoded, radar_image, cv2.TM_CCOEFF_NORMED)
    _, max_val_enc, _, max_loc_enc = cv2.minMaxLoc(result_enc)
    print(f"   Encoded floor match: {max_val_enc:.6f} at {max_loc_enc}")

    if max_val_enc >= 0.50:
        xp = max_loc_enc[0] + dimensions['halfWidth']
        yp = max_loc_enc[1] + dimensions['halfHeight']
        coord_enc = (xp + 31744, yp + 30976, floor)
        print(f"   Coordinate: {coord_enc}")

    # Also add Gaussian blur to simulate capture card blurring
    floor_encoded_blur = cv2.GaussianBlur(floor_encoded, (3, 3), 0)
    result_encb = cv2.matchTemplate(floor_encoded_blur, radar_image, cv2.TM_CCOEFF_NORMED)
    _, max_val_encb, _, max_loc_encb = cv2.minMaxLoc(result_encb)
    print(f"   Encoded+blur match:  {max_val_encb:.6f} at {max_loc_encb}")

    if max_val_encb >= 0.50:
        xp = max_loc_encb[0] + dimensions['halfWidth']
        yp = max_loc_encb[1] + dimensions['halfHeight']
        coord_encb = (xp + 31744, yp + 30976, floor)
        print(f"   Coordinate: {coord_encb}")

    # 14. Test with capture card mode (lowered thresholds)
    print(f"\n[14] Capture card mode test (threshold 0.35):")
    from src.repositories.radar.core import set_capture_card_mode, get_coordinate
    set_capture_card_mode(True)
    coord_cc = get_coordinate(gray)
    print(f"   get_coordinate result: {coord_cc}")

    # Summary
    print(f"\n[SUMMARY]")
    print(f"   Raw score:       {max_val:.4f} (need {confidence_threshold})")
    print(f"   Capture card fix: {'WORKS' if coord_cc else 'STILL FAILS'}")
    if coord_cc:
        print(f"   Coordinate:      {coord_cc}")


if __name__ == "__main__":
    main()
