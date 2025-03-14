import streamlit as st
from streamlit.components.v1 import html
import json

# Title for the app
st.title("Streamlit with JavaScript Integration")

# Simple button to trigger JavaScript
if st.button("Run JavaScript"):

    js_html = """

    <script>

        alert("Hello from JavaScript!");
        parent.getIface().me.props.setLoading(true);
        
    </script>

    """

    html(js_html, height=100)

    st.success("JavaScript function executed! Check the custom component below.")