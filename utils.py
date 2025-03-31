import base64
import math
from typing import List
import ezdxf
import shapely.geometry as sg
from pyproj import Transformer

def generate_uri(entity_data, base_uri = "http://wistor.nl/entities/"):
    """Generate a deterministic URI for a WKT entity"""
    # Create a unique identifier based on entity properties
    entity_type = entity_data['type']
    layer = entity_data['layer']
    
    # Use relevant parts of the WKT and extra data for URI generation, This ensures similar entities get similar URIs
    key_parts = [
        entity_type,
        layer,
        str(entity_data['color'])
    ]
    
    # Add relevant extra data based on entity type
    if 'center' in entity_data['extra_data']:
        key_parts.append(entity_data['extra_data']['center'])
    elif 'location' in entity_data['extra_data']:
        key_parts.append(entity_data['extra_data']['location'])
    elif 'start_point' in entity_data['extra_data']:
        key_parts.append(entity_data['extra_data']['start_point'])
    
    # Join key parts with a delimiter that won't appear in your data
    joined_parts = "||".join(key_parts)
    
    # Base64 encode for URL safety
    identifier = base64.urlsafe_b64encode(joined_parts.encode()).decode()
    
    # Format URI
    clean_layer = layer.replace(' ', '_').lower()
    clean_type = entity_type.lower()
    
    return f"{base_uri}{clean_layer}/{clean_type}/{identifier}"

def decode_uri(uri):
    # Extract the identifier part
    identifier = uri.split('/')[-1]
    
    # Decode the base64 data
    decoded = base64.urlsafe_b64decode(identifier).decode()
    
    # Split back into key parts
    key_parts = decoded.split('||')
    
    return key_parts

def get_non_empty_layer_names(doc: ezdxf.document.Drawing) -> List[str]:
    """
    Returns list of layer names where layers contain at least one entity.
    """
    used_layers = set()

    for entity in doc.modelspace():
        used_layers.add(entity.dxf.layer)

    non_empty_layer_names = sorted(used_layers)

    return non_empty_layer_names

def dxf_entity_to_wkt(entity):
    """Convert a DXF entity to WKT format with metadata and transform coordinates"""

    # Create transformer from EPSG:28992 (Amersfoort/RD New) to EPSG:4326 (WGS84)
    transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)
    
    # Helper function to transform coordinates
    def transform_point(x, y):
        lon, lat = transformer.transform(x, y)
        return lon, lat
    
    entity_type = entity.dxftype()

    result = {
        'layer': entity.dxf.layer,
        'type': entity_type,
        'color': entity.dxf.color if hasattr(entity.dxf, 'color') else 0,
        'wkt': None,
        'extra_data': {}
    }

    # LINE - Simple straight line
    if entity_type == 'LINE':
        start_x, start_y = transform_point(entity.dxf.start.x, entity.dxf.start.y)
        end_x, end_y = transform_point(entity.dxf.end.x, entity.dxf.end.y)
        
        line = sg.LineString([(start_x, start_y), (end_x, end_y)])
        result['wkt'] = line.wkt
        result['extra_data'] = {
            'start_point': f"{start_x},{start_y}",
            'end_point': f"{end_x},{end_y}"
        }
    
    # LWPOLYLINE - Lightweight polyline
    elif entity_type == 'LWPOLYLINE':
        points = entity.get_points()
        coords = [transform_point(p[0], p[1]) for p in points]
        
        if entity.closed and len(coords) > 2:
            # Closed polyline becomes a polygon
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            polygon = sg.Polygon(coords)
            result['wkt'] = polygon.wkt
        else:
            linestring = sg.LineString(coords)
            result['wkt'] = linestring.wkt
        
        result['extra_data'] = {
            'is_closed': entity.closed,
            'point_count': len(points)
        }

    # POLYLINE - Old-style polyline
    elif entity_type == 'POLYLINE':
        vertices = [transform_point(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        
        if entity.is_closed and len(vertices) > 2:
            if vertices[0] != vertices[-1]:
                vertices.append(vertices[0])
            polygon = sg.Polygon(vertices)
            result['wkt'] = polygon.wkt
        else:
            linestring = sg.LineString(vertices)
            result['wkt'] = linestring.wkt
            
        result['extra_data'] = {
            'is_closed': entity.is_closed,
            'point_count': len(vertices)
        }
        
    # CIRCLE - Perfect circle
    elif entity_type == 'CIRCLE':
        center = entity.dxf.center
        radius = entity.dxf.radius
        
        # Create points around the circle
        points = []
        for i in range(36):  # 36 points for a good approximation
            angle = math.radians(i * 10)
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            lon, lat = transform_point(x, y)
            points.append((lon, lat))
        
        # Close the polygon
        points.append(points[0])
        
        polygon = sg.Polygon(points)
        result['wkt'] = polygon.wkt
        
        center_lon, center_lat = transform_point(center.x, center.y)
        result['extra_data'] = {
            'center': f"{center_lon},{center_lat}",
            'radius': radius  # Note: radius is not transformed as it would be distorted
        }
    
    # ARC - Circular arc
    elif entity_type == 'ARC':
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle
        
        # Create points along the arc
        points = []
        # Handle cases where end_angle < start_angle (crosses 0°)
        if end_angle < start_angle:
            end_angle += 360
        
        # Number of segments depends on arc length
        angle_span = end_angle - start_angle
        num_segments = max(int(angle_span / 5), 8)  # At least 8 segments, or one every 5 degrees
        
        for i in range(num_segments + 1):
            angle = math.radians(start_angle + (angle_span * i / num_segments))
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            lon, lat = transform_point(x, y)
            points.append((lon, lat))
        
        linestring = sg.LineString(points)
        result['wkt'] = linestring.wkt
        
        center_lon, center_lat = transform_point(center.x, center.y)
        result['extra_data'] = {
            'center': f"{center_lon},{center_lat}",
            'radius': radius,
            'start_angle': start_angle,
            'end_angle': end_angle
        }
    
    # ELLIPSE
    elif entity_type == 'ELLIPSE':
        center = entity.dxf.center
        major_axis = entity.dxf.major_axis
        ratio = entity.dxf.ratio  # ratio of minor to major axis
        
        # Calculate the length of the major axis
        a = math.sqrt(major_axis.x**2 + major_axis.y**2)
        # Calculate the length of the minor axis
        b = a * ratio
        
        # Calculate the rotation angle of the ellipse
        rotation = math.atan2(major_axis.y, major_axis.x)
        
        # Generate points around the ellipse
        points = []
        for i in range(36):  # 36 points for a good approximation
            angle = i * 10  # in degrees
            angle_rad = math.radians(angle)
            
            # Parametric equation of ellipse
            x = a * math.cos(angle_rad)
            y = b * math.sin(angle_rad)
            
            # Rotate point
            x_rot = center.x + x * math.cos(rotation) - y * math.sin(rotation)
            y_rot = center.y + x * math.sin(rotation) + y * math.cos(rotation)
            
            lon, lat = transform_point(x_rot, y_rot)
            points.append((lon, lat))
        
        # Close the polygon
        points.append(points[0])
        
        polygon = sg.Polygon(points)
        result['wkt'] = polygon.wkt
        
        center_lon, center_lat = transform_point(center.x, center.y)
        result['extra_data'] = {
            'center': f"{center_lon},{center_lat}",
            'major_axis': a,
            'minor_axis': b,
            'rotation': math.degrees(rotation)
        }
    
    # POINT
    elif entity_type == 'POINT':
        lon, lat = transform_point(entity.dxf.location.x, entity.dxf.location.y)
        point = sg.Point(lon, lat)
        result['wkt'] = point.wkt
        result['extra_data'] = {
            'location': f"{lon},{lat}"
        }
    
    # SPLINE
    elif entity_type == 'SPLINE':
        # Get a polyline approximation of the spline
        points = [(p.x, p.y) for p in entity.approximate()]
        transformed_points = [transform_point(x, y) for x, y in points]
        linestring = sg.LineString(transformed_points)
        result['wkt'] = linestring.wkt
        result['extra_data'] = {
            'degree': entity.dxf.degree,
            'control_point_count': len(entity.control_points)
        }
    
    # TEXT, MTEXT - Text entities
    elif entity_type in ('TEXT', 'MTEXT'):
        # For text, we'll just use the insertion point
        if entity_type == 'TEXT':
            lon, lat = transform_point(entity.dxf.insert.x, entity.dxf.insert.y)
            text_content = entity.dxf.text
        else:  # MTEXT
            lon, lat = transform_point(entity.dxf.insert.x, entity.dxf.insert.y)
            text_content = entity.text
            
        point = sg.Point(lon, lat)
        result['wkt'] = point.wkt
        result['extra_data'] = {
            'location': f"{lon},{lat}",
            'text': text_content
        }
    
    # 3DFACE, SOLID, TRACE - Filled areas
    elif entity_type in ('3DFACE', 'SOLID', 'TRACE'):
        vertices = entity.vertices()
        points = [transform_point(v.x, v.y) for v in vertices]
        
        # Ensure the polygon is closed
        if points[0] != points[-1]:
            points.append(points[0])
            
        polygon = sg.Polygon(points)
        result['wkt'] = polygon.wkt
        result['extra_data'] = {
            'vertex_count': len(vertices)
        }
    
    # HATCH - Filled area defined by boundaries
    elif entity_type == 'HATCH':
        # Get all external paths
        paths = []
        for path in entity.paths:
            if hasattr(path, 'vertices'):
                vertices = [transform_point(v.x, v.y) for v in path.vertices]
                if vertices:
                    paths.append(vertices)
        
        # Create a MultiPolygon if multiple paths exist
        if len(paths) > 1:
            polygons = []
            for path in paths:
                if path[0] != path[-1]:
                    path.append(path[0])
                polygons.append(sg.Polygon(path))
            multi_polygon = sg.MultiPolygon(polygons)
            result['wkt'] = multi_polygon.wkt
        elif len(paths) == 1:
            path = paths[0]
            if path[0] != path[-1]:
                path.append(path[0])
            polygon = sg.Polygon(path)
            result['wkt'] = polygon.wkt
            
        result['extra_data'] = {
            'pattern': entity.dxf.pattern_name,
            'path_count': len(paths)
        }

    return result