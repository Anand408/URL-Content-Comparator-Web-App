import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import difflib
import time
from io import BytesIO

# Function to fetch cleaned text from a URL
def get_text_from_url(url, retries=3, backoff=2):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", ""):
                return "", "Failed", "Non-HTML content"
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup(['script', 'style']):
                element.decompose()
            return soup.get_text(separator=' ').strip(), "Success", None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
            else:
                return "", "Failed", str(e)

# Compare texts and extract diff
def compare_texts_detailed(old_text, new_text):
    old_words = old_text.split()
    new_words = new_text.split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    only_old, only_new, common = [], [], []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            common.extend(old_words[i1:i2])
        elif tag == 'delete':
            only_old.extend(old_words[i1:i2])
        elif tag == 'insert':
            only_new.extend(new_words[j1:j2])
        elif tag == 'replace':
            only_old.extend(old_words[i1:i2])
            only_new.extend(new_words[j1:j2])

    similarity = matcher.ratio()
    return (
        ' '.join(only_old[:500]),
        ' '.join(only_new[:500]),
        ' '.join(common[:500]),
        f"{similarity:.2%}"
    )

# Streamlit UI
st.title("🔍 URL Content Comparator Web App")
st.write("Upload an Excel file with `Old_URL` and `New_URL` columns to compare webpage content.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        st.success("File uploaded successfully!")

        if not {'Old_URL', 'New_URL'}.issubset(df.columns):
            st.error("Excel must contain 'Old_URL' and 'New_URL' columns.")
        else:
            progress = st.progress(0)
            results = []
            total = df.shape[0]

            only_in_old_list, only_in_new_list = [], []
            common_content_list, similarity_list = [], []
            old_statuses, old_errors = [], []
            new_statuses, new_errors = [], []

            for idx, row in df.iterrows():
                old_url, new_url = row['Old_URL'], row['New_URL']
                old_text, old_status, old_err = get_text_from_url(old_url)
                new_text, new_status, new_err = get_text_from_url(new_url)

                old_statuses.append(old_status)
                old_errors.append(old_err if old_err else "None")
                new_statuses.append(new_status)
                new_errors.append(new_err if new_err else "None")

                if old_status == "Failed" or new_status == "Failed":
                    only_in_old_list.append("Error fetching content")
                    only_in_new_list.append("Error fetching content")
                    common_content_list.append("Error fetching content")
                    similarity_list.append("N/A")
                else:
                    only_old, only_new, common, sim = compare_texts_detailed(old_text, new_text)
                    only_in_old_list.append(only_old)
                    only_in_new_list.append(only_new)
                    common_content_list.append(common)
                    similarity_list.append(sim)

                progress.progress((idx + 1) / total)

            df['Old URL Status'] = old_statuses
            df['Old URL Error'] = old_errors
            df['New URL Status'] = new_statuses
            df['New URL Error'] = new_errors
            df['Only in Old'] = only_in_old_list
            df['Only in New'] = only_in_new_list
            df['Common Content'] = common_content_list
            df['Similarity'] = similarity_list

            st.success("✅ Comparison complete!")
            st.dataframe(df.head(10))

            # Download button
            output = BytesIO()
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Download Result Excel",
                data=output,
                file_name="content_diff_by_column.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"An error occurred: {e}")
