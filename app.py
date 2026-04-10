import streamlit as st
import gspread
import google.generativeai as genai
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Smart Health Assistant", page_icon="🥗", layout="wide")

st.session_state.is_offline = False

@st.cache_resource
def get_gspread_client():
    try:
        if "gcp_service_account" not in st.secrets: return None
        if st.secrets["gcp_service_account"].get("project_id") == "your-project-id": return None
        credentials = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(credentials)
        return gc
    except Exception:
        return None

@st.cache_resource
def init_gemini():
    try:
        if "gemini" not in st.secrets: return None
        key = st.secrets["gemini"].get("api_key")
        if not key or key == "YOUR_GEMINI_API_KEY": return None
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception:
        return None

gc = get_gspread_client()
gemini_model = init_gemini()
ws_goals = None
ws_meals = None

if gc is not None:
    try:
        SHEET_URL = st.secrets["spreadsheet"]["url"]
        sh = gc.open_by_url(SHEET_URL)
        ws_goals = sh.worksheet("goals")
        ws_meals = sh.worksheet("meals")
    except Exception:
        st.session_state.is_offline = True
else:
    st.session_state.is_offline = True

if 'today' not in st.session_state:
    st.session_state.today = datetime.now().strftime("%Y-%m-%d")
    
if 'offline_goals' not in st.session_state:
    st.session_state.offline_goals = {"calories": 2000, "protein": 150, "carbs": 250, "fat": 60, "dietary_prefs": "None"}
if 'offline_meals' not in st.session_state:
    st.session_state.offline_meals = []

def fetch_goals():
    if st.session_state.is_offline or ws_goals is None:
        return st.session_state.offline_goals
    try:
        records = ws_goals.get_all_records()
        if not records: return {"calories": 2000, "protein": 150, "carbs": 250, "fat": 60, "dietary_prefs": "None"}
        return records[0]
    except Exception:
        return st.session_state.offline_goals

def save_goals(cal, pro, carb, fat, prefs):
    if st.session_state.is_offline or ws_goals is None:
        st.session_state.offline_goals = {"calories": cal, "protein": pro, "carbs": carb, "fat": fat, "dietary_prefs": prefs}
        return
        
    try:
        ws_goals.update('A2:F2', [["user_1", cal, pro, carb, fat, prefs]])
    except Exception:
        st.session_state.offline_goals = {"calories": cal, "protein": pro, "carbs": carb, "fat": fat, "dietary_prefs": prefs}

def fetch_meals():
    if st.session_state.is_offline or ws_meals is None:
        records = st.session_state.offline_meals
    else:
        try:
            records = ws_meals.get_all_records()
        except Exception:
            records = st.session_state.offline_meals
            
    df = pd.DataFrame(records)
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.date
        cols_to_num = ['calories', 'protein', 'carbs', 'fat']
        for col in cols_to_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    else:
        df = pd.DataFrame(columns=['date', 'meal_name', 'calories', 'protein', 'carbs', 'fat', 'meal_type'])
    return df

def log_new_meal(date_str, name, cal, pro, carb, fat, meal_type):
    new_row = {"date": date_str, "meal_name": name, "calories": cal, "protein": pro, "carbs": carb, "fat": fat, "meal_type": meal_type}
    if st.session_state.is_offline or ws_meals is None:
        st.session_state.offline_meals.append(new_row)
        return
        
    try:
        ws_meals.append_row([date_str, name, cal, pro, carb, fat, meal_type])
    except Exception:
        st.session_state.offline_meals.append(new_row)

user_goals = fetch_goals()
df_meals = fetch_meals()

if 'dietary_prefs' not in st.session_state:
    st.session_state.dietary_prefs = user_goals.get("dietary_prefs", "None")

def get_swap_suggestion(meal_name, preferences):
    if gemini_model is None:
        return f"[Offline Mode] Suggestion: Instead of {meal_name}, try a Grilled Chicken Salad. It's better for your {preferences} diet!"
        
    prompt = f"The user wants to eat: {meal_name}. They have the following dietary preferences/restrictions: {preferences}. Suggest ONE single healthier alternative."
    try:
        with st.spinner("Gemini is thinking..."):
            response = gemini_model.generate_content(prompt)
            return response.text
    except Exception:
        return f"[Error connecting to Gemini] Please check standard API keys."

def get_smart_insight(recent_meals_df, preferences):
    if gemini_model is None:
        return "[Offline Mode] Insight: You seem to be logging less protein than your daily goal! Try adding some more lean meats today."
        
    if recent_meals_df.empty: return "Not enough data yet."
    
    recent_records = recent_meals_df.tail(15).to_dict('records')
    prompt = f"Preferences: {preferences}. Meals: {recent_records}. Provide ONE short actionable Smart Insight."
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception:
        return "Insights unavailable at the moment."

with st.sidebar:
    st.title("⚙️ Settings & Goals")
    
    if st.session_state.is_offline or gemini_model is None:
        st.warning("⚠️ **Offline Mode Active**: Using local memory instead of Cloud servers.")

    st.subheader("Your Saved Daily Goals")
    with st.form("goals_form"):
        cal_goal = st.number_input("Calories", min_value=500, max_value=5000, value=int(user_goals.get("calories", 2000)))
        pro_goal = st.number_input("Protein (g)", min_value=10, max_value=400, value=int(user_goals.get("protein", 150)))
        carb_goal = st.number_input("Carbs (g)", min_value=10, max_value=600, value=int(user_goals.get("carbs", 250)))
        fat_goal = st.number_input("Fat (g)", min_value=10, max_value=250, value=int(user_goals.get("fat", 60)))
        
        dietary_prefs = st.text_input("Diet / Allergies", value=str(user_goals.get("dietary_prefs", "None")))
        
        save_btn = st.form_submit_button("Save Goals")
        
        if save_btn:
            save_goals(cal_goal, pro_goal, carb_goal, fat_goal, dietary_prefs)
            st.session_state.dietary_prefs = dietary_prefs
            st.success("Goals Saved successfully!")
            st.rerun()

st.title("🥗 Smart Food & Health Assistant")

today_date_obj = datetime.strptime(st.session_state.today, "%Y-%m-%d").date()
if not df_meals.empty:
    df_today = df_meals[df_meals['date'] == today_date_obj]
else:
    df_today = pd.DataFrame(columns=['calories', 'protein', 'carbs', 'fat'])

today_cal = df_today['calories'].sum() if not df_today.empty else 0
today_pro = df_today['protein'].sum() if not df_today.empty else 0
today_carb = df_today['carbs'].sum() if not df_today.empty else 0
today_fat = df_today['fat'].sum() if not df_today.empty else 0

remaining_cal = max(0, cal_goal - today_cal)
cal_percentage = min(100, int((today_cal / cal_goal) * 100)) if cal_goal > 0 else 0

st.subheader("📈 Today's Overview")
metrics_cols = st.columns(4)
metrics_cols[0].metric("Calories Consumed", f"{int(today_cal)} kcal", f"-{int(remaining_cal)} rem", delta_color="inverse")
metrics_cols[1].metric("Protein", f"{int(today_pro)}g", f"{int(pro_goal)}g goal")
metrics_cols[2].metric("Carbs", f"{int(today_carb)}g", f"{int(carb_goal)}g goal")
metrics_cols[3].metric("Fat", f"{int(today_fat)}g", f"{int(fat_goal)}g goal")

st.progress(cal_percentage / 100, text=f"{cal_percentage}% of Daily Calorie Goal")
st.divider()

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("🥧 Macro Breakdown")
    macro_data = pd.DataFrame({"Macro": ["Protein", "Carbs", "Fat"], "Grams": [today_pro, today_carb, today_fat]})
    if macro_data["Grams"].sum() > 0:
        fig_pie = px.pie(macro_data, names="Macro", values="Grams", color_discrete_sequence=['#ff9999', '#66b3ff', '#99ff99'])
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Log meals to see your macro breakdown!")

with chart_col2:
    st.subheader("📊 Calories per Meal Type")
    if not df_today.empty and 'meal_type' in df_today.columns:
        meal_type_grouped = df_today.groupby('meal_type')['calories'].sum().reset_index()
        fig_bar = px.bar(meal_type_grouped, x='meal_type', y='calories', color='meal_type', text_auto=True)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Log meals to see distributions!")

st.divider()

st.subheader("📅 Weekly Trend")
if not df_meals.empty:
    seven_days_ago = today_date_obj - timedelta(days=7)
    df_week = df_meals[df_meals['date'] >= seven_days_ago]
    if not df_week.empty:
        daily_cals = df_week.groupby('date')['calories'].sum().reset_index()
        daily_cals['date'] = daily_cals['date'].astype(str)
        daily_cals.set_index('date', inplace=True)
        st.line_chart(daily_cals['calories'])
    else:
        st.info("No meals logged recently.")

with st.expander("✨ Get AI Smart Insight", expanded=False):
    if st.button("Generate Insight"):
        insight_text = get_smart_insight(df_meals, st.session_state.dietary_prefs)
        st.success(f"**Insight:** {insight_text}")

st.divider()

log_col, swap_col = st.columns(2)

with log_col:
    st.subheader("➕ Log a Meal")
    with st.form("log_form"):
        meal_name = st.text_input("Meal Name", placeholder="E.g., Chicken Salad")
        meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
        
        c1, c2 = st.columns(2)
        meal_cal = c1.number_input("Calories", min_value=0, max_value=3000, value=0)
        meal_pro = c2.number_input("Protein (g)", min_value=0, max_value=200, value=0)
        
        c3, c4 = st.columns(2)
        meal_carb = c3.number_input("Carbs (g)", min_value=0, max_value=300, value=0)
        meal_fat = c4.number_input("Fat (g)", min_value=0, max_value=150, value=0)
        
        log_btn = st.form_submit_button("Add Meal")
        
        if log_btn:
            if meal_name.strip() == "":
                st.error("Please enter a meal name.")
            else:
                log_new_meal(st.session_state.today, meal_name, meal_cal, meal_pro, meal_carb, meal_fat, meal_type)
                st.success(f"Logged {meal_name}!")
                st.rerun()

with swap_col:
    st.subheader("🔄 AI Swap Suggestion")
    craving = st.text_input("What are you craving?", placeholder="E.g., Double Cheeseburger")
    if st.button("Find Healthier Swap"):
        if craving.strip() == "":
            st.warning("Please enter what you're craving first!")
        else:
            swap_text = get_swap_suggestion(craving, st.session_state.dietary_prefs)
            st.info(f"**Swap Suggestion:** {swap_text}")
