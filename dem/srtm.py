import os
import requests
import zipfile
import rasterio
import numpy as np
import matplotlib.pyplot as plt

# --------------------------
# 1. Helper: SRTM tile name
# --------------------------
def tile_name(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"


# -----------------------------------------------
# 2. Try downloading SRTM tile directly from AWS
# -----------------------------------------------
def download_srtm_aws(lat, lon, out_path):
    tile = tile_name(lat, lon)
    url = f"https://srtm.kurviger.de/SRTM1/{tile}.hgt.zip"

    print(f"Trying direct SRTM download: {url}")

    r = requests.get(url, stream=True)
    if r.status_code != 200:
        print("Direct download failed.")
        return False

    zip_path = out_path + ".zip"
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)

    # unzip
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(os.path.dirname(out_path))
    os.remove(zip_path)

    print("Direct SRTM download successful.")
    return True


# ---------------------------------------------------------
# 3. Fallback: Download DEM from OpenTopography
# ---------------------------------------------------------
def download_opentopo(bounds, out_path, api_key):
    minlon, minlat, maxlon, maxlat = bounds

    print("Trying OpenTopography fallback...")

    url = (
        "https://portal.opentopography.org/API/globaldem?"
        "demtype=SRTMGL1&"
        f"south={minlat}&north={maxlat}&west={minlon}&east={maxlon}&"
        "outputFormat=GTiff"
        f"apikey={api_key}"
    )

    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise RuntimeError("OpenTopography request failed.")

    with open(out_path, "wb") as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)

    print("OpenTopography download successful.")
    return True


# ---------------------------------------------------------
# 4. Download DEM for Langtang Region
# ---------------------------------------------------------
bounds = (85.25, 28.15, 85.90, 28.60)
output_tif = "langtang_srtm.tif"

api_key = "d4339698fa9c0fc3fbdfaef059ebb1c3"

# Try direct SRTM tile downloads first
success = False
for lat in range(28, 30):  # rough coverage
    for lon in range(85, 87):
        tile = tile_name(lat, lon)
        out_tile = f"{tile}.hgt"

        if download_srtm_aws(lat, lon, out_tile):
            success = True

if not success:
    # fallback to OpenTopography
    download_opentopo(bounds, output_tif, api_key)
    hgt_mode = False
else:
    # If tiles exist, patch them into raster
    # (Simplest: convert only the tile covering Langtang)
    # Use first tile that exists:
    for lat in range(28, 30):
        for lon in range(85, 87):
            tile_path = f"{tile_name(lat, lon)}.hgt"
            if os.path.exists(tile_path):
                print(f"Using tile {tile_path}")
                # Convert raw .hgt to GeoTIFF
                import rasterio
                import rasterio.transform

                data = np.fromfile(tile_path, np.dtype(">i2")).reshape(3601, 3601)
                transform = rasterio.transform.from_origin(
                    lon, lat + 1, 1/3600, 1/3600
                )

                with rasterio.open(
                    output_tif,
                    "w",
                    driver="GTiff",
                    height=data.shape[0],
                    width=data.shape[1],
                    count=1,
                    dtype="int16",
                    crs="EPSG:4326",
                    transform=transform,
                ) as dst:
                    dst.write(data, 1)

                hgt_mode = True
                break
        if success:
            break


# ---------------------------------------------------------
# 5. Load and plot DEM
# ---------------------------------------------------------
with rasterio.open(output_tif) as src:
    dem = src.read(1)

plt.figure(figsize=(10, 8))
plt.imshow(dem, cmap="terrain")
plt.colorbar(label="Elevation (meters)")
plt.title("DEM – Langtang National Park")
plt.axis("off")
#plt.show()

plt.save("langtang_heightmap.png")