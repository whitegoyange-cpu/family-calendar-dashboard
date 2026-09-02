import streamlit as st
import datetime
import calendar
import json
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =======================================================
# 1. 화면 및 CSS 스타일 정의 (세로형 스마트 액자)
# =======================================================
st.set_page_config(
    page_title="가족 스마트 캘린더 액자",
    page_icon="🖼️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 5분(300초)마다 화면을 자동 갱신
st.markdown("""
    <meta http-equiv="refresh" content="300">
    <style>
        .stApp { background-color: #000000; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; padding-left: 0.5rem; padding-right: 0.5rem; max-width: 650px; }
        header { visibility: hidden; }
        footer { visibility: hidden; }

        .photo-frame {
            position: relative;
            width: 100%;
            height: 380px;
            border-radius: 12px;
            background-size: cover;
            background-position: center;
            box-shadow: inset 0 -80px 80px rgba(0,0,0,0.85);
            margin-bottom: 8px;
            display: flex;
            align-items: flex-end;
            padding: 20px;
            box-sizing: border-box;
        }
        .overlay-container { display: flex; justify-content: space-between; align-items: flex-end; width: 100%; }
        .time-text { font-size: 3.2rem; font-weight: 300; line-height: 1; text-shadow: 0 2px 10px rgba(0,0,0,0.9); }
        .date-text { font-size: 1.1rem; opacity: 0.9; margin-top: 4px; text-shadow: 0 2px 8px rgba(0,0,0,0.9); }
        .weather-container { text-align: right; text-shadow: 0 2px 8px rgba(0,0,0,0.9); }
        .weather-temp { font-size: 2.8rem; font-weight: 300; line-height: 1; }
        .weather-desc { font-size: 1rem; opacity: 0.85; margin-top: 4px; }

        .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 6px; }
        .cal-th { color: #8E8E93; text-align: center; padding: 6px 0; font-size: 0.85rem; font-weight: 600; border-bottom: 1px solid #2C2C2E; }
        .cal-th.sun { color: #FF453A; }
        .cal-th.sat { color: #0A84FF; }
        .cal-td { height: 75px; vertical-align: top; border-bottom: 1px solid #1C1C1E; padding: 3px; }
        .cal-td.today { background: radial-gradient(circle at 14px 14px, #FF3B30 11px, transparent 12px); font-weight: bold; }
        .cal-td.other-month { opacity: 0.2; }
        .day-num { font-size: 0.85rem; margin-bottom: 2px; }
        .day-num.sun { color: #FF453A; }
        .day-num.sat { color: #0A84FF; }

        .event-chip {
            border-radius: 3px;
            padding: 1px 4px;
            font-size: 0.65rem;
            margin-bottom: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
            line-height: 1.2;
        }

        div[data-testid="stButton"] button {
            background-color: #1C1C1E;
            color: #E5E5EA;
            border: 1px solid #3A3A3C;
            border-radius: 8px;
            padding: 2px 10px;
            font-size: 0.85rem;
        }
    </style>
""", unsafe_allow_html=True)

# =======================================================
# 2. 인증 및 캘린더 연동 설정
# =======================================================
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

CALENDARS = {
    '공휴일':      {'id': 'ko.south_korea#holiday@group.v.calendar.google.com', 'color': '#FF453A', 'text': '#FFF'},
    '공용(H&K)': {'id': 'whitegoyange@gmail.com', 'color': '#20C997', 'text': '#000'},
    '아빠':      {'id': '88fd898ea7cbaeb8bbf70103be22ff505fb04927b3de105a6f58e8326c7b50ff@group.calendar.google.com', 'color': '#339AF0', 'text': '#FFF'},
    '엄마':      {'id': '7f7dcf46619e31f3b6e69580cf25d3d6640fabe540159eacc88206fa1e730d83@group.calendar.google.com', 'color': '#FF7043', 'text': '#FFF'},
    '정원':      {'id': '51db02c009dbbe3a69fdf61d28cdc458f242dcd29260cb981f3384793d5b4ad8@group.calendar.google.com', 'color': '#CC5DE8', 'text': '#FFF'},
    '정빈':      {'id': 'f26677e78b93cb2afd0c5d67dde8a0eec92515055a5b9883b6d3ac6fe9c5e0ae@group.calendar.google.com', 'color': '#FCC419', 'text': '#000'},
    '현정':      {'id': 'b84e8e332f6f1a2b8013db4f92da306faf29bfbce33d882e4cebdbaa96d4b7ad@group.calendar.google.com', 'color': '#51CF66', 'text': '#000'},
}

@st.cache_resource
def get_service():
    # 1. 클라우드 배포 환경(Secrets) 확인 시도
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = json.loads(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
            return build('calendar', 'v3', credentials=creds)
    except Exception:
        pass

    # 2. 로컬 환경인 경우 service_account.json 직접 파일 로드
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
                # 시작 날짜 및 종료 날짜 파싱
                start_raw = item['start'].get('date') or item['start'].get('dateTime')
                end_raw = item['end'].get('date') or item['end'].get('dateTime')
                if not start_raw:
                    continue

                s_date = datetime.datetime.fromisoformat(start_raw.replace('Z', '+00:00')).date()
                
                # 종료일 처리 (구글 캘린더 '종일 일정'은 종료일이 다음 날 00시로 잡힘)
                if end_raw:
                    e_date = datetime.datetime.fromisoformat(end_raw.replace('Z', '+00:00')).date()
                    if 'T' not in end_raw:  # 종일 일정인 경우 마지막 날 포함 조정
                        e_date = e_date - datetime.timedelta(days=1)
                else:
                    e_date = s_date

                # 현재 보고 있는 월의 범위와 겹치는 기간 계산
                curr_month_start = datetime.date(year, month, 1)
                curr_month_end = datetime.date(year, month, last_day)
                
                actual_start = max(s_date, curr_month_start)
                actual_end = min(e_date, curr_month_end)

                # 시작일부터 종료일까지 모든 날짜에 일정 추가
                cur = actual_start
                while cur <= actual_end:
                    d_key = cur.strftime("%Y-%m-%d")
                    if d_key not in events_by_date:
                        events_by_date[d_key] = []
                    events_by_date[d_key].append({
                        'name': name,
                        'summary': item.get('summary', '일정'),
                        'color': info['color'],
                        'text': info['text']
                    })
                    cur += datetime.timedelta(days=1)

        except Exception:
            continue
            
    return events_by_date

# =======================================================
# 3. 경기도 안산 날씨 및 일 단위 감성 풍경 사진 로드
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
        return f"{temp}°", f"{desc} {icon}"
    except Exception:
        return "--°", "맑음 ☀️"

def get_daily_landscape_photo():
    """오늘 날짜 문자열(예: 2026-09-02)을 시드로 사용하여 하루 동안 고정된 감성 풍경 사진 제공"""
    today_str = datetime.date.today().isoformat()
    # 800x600 고화질 풍경 사진 (하루 동안 동일 유지, 자정 넘어가면 변경)
    return f"https://picsum.photos/seed/nature-{today_str}/800/600"

# =======================================================
# 4. 상단 액자 (일일 감성 풍경 + 시계 + 안산 날씨)
# =======================================================
now = datetime.datetime.now()
temp_str, weather_status = get_ansan_weather()
bg_img_url = get_daily_landscape_photo()

time_str = now.strftime("%I:%M")
date_str = now.strftime("%A, %B %d")

st.markdown(f"""
    <div class="photo-frame" style="background-image: url('{bg_img_url}');">
        <div class="overlay-container">
            <div>
                <div class="time-text">{time_str}</div>
                <div class="date-text">{date_str}</div>
            </div>
            <div class="weather-container">
                <div class="weather-temp">{temp_str}</div>
                <div class="weather-desc">{weather_status}</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# =======================================================
# 5. 월간 이동 네비게이션 컨트롤
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

c_title, c_prev, c_today, c_next = st.columns([3.5, 1, 1, 1])
with c_title:
    st.markdown(f"<strong style='font-size:1.15rem;'>{st.session_state.view_year}년 {st.session_state.view_month}월</strong>", unsafe_allow_html=True)
with c_prev:
    st.button("◀", on_click=prev_month)
with c_today:
    st.button("오늘", on_click=reset_today)
with c_next:
    st.button("▶", on_click=next_month)

# =======================================================
# 6. 하단 캘린더 매트릭스 렌더링
# =======================================================
events_map = get_month_events(st.session_state.view_year, st.session_state.view_month)
cal = calendar.Calendar(firstweekday=6)
month_days = cal.monthdayscalendar(st.session_state.view_year, st.session_state.view_month)

cal_html = '<table class="cal-table">'
cal_html += '<thead><tr>'
cal_html += '<th class="cal-th sun">S</th><th class="cal-th">M</th><th class="cal-th">T</th><th class="cal-th">W</th><th class="cal-th">T</th><th class="cal-th">F</th><th class="cal-th sat">S</th>'
cal_html += '</tr></thead><tbody>'

for week in month_days:
    cal_html += '<tr>'
    for col_idx, day in enumerate(week):
        # 이번 달에 속하지 않는 빈 칸 처리
        if day == 0:
            cal_html += '<td class="cal-td other-month"></td>'
            continue

        # 1) 오늘 날짜(YYYY-MM-DD) 문자열 생성 및 오늘 여부 체크
        d_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day:02d}"
        is_today = (st.session_state.view_year == real_today.year and 
                    st.session_state.view_month == real_today.month and 
                    day == real_today.day)
        
        # 2) 해당 일자에 '공휴일' 일정이 있는지 검사
        has_holiday = False
        if d_str in events_map:
            has_holiday = any(ev['name'] == '공휴일' for ev in events_map[d_str])

        # 3) 셀(칸) 스타일 지정 (오늘 날짜 강조 테두리)
        td_cls = "cal-td today" if is_today else "cal-td"
        
        # 4) 숫자 색상 지정: 일요일(col_idx == 0)이거나 공휴일이면 빨간색(day-num sun) 적용
        if col_idx == 0 or has_holiday:
            num_cls = "day-num sun"
        elif col_idx == 6:
            num_cls = "day-num sat"
        else:
            num_cls = "day-num"

        # 5) HTML 날짜 칸 및 숫자 출력
        cal_html += f'<td class="{td_cls}">'
        cal_html += f'<div class="{num_cls}">{day}</div>'

        # 6) 해당 날짜의 일정 뱃지(공휴일 포함) 출력
        if d_str in events_map:
            # 공휴일이 먼저 눈에 띄도록 공휴일 일정을 맨 위로 정렬
            sorted_events = sorted(events_map[d_str], key=lambda x: 0 if x['name'] == '공휴일' else 1)
            
            for ev in sorted_events:
                # 공휴일은 이름 없이 명칭만 깔끔하게, 가족 일정은 [이름] 포함 출력
                label = ev["summary"] if ev["name"] == '공휴일' else f'[{ev["name"]}] {ev["summary"]}'
                chip = f'<span class="event-chip" style="background-color: {ev["color"]}; color: {ev["text"]};" title="{label}">'
                chip += f'{label}'
                chip += '</span>'
                cal_html += chip

        cal_html += '</td>'
    cal_html += '</tr>'

cal_html += '</tbody></table>'
st.markdown(cal_html, unsafe_allow_html=True)
