import zipfile
import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.geometry import LineString
import argparse

# Utils
def read_df_from_zip(zip_path, file_name):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        if file_name in zip_ref.namelist():
            with zip_ref.open(file_name) as file:
                df = pd.read_csv(file)
                return df
        else:
            raise ValueError(f"File {file_name} not found in {zip_path}")
        
def read_file(dir, file_name):
    if not os.path.exists(dir):
        raise ValueError(f"Dir {dir} not found")
    
    if os.path.isdir(dir):
        with open(os.path.join(dir, file_name), 'r') as file:
            return file.read()
    if os.path.isfile(dir) and dir.endswith('.zip'):
        return read_df_from_zip(dir, file_name)
    
    raise ValueError(f"Dir {dir} is not a directory or a zip file")

def read_gtfs_files(dir):
    return {
        # 'agency': read_file(dir, 'agency.txt'),
        'stops': read_file(dir, 'stops.txt'),
        'shapes': read_file(dir, 'shapes.txt'),
    }

def to_point_shape_file(df, name_map, xy, output_path, crs=4326):
    df['name'] = df[name_map]
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df[xy[0]], df[xy[1]], z=0)
    )
    gdf.set_crs(epsg=crs, inplace=True)

    # Save as Shapefile
    gdf.to_file(os.path.join(output_path, 'stops.shp'))
    gdf.to_file(os.path.join(output_path, 'stops.geojson'), driver='GeoJSON')

def to_line_shape_file(df, name_map, xy, output_path, crs=4326):
    shapes = df.groupby(name_map).apply(
        lambda l: LineString(zip(l[xy[0]], l[xy[1]]))
    )
    gdf = gpd.GeoDataFrame(shapes, columns=["geometry"])
    gdf['name'] = shapes.index
    gdf = gdf[['name', 'geometry']].reset_index(drop=True)
    gdf.set_crs(epsg=crs, inplace=True)

    # Save as Shapefile
    gdf.to_file(os.path.join(output_path, 'road.shp'))

def make_stop_shape(stops_df, output_path):
    to_point_shape_file(stops_df, 'stop_id', ['stop_lon', 'stop_lat'], output_path)

def make_route_shape(shapes_df, output_path):
    to_line_shape_file(shapes_df, 'shape_id', ['shape_pt_lon', 'shape_pt_lat'], output_path)

def make_all_shape(gtfs_path, output_path):
    gtfs_files = read_gtfs_files(gtfs_path)
    make_stop_shape(gtfs_files['stops'], output_path)
    make_route_shape(gtfs_files['shapes'], output_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert GTFS to Shapefile')
    parser.add_argument('--gtfs-path', type=str, help='Path to GTFS zip file')
    parser.add_argument('--output-path', type=str, help='Output path for shapefile')
    args = parser.parse_args()
    make_all_shape(args.gtfs_path, args.output_path)
