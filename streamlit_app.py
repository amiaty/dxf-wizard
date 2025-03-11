#streamlit run streamlit_app.py --server.enableXsrfProtection=false
import streamlit as st
import io
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf import recover
from ezdxf.addons.drawing.config import Configuration, TextPolicy
#from pywistor import Wistor

# Initialize session state variables
if 'doc' not in st.session_state:
    st.session_state.doc = None
if 'layer_names' not in st.session_state:
    st.session_state.layer_names = []
if 'wkt_cache' not in st.session_state:
    st.session_state.wkt_cache = {}

@st.cache_data
def display_dxf_without_text(doc_id, selected_layers=None):
    """Cache the DXF rendering to avoid recomputation"""
    doc = st.session_state.doc
    if not doc:
        return None
        
    fig = plt.figure(dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    config = Configuration(text_policy=TextPolicy.IGNORE)
    
    # Get the modelspace
    msp = doc.modelspace()
    
    # Create a filter function to select entities based on layer
    def entity_filter(entity):
        if selected_layers is None or not selected_layers:
            return True  # If no layers are specified, include all entities
        return entity.dxf.layer in selected_layers
    
    # Draw the layout with the filter
    frontend = Frontend(ctx, out, config=config)
    frontend.draw_layout(msp, finalize=True, filter_func=entity_filter)
    
    return fig

@st.cache_data
def export_to_wkt(doc_id, selected_layers):
    """Cache the WKT conversion to avoid recomputation"""
    # Check if we already computed this combination
    cache_key = tuple(sorted(selected_layers))
    if cache_key in st.session_state.wkt_cache:
        return st.session_state.wkt_cache[cache_key]
        
    doc = st.session_state.doc
    if not doc:
        return []
        
    msp = doc.modelspace()
    wkt_list = []
    
    for entity in msp:
        try:
            if selected_layers and entity.dxf.layer not in selected_layers:
                continue
                
            if entity.dxftype() == 'LINE':
                wkt_list.append(f"LINESTRING({entity.dxf.start.x} {entity.dxf.start.y}, {entity.dxf.end.x} {entity.dxf.end.y})")
                
            elif entity.dxftype() == 'LWPOLYLINE':
                points = entity.get_points()
                coords = ", ".join([f"{p[0]} {p[1]}" for p in points])
                
                if entity.closed and len(points) > 2:
                    wkt_list.append(f"POLYGON(({coords}, {points[0][0]} {points[0][1]}))")
                else:
                    wkt_list.append(f"LINESTRING({coords})")
                    
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                wkt_list.append(f"POINT({center.x} {center.y})")
        except Exception as e:
            # Skip problematic entities
            continue
    
    # Store in cache
    st.session_state.wkt_cache[cache_key] = wkt_list
    return wkt_list

def process_uploaded_file(uploaded_file):
    """Process the uploaded file and store in session state"""
    try:
        # Get the bytes from the uploaded file
        bytes_data = uploaded_file.getvalue()
        
        # Create BytesIO object for ezdxf to read
        binary_dxf = io.BytesIO(bytes_data)
        
        # Try to read using recover mode
        doc, _ = recover.read(binary_dxf)
        
        # Store in session state
        st.session_state.doc = doc
        st.session_state.doc_id = id(doc)  # Used for caching
        st.session_state.layer_names = [layer.dxf.name for layer in doc.layers]
        st.session_state.wkt_cache = {}  # Clear cache on new file
        
        return True
    except Exception as e:
        st.error(f"Error processing DXF file: {str(e)}")
        return False


hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            /* Target the specific container with important flag and fixed position override */
            ._container_1upux_1 {
                display: none !important;
                position: absolute !important;
                visibility: hidden !important;
                opacity: 0 !important;
                height: 0 !important;
                pointer-events: none !important;
            }
            
            /* Alternative approach using fixed position targeting */
            div[style*="position: fixed"][style*="bottom: 0"] {
                display: none !important;
            }
            
            /* Additional attempt using more specific selectors */
            div[class*="_container_"][style*="position: fixed"],
            div[class*="_container_1upux_"] {
                display: none !important;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("DXF to WKT Wizard")

uploaded_file = st.file_uploader("Choose a DXF file", type=['dxf'], key="file_uploader")

# Process the uploaded file
if uploaded_file is not None and (not st.session_state.doc or uploaded_file.name != st.session_state.get('last_file', '')):
    st.session_state.last_file = uploaded_file.name
    if process_uploaded_file(uploaded_file):
        st.success("DXF file loaded successfully!")

# Only show controls if we have a document
if st.session_state.doc is not None:
    # Display the full drawing first
    full_fig = display_dxf_without_text(st.session_state.doc_id)
    if full_fig:
        st.pyplot(full_fig)
    
    # Layer selection
    selected_layers = st.multiselect(
        "Select Layers", 
        st.session_state.layer_names, 
        default=[]
    )
    
    if selected_layers:
        col1, col2 = st.columns(2)
        
        with col1:
            filtered_fig = display_dxf_without_text(st.session_state.doc_id, selected_layers)
            if filtered_fig:
                st.pyplot(filtered_fig)
        
        with col2:
            wkt_strings = export_to_wkt(st.session_state.doc_id, selected_layers)
            wkt_text = ",\n".join(wkt_strings)
            st.text_area("WKT Objects List", wkt_text, height=400)
            #wistor = Wistor("Demo", "Demo", "Demo")
            #wistor.execute_rule('ams_add_many_wkt',{"pairs":'(<http://example.org/Point55> "POINT(4.9 52.3)"^^geo:wktLiteral)\n(<http://example.org/Point87> "POINT(4.8 51.4)"^^geo:wktLiteral)'},debug_mode=True)