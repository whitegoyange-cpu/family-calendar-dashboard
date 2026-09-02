import streamlit as st
import datetime
import calendar
import json
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =======================================================
# 1. 화면 기본 설정 (와이드 전체폭 레이아웃)
# =======================================================
st.set_page_config(
    page_title="가족 와이드 캘린더",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 5분(300초) 자동 새로고침 및 가로 전체화면 최적화 CSS
st.markdown("""
    <meta http-equiv="refresh" content="300">
    <style>
        /* 기본 여백 완전 제거 및 다크 테마 */
        .stApp { background-color: #0B0E14; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .block-container {
            padding-top: 0.3rem !important;
            padding-bottom: 0.2rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            max-width: 100% !important;
        }
        header { visibility: hidden; }
        footer { visibility: hidden; }

        /* 상단 컴팩트 헤더 띠 (화면 높이 8% 수준) */
        .top-banner {
            position: relative;
            width: 100%;
            height: 62px;
            border-radius: 8px;
            background-size: cover;
            background-position: center;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            box-shadow: inset 0 0 100px rgba(0,0,0,0.85);
            margin-bottom: 6px;
            border: 1px solid #1F2430;
        }
        .header-left { display: flex; align-items: baseline; gap: 12px; }
        .time-text { font-size: 1.9rem; font-weight: 400; line-height: 1; letter-spacing: -0.5px; }
        .date-text { font-size: 0.95rem; opacity: 0.85; }
        .weather-box { font-size: 1.15rem; font-weight: 400; opacity: 0.9; }

        /* 가로 화면 가득 차는 테이블 */
        .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 2px; }
        .cal-th { color: #8F9BA8; text-align: center; padding: 6px 0; font-size: 0.85rem; font-weight: 600; border-bottom: 1px solid #232936; background-color: #12161F; }
        .cal-th.sun { color: #FF5252; }
        .cal-th.sat { color: #448AFF; }
        
        /* 세로 셀 높이를 넉넉하게 확장 (일정 가독성 확보) */
        .cal-td {
            height: 112px;
            vertical-align: top;
            border: 1px solid #1E232F;
            padding: 4px;
            background-color: #12151D;
        }
        .cal-td.today {
            background-color: #161C28;
            border: 2px solid #2979FF;
        }
        .cal-td.other-month { opacity: 0.2; background-color: #0B0E14; }
        .day-num { font-size: 0.85rem; font-weight: bold; margin-bottom: 3px; }
        .day-num.sun { color: #FF5252; }
        .day-num.sat { color: #448AFF; }

        /* 일정 태그 칩 */
        .event-chip {
            border-radius: 4px;
            padding: 2px 5px;
            font-size: 0.72rem;
            margin-bottom: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
            line-height: 1.25;
            font-weight: 500;
        }

        /* 버튼 및 상단 네비게이션 정렬 */
        div[data-testid="stButton"] button {
            background-color: #161B26;
            color: #E2E8F0;
            border: 1px solid #2D3748;
            border-radius: 6px;
            padding: 2px 10px;
            height: 32px;
            font-size: 0.85rem;
        }
        div[data-testid="stButton"] button:hover {
            border-color: #448AFF;
            color: #448AFF;
        }
        .legend-inline { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; margin-top: 4px; }
        .legend-dot { width: 9px; height: 9px; border-radius: 2px; display: inline-block; margin-right: 3px; }
    </style>
""", unsafe_allow_html=True)

# =======================================================
# 2. 구글 캘린더 연동 및 인증 설정
# =======================================================
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

CALENDARS = {
    '공용(H&K)': {'id': 'whitegoyange@gmail.com', 'color': '#20C997', 'text': '#000'},
    '아빠':      {'id': '88fd898ea7cbaeb8bbf70103be22ff505fb04927b3de105a6f58e8326c7b50ff@group.calendar.google.com', 'color': '#339AF0', 'text': '#FFF'},
    '엄마':      {'id': '7f7dcf46619e31f3b6e69580cf25d3d6640fabe540159eacc88206fa1e730d83@group.calendar.google.com', 'color': '#FF6B6B', 'text': '#FFF'},
    '정원':      {'id': '51db02c009dbbe3a69fdf61d28cdc458f242dcd29260cb981f3384793d5b4ad8@group.calendar.google.com', 'color': '#CC5DE8', 'text': '#FFF'},
    '정빈':      {'id': 'f26677e78b93cb2afd0c5d67dde8a0eec92515055a5b9883b6d3ac6fe9c5e0ae@group.calendar.google.com', 'color': '#FCC419', 'text': '#000'},
    '현정':      {'id': 'b84e8e332f6f1a2b8013db4f92da306faf29bfbce33d882e4cebdbaa96d4b7ad@group.calendar.google.com', 'color': '#51CF66', 'text': '#000'},
}

@st.cache_resource
def get_service():
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = json.loads(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
            return build('calendar', 'v3', credentials=creds)
    except Exception:
        pass
    creds = service_account.Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

def get_month_events(year, month):
    service = get_service()
    start_dt = datetime.datetime(year, month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    end_dt = datetime.datetime(year, month, last_day, 23, 59, 59, tzinfo=datetime.timezone.utc)

    events_by_date = {}
    for name, info in CALENDARS.items():
        if '@' not in info['id']:
            continue
        try:
            res = service.events().list(
                calendarId=info['id'],
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            for item in res.get('items', []):
                start = item['start'].get('dateTime', item['start'].get('date'))
                date_key = start[:10]
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                events_by_date[date_key].append({
                    'name': name,
                    'summary': item.get('summary', '일정'),
                    'color': info['color'],
                    'text': info['text']
                })
        except Exception:
            continue
    return events_by_date

# =======================================================
# 3. 경기도 안산 날씨 및 일일 풍경 배너
# =======================================================
def get_ansan_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=37.3219&longitude=126.8309&current_weather=true"
        r = requests.get(url, timeout=3).json()
        curr = r.get('current_weather', {})
        temp = round(curr.get('temperature', 20))
        code = curr.get('weathercode', 0)
        
        if code == 0:
            desc, icon = "맑음", "☀️"
        elif code in [1, 2, 3]:
            desc, icon = "구름 조금", "⛅"
        elif code in [45, 48]:
            desc, icon = "안개", "🌫️"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81]:
            desc, icon = "비", "🌧️"
        elif code in [71, 73, 75, 85]:
            desc, icon = "눈", "❄️"
        elif code >= 95:
            desc, icon = "뇌우", "⛈️"
        else:
            desc, icon = "흐림", "☁️"
        return f"{temp}°C", f"{desc} {icon}"
    except Exception:
        return "--°C", "맑음 ☀️"

def get_daily_banner_photo():
    today_str = datetime.date.today().isoformat()
    return f"https://picsum.photos/seed/nature-{today_str}/1400/200"

# =======================================================
# 4. 상단 미니멀 띠 배너 (시간 / 날짜 / 안산 날씨)
# =======================================================
now = datetime.datetime.now()
temp_str, weather_status = get_ansan_weather()
bg_url = get_daily_banner_photo()

time_str = now.strftime("%H:%M")
date_str = now.strftime("%Y년 %m월 %d일 (%a)")

st.markdown(f"""
    <div class="top-banner" style="background-image: url('{bg_url}');">
        <div class="header-left">
            <div class="time-text">{time_str}</div>
            <div class="date-text">{date_str}</div>
        </div>
        <div class="weather-box">안산 {temp_str} &nbsp;{weather_status}</div>
    </div>
""", unsafe_allow_html=True)

# =======================================================
# 5. 월간 네비게이션 컨트롤 및 색상 범례 한 줄 배치
# =======================================================
real_today = datetime.date.today()
if 'view_year' not in st.session_state:
    st.session_state.view_year = real_today.year
if 'view_month' not in st.session_state:
    st.session_state.view_month = real_today.month

def prev_month():
    if st.session_state.view_month == 1:
        st.session_state.view_month = 12
        st.session_state.view_year -= 1
    else:
        st.session_state.view_month -= 1

def next_month():
    if st.session_state.view_month == 12:
        st.session_state.view_month = 1
        st.session_state.view_year += 1
    else:
        st.session_state.view_month += 1

def reset_today():
    st.session_state.view_year = real_today.year
    st.session_state.view_month = real_today.month

c_title, c_legend, c_prev, c_today, c_next = st.columns([1.8, 4.2, 0.6, 0.6, 0.6])

with c_title:
    st.markdown(f"<strong style='font-size:1.25rem;'>🗓️ {st.session_state.view_year}년 {st.session_state.view_month}월</strong>", unsafe_allow_html=True)

with c_legend:
    legend_html = '<div class="legend-inline">'
    for name, info in CALENDARS.items():
        legend_html += f'<span><span class="legend-dot" style="background-color: {info["color"]};"></span>{name}</span>'
    legend_html += '</div>'
    st.markdown(legend_html, unsafe_allow_html=True)

with c_prev:
    st.button("◀", on_click=prev_month, use_container_width=True)
with c_today:
    st.button("오늘", on_click=reset_today, use_container_width=True)
with c_next:
    st.button("▶", on_click=next_month, use_container_width=True)

# =======================================================
# 6. 와이드 월간 달력 렌더링
# =======================================================
events_map = get_month_events(st.session_state.view_year, st.session_state.view_month)
cal = calendar.Calendar(firstweekday=6)
month_days = cal.monthdayscalendar(st.session_state.view_year, st.session_state.view_month)

cal_html = '<table class="cal-table">'
cal_html += '<thead><tr>'
cal_html += '<th class="cal-th sun">일 (SUN)</th><th class="cal-th">월 (MON)</th><th class="cal-th">화 (TUE)</th><th class="cal-th">수 (WED)</th><th class="cal-th">목 (THU)</th><th class="cal-th">금 (FRI)</th><th class="cal-th sat">토 (SAT)</th>'
cal_html += '</tr></thead><tbody>'

for week in month_days:
    cal_html += '<tr>'
    for col_idx, day in enumerate(week):
        if day == 0:
            cal_html += '<td class="cal-td other-month"></td>'
            continue

        d_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day:02d}"
        is_today = (st.session_state.view_year == real_today.year and 
                    st.session_state.view_month == real_today.month and 
                    day == real_today.day)
        
        td_cls = "cal-td today" if is_today else "cal-td"
        num_cls = "day-num sun" if col_idx == 0 else ("day-num sat" if col_idx == 6 else "day-num")

        cal_html += f'<td class="{td_cls}">'
        cal_html += f'<div class="{num_cls}">{day}</div>'

        if d_str in events_map:
            for ev in events_map[d_str]:
                chip = f'<span class="event-chip" style="background-color: {ev["color"]}; color: {ev["text"]};" title="[{ev["name"]}] {ev["summary"]}">'
                chip += f'[{ev["name"]}] {ev["summary"]}'
                chip += '</span>'
                cal_html += chip

        cal_html += '</td>'
    cal_html += '</tr>'

cal_html += '</tbody></table>'
st.markdown(cal_html, unsafe_allow_html=True)
