import streamlit as st
import io
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf import recover
from ezdxf.addons.drawing.config import Configuration, TextPolicy

import pandas as pd
from pywistor import Wistor
from utils import generate_uri, get_non_empty_layer_names, dxf_entity_to_wkt

def display_dxf(doc, selected_layers=None, render_txt=False):
    """Display the DXF file using matplotlib"""
    if not doc:
        return None

    fig = plt.figure(dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)

    # Use IGNORE or SHOW based on render_txt flag
    config = Configuration(text_policy=TextPolicy.FILLING if render_txt else TextPolicy.IGNORE)

    msp = doc.modelspace()

    def entity_filter(entity):
        if selected_layers is None or not selected_layers:
            return True
        return entity.dxf.layer in selected_layers

    frontend = Frontend(ctx, out, config=config)

    # If render_txt is True, we skip the filter to include all entities
    frontend.draw_layout(msp, finalize=True, filter_func=entity_filter)

    return fig

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

st.title("DXF Wizard")

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
    full_fig = display_dxf(doc)
    if full_fig: st.pyplot(full_fig)
    
    # Layer selection (here we are only interested in layers with entities)
    layer_names = get_non_empty_layer_names(doc)
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
                if col2.button("Import"):
                    wistor = Wistor("AMS", "Gemeente Amersfoort", "oA^a&W4TvxK^zl", cgi="https://amersfoort-bms-poc.wistor.nl/servlets/cgi/")
                    rule_result = wistor.execute_rule('ams_add_many_wkt',{"triples":triples_text}, debug_mode=True)
                    if rule_result['success']:
                        st.success(f"{len(triples)} {selected_object_type} successfully added to the database!")
                    else:
                        st.error(f"Error adding entities to GraphDB: {rule_result['errors']}")
        else:
            st.write("No entities found in the selected layers.")
