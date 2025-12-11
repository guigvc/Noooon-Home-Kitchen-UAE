import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import time

# ==========================================
# ⚙️ 1. 配置区
# ==========================================
st.set_page_config(page_title="Noon 选品看板", layout="wide", page_icon="🌍")

st.markdown('<div id="top_anchor"></div>', unsafe_allow_html=True)

# ⚠️ 本地运行请确认路径正确
DATA_FILE = r"E:\ZHX\Noon Intel\noon_data.parquet"

if 'selected_category_state' not in st.session_state:
    st.session_state.selected_category_state = None
if 'scroll_trigger_id' not in st.session_state:
    st.session_state.scroll_trigger_id = 0

# ==========================================
# 📂 2. 数据读取
# ==========================================
@st.cache_data
def load_data():
    try:
        df = pd.read_parquet(DATA_FILE)
        
        if '类目' in df.columns: df['Target_Category'] = df['类目']
        elif '所属类目' in df.columns: df['Target_Category'] = df['所属类目']
        else: st.error("缺少类目列"); st.stop()

        if '国家' not in df.columns: df['国家'] = '阿联酋'

        cols_to_fix = ['销量数字', '评论数', '价格', '评分', '排名']
        for col in cols_to_fix:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"读取失败: {e}")
        return pd.DataFrame()

df_raw = load_data()
if df_raw.empty: st.stop()

# ==========================================
# 🌍 3. 国家筛选
# ==========================================
st.sidebar.header("🌍 区域选择")
available_countries = df_raw['国家'].unique().tolist()
default_idx = 0
if "阿联酋" in available_countries: default_idx = available_countries.index("阿联酋")

selected_country = st.sidebar.radio(
    "请选择目标市场：",
    options=available_countries,
    index=default_idx,
    horizontal=True
)

df = df_raw[df_raw['国家'] == selected_country].copy()

currency_symbol = "AED"
if selected_country == "沙特": currency_symbol = "SAR"
elif selected_country == "阿联酋": currency_symbol = "AED"

st.sidebar.markdown("---")

# ==========================================
# 🧮 4. 数据聚合 (新增评论数统计)
# ==========================================
base_stats = df.groupby('Target_Category').agg(
    产品总数=('产品名', 'count'),
    类目总销量=('销量数字', 'sum'),
    类目总评论=('评论数', 'sum') # <--- 新增这一行
).reset_index()

def get_top10_sum(group):
    return group.nlargest(10, '销量数字')['销量数字'].sum()

top10_stats = df.groupby('Target_Category').apply(get_top10_sum).reset_index(name='Top10销量总和')
category_stats = pd.merge(base_stats, top10_stats, on='Target_Category')

# ==========================================
# 🎨 5. 筛选与排序 (核心修改区)
# ==========================================
st.sidebar.header("🔍 筛选与排序")

# ⭐ 新增：排序方式选择
sort_mode = st.sidebar.radio(
    "类目方块排序依据：",
    ["按总销量 (热度)", "按总评论数 (沉淀)"],
    index=0
)

st.sidebar.markdown("---")

min_products = st.sidebar.slider("类目最少产品数", 0, int(category_stats['产品总数'].max()), 10)
min_sales = st.sidebar.slider("类目最少总销量", 0, int(category_stats['类目总销量'].max()), 0)

# 筛选
filtered_cats_df = category_stats[
    (category_stats['产品总数'] >= min_products) & 
    (category_stats['类目总销量'] >= min_sales)
]

# ⭐ 执行排序逻辑
if sort_mode == "按总销量 (热度)":
    filtered_cats_df = filtered_cats_df.sort_values(by='类目总销量', ascending=False)
else:
    filtered_cats_df = filtered_cats_df.sort_values(by='类目总评论', ascending=False)

valid_categories = filtered_cats_df['Target_Category'].tolist()
df_filtered = df[df['Target_Category'].isin(valid_categories)]

# ==========================================
# 📊 6. 总看板
# ==========================================
st.title(f"Noon畅销榜看板 - {selected_country}站")

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 筛选后类目", f"{len(valid_categories)}")
c2.metric("🛒 商品总数", f"{len(df_filtered):,}")
c3.metric("🔥 累计总销量", f"{filtered_cats_df['类目总销量'].sum():,}")
c4.metric("💬 累计总评论", f"{filtered_cats_df['类目总评论'].sum():,}") # 新增指标
st.markdown("---")

# ==========================================
# 🔲 7. 类目矩阵 (动态显示内容)
# ==========================================
st.subheader(f"📋 {selected_country} - 类目矩阵")
st.caption(f"当前排序：{sort_mode}")

cols_per_row = 5
rows = [valid_categories[i:i + cols_per_row] for i in range(0, len(valid_categories), cols_per_row)]

for row_cats in rows:
    cols = st.columns(cols_per_row)
    for index, cat_name in enumerate(row_cats):
        cat_data = filtered_cats_df[filtered_cats_df['Target_Category'] == cat_name].iloc[0]
        
        # ⭐ 动态决定方块显示什么数据
        if "销量" in sort_mode:
            metric_text = f"🔥 Top10销量: {int(cat_data['Top10销量总和']):,}"
        else:
            metric_text = f"💬 总评论数: {int(cat_data['类目总评论']):,}"

        with cols[index]:
            label = f"**{cat_name}**\n\n🛒 {cat_data['产品总数']} | {metric_text}"
            if st.button(label, key=cat_name, use_container_width=True):
                st.session_state.selected_category_state = cat_name
                st.session_state.scroll_trigger_id = time.time() 

# 自动滚屏脚本
if st.session_state.scroll_trigger_id > 0:
    js = f"""
    <script>
        var element = window.parent.document.getElementById("detail_anchor");
        if (element) {{
            element.scrollIntoView({{behavior: "smooth", block: "start"}});
        }}
    </script>
    """
    components.html(js, height=0)

# ==========================================
# 🕵️ 8. 类目详细透视
# ==========================================
st.markdown("---")
st.markdown('<div id="detail_anchor"></div>', unsafe_allow_html=True) 
st.header("🔎 类目详细透视")

current_cat = st.session_state.selected_category_state
if current_cat not in valid_categories:
    current_cat = valid_categories[0] if valid_categories else None

if current_cat:
    # 这里的排序依然保持按“排名”或“销量”排，因为看单品还是看热度比较多
    subset = df[df['Target_Category'] == current_cat].sort_values(by='排名', ascending=True)
    
    st.markdown(f"### 📦 当前展示: <span style='color:#FF4B4B'>{current_cat}</span> ({selected_country})", unsafe_allow_html=True)
    
    view_mode = st.radio("👀 选择查看模式", ["大图清单模式 (推荐)", "紧凑表格模式"], horizontal=True)

    if "大图清单" in view_mode:
        st.info("💡 提示：此模式下图片最大，适合观察产品外观细节。")
        for _, row in subset.iterrows():
            with st.container(border=True):
                col_img, col_info = st.columns([1, 4])
                with col_img:
                    if row['原图链接'] and row['原图链接'].startswith('http'):
                        st.image(row['原图链接'], use_container_width=True)
                    else:
                        st.text("无图")
                with col_info:
                    st.markdown(f"### [#{row['排名']}] {row['产品名']}({row['商品链接']})")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("价格", f"{row['价格']} {currency_symbol}") 
                    m2.metric("评分", f"{row['评分']} ⭐ ({int(row['评论数'])})")
                    m3.metric("近期销量", f"{int(row['销量数字'])}")
                    m4.markdown(f"**销量描述:** {row['销量描述']}")
                    
                    sales_val = int(row['销量数字'])
                    max_val = int(df['销量数字'].max())
                    progress_val = min(sales_val / max_val, 1.0) if max_val > 0 else 0
                    st.progress(progress_val, text=f"全站热度占比: {int(progress_val*100)}%")
    else:
        possible_cols = ['排名', '原图链接', '产品名', '价格', '评分', '评论数', '销量数字', '销量描述', '商品链接']
        final_cols = [c for c in possible_cols if c in subset.columns]
        st.dataframe(
            subset[final_cols],
            column_config={
                "原图链接": st.column_config.ImageColumn("图片", width="large"),
                "商品链接": st.column_config.LinkColumn("链接", display_text="去购买"),
                "销量数字": st.column_config.ProgressColumn("热度", format="%d", min_value=0, max_value=int(df['销量数字'].max())),
                "价格": st.column_config.NumberColumn(f"价格 ({currency_symbol})", format="%.2f"), 
            },
            use_container_width=True,
            height=1000,
            hide_index=True
        )
else:
    st.warning(f"👈 该国家 ({selected_country}) 下没有符合筛选条件的数据")

# ==========================================
# ⬆️ 9. 回到顶部按钮
# ==========================================
st.markdown("---")
col_b1, col_b2, col_b3 = st.columns([1, 2, 1])

with col_b2:
    if st.button("⬆️ 回到顶部 (选择其他类目)", use_container_width=True):
        js_top = """
        <script>
            var element = window.parent.document.getElementById("top_anchor");
            if (element) {
                element.scrollIntoView({behavior: "smooth", block: "start"});
            }
        </script>
        """
        components.html(js_top, height=0)