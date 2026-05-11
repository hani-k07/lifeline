import os
import re

def replace_css_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    orig_content = content
    # Try to find the MASTER_CSS variable in app.py
    content = re.sub(r'MASTER_CSS = """\n<style>\n@import url.*?<\/style>\n"""\nst\.markdown\(MASTER_CSS, unsafe_allow_html=True\)', 
                     'from utils.styles import get_glass_css\nst.markdown(get_glass_css(), unsafe_allow_html=True)', 
                     content, flags=re.DOTALL)
    
    # Try to find st.markdown("""<style>@import...</style>""", unsafe_allow_html=True)
    content = re.sub(r'st\.markdown\("""<style>\n@import url\(.*?</style>""", unsafe_allow_html=True\)',
                     'from utils.styles import get_glass_css\nst.markdown(get_glass_css(), unsafe_allow_html=True)',
                     content, flags=re.DOTALL)

    if content != orig_content:
        print(f"Replaced CSS in {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

for root, _, files in os.walk('pages'):
    for file in files:
        if file.endswith('.py'):
            replace_css_in_file(os.path.join(root, file))

replace_css_in_file('app.py')

print("CSS refactoring complete.")
