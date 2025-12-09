from flask import Flask, render_template_string, request
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# HTTP 요청 시 인증서 검증 경고를 방지 (Render 환경에서는 필요 없을 수 있으나 안전을 위해 포함)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


app = Flask(__name__)

# [기상청 API 설정]
AUTH_KEY = "6cM_QKR5T2KDP0CkeU9i-w" # 사용자님의 인증키를 그대로 사용
TARGET_STATIONS = ['140', '886']

# HTML 디자인 (직관적인 UI)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>군산 적설 데이터 조회</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: sans-serif; padding: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 900px; margin: auto; }
        table { width: 100%; border-collapse: collapse; margin-top: 25px; background: white; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
        th, td { border: 1px solid #e0e0e0; padding: 15px; text-align: center; }
        th { background-color: #007bff; color: white; font-weight: 600; }
        tr:nth-child(even) { background-color: #f8f8f8; }
        tr:hover { background-color: #e9f5ff; }
        .header { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h1 { color: #007bff; margin-top: 0; font-size: 24px; }
        p { color: #666; }
        form { margin-top: 15px; display: flex; gap: 10px; align-items: center; }
        input[type="text"] { padding: 10px; border: 1px solid #ccc; border-radius: 4px; flex-grow: 1; }
        button { padding: 10px 15px; background-color: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; transition: background-color 0.3s; }
        button:hover { background-color: #218838; }
        .no-data { text-align: center; color: #dc3545; margin-top: 30px; font-size: 1.1em; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>❄️ 군산 지역 적설 데이터 조회</h1>
            <p>제작자: 군산공항 김영진</p>
            <form method="get">
                조회 날짜 (YYYYMMDD): <input type="text" name="date" placeholder="YYYYMMDD" value="{{ today }}">
                <button type="submit">조회하기</button>
            </form>
        </div>
        {% if results %}
            <table>
                <thead>
                    <tr>
                        <th>시간</th><th>지역</th><th>총 쌓인 눈 (cm)</th><th>새로 내린 눈 (cm)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in results %}
                    <tr>
                        <td>{{ row.hour }}:00</td><td>{{ row.name }}</td><td>{{ row.tot }}</td><td>{{ row.day }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <div class="no-data">
                데이터를 불러오지 못했거나, 해당 날짜의 데이터가 없습니다.
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

# API 통신 함수: requests timeout을 3초로 단축하여 웹 타임아웃 방지
def fetch_single_data(tm):
    url_tot = f"https://apihub.kma.go.kr/api/typ01/url/kma_snow1.php?sd=tot&tm={tm}&help=0&authKey={AUTH_KEY}"
    url_day = f"https://apihub.kma.go.kr/api/typ01/url/kma_snow1.php?sd=day&tm={tm}&help=0&authKey={AUTH_KEY}"
    res_dict = {stn: {'tot': '-', 'day': '-'} for stn in TARGET_STATIONS}
    
    # [핵심 수정] 타임아웃을 3초로 설정
    REQUEST_TIMEOUT = 3 
    
    try:
        rt = requests.get(url_tot, timeout=REQUEST_TIMEOUT).text
        rd = requests.get(url_day, timeout=REQUEST_TIMEOUT).text
        
        for line in rt.split('\n'):
            if not line.startswith('#') and len(line.split(',')) > 2:
                parts = line.split(',')
                if parts[1].strip() in TARGET_STATIONS: res_dict[parts[1].strip()]['tot'] = parts[-2].strip()
        for line in rd.split('\n'):
            if not line.startswith('#') and len(line.split(',')) > 2:
                parts = line.split(',')
                if parts[1].strip() in TARGET_STATIONS: res_dict[parts[1].strip()]['day'] = parts[-2].strip()
    except requests.exceptions.Timeout:
        # API 응답 지연 시 '-' 반환
        pass
    except Exception:
        # 기타 오류 발생 시 '-' 반환
        pass
        
    return tm[8:10], res_dict

@app.route('/')
def index():
    now = datetime.now()
    today = now.strftime("%Y%m%d")
    target_date = request.args.get('date', today)
    
    end_hour = now.hour if target_date == today else 23
    hours = [f"{target_date}{h:02d}00" for h in range(end_hour + 1)]
    
    # [핵심 수정] 워커 수를 10개로 늘려 병렬 처리 속도 개선
    with ThreadPoolExecutor(max_workers=10) as exec:
        data = list(exec.map(fetch_single_data, hours))
    
    data.sort(key=lambda x: x[0])
    
    final_results = []
    has_data = False
    
    for hour, res in data:
        for stn in TARGET_STATIONS:
            name = "군산" if stn == '140' else "군산산단"
            result_tot = res[stn]['tot']
            result_day = res[stn]['day']
            
            # 실제 값이 있다면 데이터 존재 플래그 설정
            if result_tot != '-' or result_day != '-':
                 has_data = True
                 
            final_results.append({'hour': hour, 'name': name, 'tot': result_tot, 'day': result_day})
    
    # 데이터가 아예 없을 경우 (모두 '-') 빈 리스트 반환
    if not has_data and all(r['tot'] == '-' and r['day'] == '-' for r in final_results):
        final_results = None

    return render_template_string(HTML_TEMPLATE, results=final_results, today=target_date)

# Gunicorn이 Render 환경에서 서버를 실행하므로, 아래 __name__ == '__main__' 블록은 실행되지 않습니다.
# 테스트를 위해 로컬에서 돌릴 때만 사용됩니다.
# if __name__ == '__main__':
#     app.run(debug=True)
