import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from fpdf import FPDF
import base64
from datetime import datetime

# [1. 데이터 및 설정]
KAKAO_API_KEY = "684158fbad0f42f98b384d4888a23d0b"
JINJU_SOLAR_SUBSIDY = 2300000 
ZEB_TAX_BENEFIT = 750000      

TECH_DELTAS = {
    "저탄소 콘크리트": {"cost": 5000000, "carbon": -8000, "energy_save": 0},
    "강화 단열": {"cost": 10000000, "carbon": -2000, "energy_save": 0.25},
    "태양광 발전": {"cost": 6000000, "carbon": -1500, "energy_save": 0.40}
}

# [2. 유틸리티 함수]
def calculate_elec_bill(kwh):
    if kwh <= 200: return 910 + (kwh * 120)
    elif kwh <= 400: return 1600 + (200 * 120) + ((kwh - 200) * 214)
    else: return 7300 + (200 * 120) + (200 * 214) + ((kwh - 400) * 307)

def estimate_kwh(bill_won):
    for kwh in range(0, 1501):
        if calculate_elec_bill(kwh) >= bill_won: return kwh
    return 1500

def create_pdf(report_data):
    pdf = FPDF()
    pdf.add_page()
    # 폰트 설정 (기본 폰트는 한글이 깨질 수 있어 영문 위주나 표준 설정 사용, 
    # 실제 환경에선 한글 폰트 경로 지정 필요. 여기선 구조 위주로 생성)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ZEB Construction Analysis Report", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 12)
    for key, value in report_data.items():
        pdf.cell(0, 10, f"{key}: {value}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- UI 레이아웃 ---
st.set_page_config(page_title="진주형 ZEB 컨설턴트", layout="wide")
st.title("진주시 단독주택 제로에너지(ZEB) 의사결정 시스템")

# [사이드바]
with st.sidebar:
    st.header("1. 기본 정보")
    address = st.text_input("건축 예정지 주소", "경상남도 진주시")
    current_bill = st.slider("현재 월평균 전기 요금 (원)", 10000, 300000, 80000, step=5000)
    area = st.number_input("건물 연면적 (㎡)", value=132) # 약 40평
    
    st.divider()
    st.header("2. 기술 선택 (B안)")
    chk_concrete = st.checkbox("저탄소 콘크리트 (LCA 개선)")
    chk_insulation = st.checkbox("강화 단열재 (패시브급)")
    chk_solar = st.checkbox("태양광 발전 (3kW)")

# [계산부]
current_kwh = estimate_kwh(current_bill)
ratio = area / 100
cost_a = 250000000 * ratio
carb_a = 45000 * ratio
eng_cost_a = current_bill * 12

extra_cost, applied_benefit, energy_indep = 0, 0, 0
selected_techs = []

if chk_concrete:
    extra_cost += 5000000; selected_techs.append("저탄소 콘크리트")
if chk_insulation:
    extra_cost += 10000000; energy_indep += 0.25; selected_techs.append("강화 단열")
if chk_solar:
    extra_cost += 6000000; applied_benefit += JINJU_SOLAR_SUBSIDY; energy_indep += 0.40; selected_techs.append("태양광 발전")

zeb_grade = "5등급" if energy_indep >= 0.20 else "미인증"
if energy_indep >= 0.60: zeb_grade = "1등급"
if zeb_grade != "미인증": applied_benefit += ZEB_TAX_BENEFIT

final_kwh = max((current_kwh * (0.75 if chk_insulation else 1.0)) - (300 if chk_solar else 0), 0)
eng_cost_b = calculate_elec_bill(final_kwh) * 12
real_saving = eng_cost_a - eng_cost_b
net_investment = extra_cost - applied_benefit
payback = net_investment / real_saving if real_saving > 0 else 0

# [메인 화면 시각화]
st.subheader(f"예상 ZEB 등급: {zeb_grade} (자립률 {energy_indep*100:.0f}%)")
st.progress(min(energy_indep/0.65, 1.0))

c1, c2, c3, c4 = st.columns(4)
c1.metric("정부/지자체 혜택", f"{applied_benefit/10000:,.0f} 만원")
c2.metric("실질 투자비", f"{net_investment/10000:,.0f} 만원")
c3.metric("연간 절감액", f"{real_saving/10000:,.1f} 만원")
c4.metric("투자 회수 기간", f"{payback:.1f} 년" if payback > 0 else "-")

st.divider()

col_left, col_right = st.columns(2)
with col_left:
    st.write("**20년 누적 비용 비교 (시공비 포함)**")
    years = list(range(0, 21))
    total_a = [cost_a + (eng_cost_a * y) for y in years]
    total_b = [(cost_a + net_investment) + (eng_cost_b * y) for y in years]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=total_a, name="표준 설계(A)", line=dict(color='gray', dash='dash')))
    fig.add_trace(go.Scatter(x=years, y=total_b, name="진주 맞춤형(B)", line=dict(color='#2ecc71', width=4)))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.write("**기술별 탄소 및 비용 상세**")
    df_tech = pd.DataFrame({
        "기술항목": ["저탄소콘크리트", "강화단열", "태양광발전"],
        "시공비": [500, 1000, 600],
        "에너지절감률(%)": [0, 25, 40]
    })
    st.table(df_tech)

# [데이터 출처 섹션]
with st.expander("데이터 산출 근거 및 API 참조 기준"):
    st.markdown("""
    - **위치 데이터:** Kakao Local API (진주시 행정구역 기준)
    - **전기 요금:** 한국전력공사 주택용 저압 요금표 (2024년 기준 누진제 적용)
    - **보조금:** 진주시 신재생에너지 보급 지원사업 (국비+지자체비 합산)
    - **ZEB 혜택:** 지방세특례제한법 제47조의2 (취득세 15% 감면 적용)
    - **환경 지표:** 국립산림과학원 주요 수종별 탄소흡수량 가이드라인
    """)

# [PDF 리포트 생성 및 다운로드]
report_content = {
    "Project Address": address,
    "Building Area": f"{area} m2",
    "Selected Technologies": ", ".join(selected_techs),
    "ZEB Grade": zeb_grade,
    "Total Government Benefit": f"{applied_benefit:,.0f} KRW",
    "Net Investment": f"{net_investment:,.0f} KRW",
    "Annual Saving": f"{real_saving:,.0f} KRW",
    "Payback Period": f"{payback:.1f} Years"
}

if st.button("분석 리포트 PDF 다운로드 (영문 기준)"):
    pdf_bytes = create_pdf(report_content)
    st.download_button(label="Click to Download PDF", data=pdf_bytes, file_name=f"ZEB_Report_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf")

st.success(f"현재 월 {current_bill:,.0f}원을 지불하시는 건축주님은 누진 구간 하락으로 인해 연간 {real_saving/10000:,.1f}만원의 이득을 보실 수 있습니다.")