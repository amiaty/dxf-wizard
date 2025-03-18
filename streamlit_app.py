import streamlit as st
import io
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf import recover
from ezdxf.addons.drawing.config import Configuration, TextPolicy
import shapely.geometry as sg
import pandas as pd
import math
import uuid
from pywistor import Wistor
from utils import generate_uri

def display_dxf_without_text(doc, selected_layers=None):
    """Display the DXF file using matplotlib"""
    if not doc:
        return None
        
    fig = plt.figure(dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    config = Configuration(text_policy=TextPolicy.IGNORE)
    
    msp = doc.modelspace()
    
    # Create a filter function to select entities based on layer
    def entity_filter(entity):
        if selected_layers is None or not selected_layers:
            return True  # If no layers are specified, include all entities
        return entity.dxf.layer in selected_layers
    
    frontend = Frontend(ctx, out, config=config)
    frontend.draw_layout(msp, finalize=True, filter_func=entity_filter)
    
    return fig

def dxf_entity_to_wkt(entity):
    """Convert a DXF entity to WKT format with metadata"""
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
        line = sg.LineString([(entity.dxf.start.x, entity.dxf.start.y), 
                              (entity.dxf.end.x, entity.dxf.end.y)])
        result['wkt'] = line.wkt
        result['extra_data'] = {
            'start_point': f"{entity.dxf.start.x},{entity.dxf.start.y}",
            'end_point': f"{entity.dxf.end.x},{entity.dxf.end.y}"
        }
        
    # LWPOLYLINE - Lightweight polyline
    elif entity_type == 'LWPOLYLINE':
        points = entity.get_points()
        coords = [(p[0], p[1]) for p in points]
        
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
        vertices = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        
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
            points.append((x, y))
        
        # Close the polygon
        points.append(points[0])
        
        polygon = sg.Polygon(points)
        result['wkt'] = polygon.wkt
        result['extra_data'] = {
            'center': f"{center.x},{center.y}",
            'radius': radius
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
            points.append((x, y))
        
        linestring = sg.LineString(points)
        result['wkt'] = linestring.wkt
        result['extra_data'] = {
            'center': f"{center.x},{center.y}",
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
            
            points.append((x_rot, y_rot))
        
        # Close the polygon
        points.append(points[0])
        
        polygon = sg.Polygon(points)
        result['wkt'] = polygon.wkt
        result['extra_data'] = {
            'center': f"{center.x},{center.y}",
            'major_axis': a,
            'minor_axis': b,
            'rotation': math.degrees(rotation)
        }
        
    # POINT
    elif entity_type == 'POINT':
        point = sg.Point(entity.dxf.location.x, entity.dxf.location.y)
        result['wkt'] = point.wkt
        result['extra_data'] = {
            'location': f"{entity.dxf.location.x},{entity.dxf.location.y}"
        }
        
    # SPLINE
    elif entity_type == 'SPLINE':
        # Get a polyline approximation of the spline
        points = [(p.x, p.y) for p in entity.approximate()]
        linestring = sg.LineString(points)
        result['wkt'] = linestring.wkt
        result['extra_data'] = {
            'degree': entity.dxf.degree,
            'control_point_count': len(entity.control_points)
        }
        
    # TEXT, MTEXT - Text entities
    elif entity_type in ('TEXT', 'MTEXT'):
        # For text, we'll just use the insertion point
        if entity_type == 'TEXT':
            point = sg.Point(entity.dxf.insert.x, entity.dxf.insert.y)
            text_content = entity.dxf.text
        else:  # MTEXT
            point = sg.Point(entity.dxf.insert.x, entity.dxf.insert.y)
            text_content = entity.text
            
        result['wkt'] = point.wkt
        result['extra_data'] = {
            'location': f"{entity.dxf.insert.x},{entity.dxf.insert.y}",
            'text': text_content
        }
        
    # 3DFACE, SOLID, TRACE - Filled areas
    elif entity_type in ('3DFACE', 'SOLID', 'TRACE'):
        points = [(v.x, v.y) for v in entity.vertices()]
        
        # Ensure the polygon is closed
        if points[0] != points[-1]:
            points.append(points[0])
            
        polygon = sg.Polygon(points)
        result['wkt'] = polygon.wkt
        result['extra_data'] = {
            'vertex_count': len(entity.vertices())
        }
        
    # HATCH - Filled area defined by boundaries
    elif entity_type == 'HATCH':
        # Get all external paths
        paths = []
        for path in entity.paths:
            if hasattr(path, 'vertices'):
                vertices = [(v.x, v.y) for v in path.vertices]
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


def export_to_wkt(doc, selected_layers):
    """Export DXF entities to WKT using Shapely with expanded entity type support"""
    if not doc:
        return pd.DataFrame()
        
    msp = doc.modelspace()
    entities_data = []
    
    for entity in msp:
        try:
            if selected_layers and entity.dxf.layer not in selected_layers:
                continue
                
            # Convert entity to WKT and get metadata
            result = dxf_entity_to_wkt(entity)
            
            # Skip entities that couldn't be converted
            if not result['wkt']:
                continue
                
            # Generate a URI for the entity
            uri = generate_uri(result)
            
            # Add to our results list
            entities_data.append({
                'uri': uri,
                'layer': result['layer'],
                'type': result['type'],
                'wkt': result['wkt'],
                'color': result['color'],
                'extra_data': result['extra_data']
            })
                
        except Exception as e:
            # Log the error but continue processing other entities
            print(f"Error processing {entity.dxftype()} entity: {str(e)}")
            continue
    
    return pd.DataFrame(entities_data)

def process_uploaded_file(uploaded_file):
    """Process the uploaded file"""
    try:
        bytes_data = uploaded_file.getvalue()
        binary_dxf = io.BytesIO(bytes_data)
        doc, _ = recover.read(binary_dxf)
        return doc
    except Exception as e:
        st.error(f"Error processing DXF file: {str(e)}")
        return None

# Hide Streamlit components
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("DXF to WKT Converter")

uploaded_file = st.file_uploader("Choose a DXF file", type=['dxf'])

# Process the uploaded file
doc = None
if uploaded_file is not None:
    doc = process_uploaded_file(uploaded_file)
    if doc:
        st.success("DXF file loaded successfully!")

# Only show controls if we have a document
if doc is not None:
    # Display the full drawing first
    full_fig = display_dxf_without_text(doc)
    if full_fig:
        st.pyplot(full_fig)
    
    # Layer selection
    layer_names = [layer.dxf.name for layer in doc.layers]
    selected_layers = st.multiselect(
        "Select Layers", 
        layer_names, 
        default=[]
    )
    
    if selected_layers:
        # Get entity data with WKT and URIs
        entity_data = export_to_wkt(doc, selected_layers)
        
        # Display WKT and entity info
        if not entity_data.empty:
            st.subheader("Entity Data with URIs")
            st.dataframe(entity_data)
            
            # Option to download data in different formats
            col1, col2 = st.columns(2)
            
            with col1:
                selected_object_type = st.selectbox("What is the type of the selected objects?",("sewer_pipe", "other"))

            with col2:
                triples = []
                for _, row in entity_data.iterrows():
                    triples.append(f"(<{row['uri']}> \"{row['wkt']}\"^^geo:wktLiteral <http://wistor.nl/entityType#{selected_object_type}>)")
                triples_text = "\n".join(triples)
                if col2.button("Save to GraphDB"):
                    wistor = Wistor("Demo", "Demo", "Demo")
                    rule_result = wistor.execute_rule('ams_add_many_wkt',{"triples":triples_text}, debug_mode=True)
                    if rule_result['success']:
                        st.success("Entities added to GraphDB successfully!")
                    else:
                        st.error(f"Error adding entities to GraphDB: {rule_result['errors']}")
        else:
            st.write("No entities found in the selected layers.")
