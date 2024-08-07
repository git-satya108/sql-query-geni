import os
import openai
import streamlit as st
from dotenv import load_dotenv, find_dotenv
import pandas as pd
from PandaSQLite import PandaSQLiteDB
from sqlalchemy import create_engine

# Load OpenAI API key
load_dotenv(find_dotenv(), override=True)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize PandaSQLiteDB
db = PandaSQLiteDB("database.db")

# Initialize session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display the banner image
st.image("imagebanner1.png", use_column_width=True)


# Function to load and read multiple Excel files
def load_excel_files(uploaded_files):
    all_sheets = {}
    for uploaded_file in uploaded_files:
        xls = pd.ExcelFile(uploaded_file)
        for sheet_name in xls.sheet_names:
            all_sheets[sheet_name] = pd.read_excel(xls, sheet_name)
    return all_sheets


# Function to analyze data and provide recommendations
def analyze_data(sheets):
    response = ""
    for sheet_name, df in sheets.items():
        response += f"Table '{sheet_name}' has {df.shape[0]} rows and {df.shape[1]} columns.\n\n"
        if df.isnull().values.any():
            response += f"Warning: The sheet '{sheet_name}' contains missing values. This might affect SQL generation.\n"
        prompt = f"Explain the contents of the following table:\n{df.head()}"
        explanation = chat_with_assistant(prompt,
                                          "You are a helpful assistant, SQL programmer, data scientist, and generative AI specialist.")
        response += f"Explanation: {explanation}\n\n"
    return response


# Chat with the assistant using OpenAI API
def chat_with_assistant(prompt, system_message):
    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ]
        )
        message = response.choices[0].message.content
        return message
    except Exception as e:
        return None


# Create tables in SQLite from Excel sheets
def create_tables_from_sheets(sheets):
    for sheet_name, df in sheets.items():
        df.to_csv(f"{sheet_name}.csv", index=False)
        try:
            db.import_data(sheet_name, f"{sheet_name}.csv", format="csv", if_exists="replace")
            st.success(f"Table created for sheet: {sheet_name}")
        except Exception as e:
            st.error(f"An error occurred while creating the table {sheet_name}: {str(e)}")


# Upload and process documents
uploaded_files = st.file_uploader("Upload your Excel files", accept_multiple_files=True, type=["xlsx"])
if uploaded_files:
    sheets = load_excel_files(uploaded_files)
    st.session_state['sheets'] = sheets
    st.success("Documents uploaded and processed successfully.")
    create_tables_from_sheets(sheets)

# Add Data button
if st.button("Add Data"):
    sheets = st.session_state.get('sheets', None)
    if sheets:
        create_tables_from_sheets(sheets)
        st.success("Data added to the database.")
    else:
        st.error("No data to add. Please upload a document first.")

# SQL query generation section with example prompts
st.markdown("## Generate SQL queries based on the uploaded data or provided schema:")
prompt = st.text_area("Enter your prompt here (e.g., 'Select all data from the student performance table'):",
                      height=100)
table_name = st.text_input("Enter the table name:")
system_message = (
    "You are a well-versed and proficient SQL programmer and you are excellent in generating and executing SQL queries. "
    "You provide thoughtful recommendations and insights on the table schema and detect any anomalies in the data such as null values, "
    "missing values, duplicates, data types, etc. You are an unbeatable anomaly detector and detect data issues and schema issues spontaneously."
)
if st.button("Generate SQL Query"):
    if prompt:
        if table_name in st.session_state['sheets']:
            df = st.session_state['sheets'][table_name]
            # Replace spaces in column names with underscores
            df.columns = df.columns.str.replace(' ', '_')

            # Create an in-memory SQLite database
            engine = create_engine("sqlite:///:memory:")

            # Convert DataFrame to a SQL table
            df.to_sql(table_name, engine, if_exists="replace")

            sql_result = chat_with_assistant(prompt, system_message)
            st.write(f"Generated SQL Query:\n{sql_result}")

            try:
                # Extract the actual SQL query from the response
                sql_query = extract_sql_query(sql_result)
                explanation_prompt = f"Explain how the following SQL query will be executed:\n{sql_query}"
                explanation = chat_with_assistant(explanation_prompt, system_message)
                st.write(f"Execution Explanation:\n{explanation}")
            except Exception as e:
                pass  # Do not show error messages
            st.session_state.chat_history.append({
                "user": prompt,
                "generator": sql_result
            })
        else:
            st.error(
                f"Table '{table_name}' not found in the uploaded data. Available tables are: {', '.join(st.session_state['sheets'].keys())}.")
    else:
        st.error("Please enter a prompt to generate an SQL query.")


# Function to extract the actual SQL query from the assistant's response
def extract_sql_query(response):
    lines = response.split('\n')
    for i, line in enumerate(lines):
        if "SELECT" in line.upper():
            return '\n'.join(lines[i:]).strip()
    return response


# Adjust prompt box and buttons
st.markdown("""
    <style>
        .stTextArea textarea {
            width: 700px;
        }
        .stButton button {
            width: 200px;
        }
    </style>
""", unsafe_allow_html=True)
