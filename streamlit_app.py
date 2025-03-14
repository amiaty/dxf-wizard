import streamlit as st
from streamlit.components.v1 import html

# Title for the app
st.title("Streamlit with JavaScript Integration")

# Simple button to trigger JavaScript
if st.button("Run JavaScript"):
    js_html = """
    <script>
        (function() {
            let levels = 0;
            let iface = null;
            let context = window;

            try {
                while (levels < 4) { // Ensure we don't go beyond 3 levels
                    if (context.getIface) {
                        iface = context.getIface();
                        break;
                    }
                    if (context.parent === context) break; // Stop if no more parents
                    context = context.parent;
                    levels++;
                }

                if (iface && iface.me && iface.me.showToast) {
                    iface.me.showToast("hallo");
                } else {
                    console.error("Unable to find getIface().me.showToast");
                }
            } catch (error) {
                console.error("Error accessing parent levels: ", error);
            }
        })();
    </script>
    """

    html(js_html, height=100)

    st.success("JavaScript function executed! Check the iframe.")
