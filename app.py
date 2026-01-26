import sqlite3
import pandas as pd
import streamlit as st
from openai import OpenAI
import os                     # Added: For accessing system environment variables
from dotenv import load_dotenv # Added: For loading configurations from .env file

# Load environment variables from the .env file for security
load_dotenv()

# ==========================================
# Page Configuration
# ==========================================
st.set_page_config(page_title="SmartDB Insight Agent", page_icon="🤖", layout="centered")
st.title("🤖 SmartDB Insight Agent")
st.markdown("💬 **Natural Language Data Analytics | Powered by RAG + Agentic Self-Correction**")

# ==========================================
# Step 1: Database Setup (Ensuring persistence)
# ==========================================
@st.cache_resource
def setup_database():
    conn = sqlite3.connect('ecommerce.db')
    cursor = conn.cursor()
    # Create tables
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, status TEXT)')
    
    # Mock data insertion
    cursor.execute('INSERT OR IGNORE INTO users (id, name, age) VALUES (1, "Alice", 28), (2, "Bob", 35), (3, "Charlie", 22)')
    cursor.execute('INSERT OR IGNORE INTO orders (id, user_id, amount, status) VALUES (1, 1, 1500.0, "paid"), (2, 2, 800.0, "paid"), (3, 1, 1200.0, "shipped")')
    conn.commit()
    conn.close()

setup_database()

# ==========================================
# Step 2: AI Client Configuration (Secure)
# ==========================================
client = OpenAI(
    # Fetching the API Key from environment variables (Best Practice)
    api_key=os.getenv("ZHIPU_API_KEY"),
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

# RAG Knowledge Base: Defining Schema & Business Logic
db_schema_knowledge = """
【Table 1】users: id, name, age (Business Rule: Users with age > 30 are VIPs)
【Table 2】orders: id, user_id, amount, status
"""

# ==========================================
# Step 3: Core Agent Logic & UI
# ==========================================
user_question = st.chat_input("Enter your query (e.g., 'Who are the VIP users and how much did they spend?')")

if user_question:
    with st.chat_message("user"):
        st.write(user_question)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        status_placeholder.info("🤖 Agent is reasoning and generating SQL...")

        system_prompt = f"""
        You are a specialized SQL Analyst. Generate SQLite queries based on this context:
        {db_schema_knowledge}
        
        Rules:
        1. Output ONLY the raw SQL code.
        2. No Markdown formatting.
        3. Translate business concepts (like VIP) into logical filters as defined.
        """
        
        chat_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ]
        
        max_retries = 3
        success = False

        # --- Self-Correction Loop ---
        for attempt in range(1, max_retries + 1):
            response = client.chat.completions.create(model="glm-4-flash", messages=chat_history)
            sql_query = response.choices[0].message.content.replace("```sql", "").replace("```", "").strip()
            
            st.code(sql_query, language="sql")

            conn = sqlite3.connect('ecommerce.db')
            try:
                df = pd.read_sql_query(sql_query, conn)
                status_placeholder.success(f"✅ Success! Found {len(df)} records.")
                st.dataframe(df, use_container_width=True)
                conn.close()
                success = True
                break

            except Exception as e:
                error_msg = str(e)
                st.warning(f"⚠️ Attempt {attempt} failed: {error_msg}. Initiating self-correction...")
                
                # Feedback to the LLM
                chat_history.append({"role": "assistant", "content": sql_query})
                chat_history.append({"role": "user", "content": f"The SQL failed: {error_msg}. Please fix the syntax and provide pure SQL."})
                conn.close()
        
        if not success:
            status_placeholder.error("💥 Agent failed to resolve the query after 3 attempts.")