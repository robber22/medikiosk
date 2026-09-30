import streamlit as st
import io, base64

def render_nicely(d):
    if not d:
        st.caption("Nothing extracted.")
        return
    for k, v in d.items():
        if v in (None, "", "unclear", []):
            continue
        label = k.replace("_", " ").title()
        if isinstance(v, list):
            if not v:
                continue
            st.markdown(f"**{label}:**")
            for item in v:
                if isinstance(item, dict):
                    line = " — ".join(str(x) for x in item.values() if x)
                    st.markdown(f"- {line}")
                else:
                    st.markdown(f"- {item}")
        else:
            st.markdown(f"**{label}:** {v}")

def compress_image_to_base64(pil_image, max_width=800, quality=60):
    img = pil_image.convert("RGB")
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")