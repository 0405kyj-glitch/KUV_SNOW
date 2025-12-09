from flask import Flask, render_template_string, request
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# [기상청 API 설정]
AUTH_KEY = "6cM_QKR5T2KDP0CkeU9i-w"
TARGET_STATIONS = ['140', '886']

# HTML 디자인 (직관적인 UI)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>군산 적설 데이터 조회</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background-color: #f4f4f9; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: center; }
        th { background-color: #007bff; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .header { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
</head>
<body>
    <div class="header">
        <h1>❄️ 군산 지역 적설 데이터 조회</h1>
        <p>제작자: 군산공항 김영진</p>
        <form method="get">
            조회 날짜: <input type="text" name="date" placeholder="YYYYMMDD" value="{{ today }}">
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
    {% endif %}
</body>
</html>
"""

def fetch_single_data(tm):
    url_tot = f"https://apihub.kma.go.kr/api/typ01/url/kma_snow1.php?sd=tot&tm={tm}&help=0&authKey={AUTH_KEY}"
    url_day = f"https://apihub.kma.go.kr/api/typ01/url/kma_snow1.php?sd=day&tm={tm}&help=0&authKey={AUTH_KEY}"
    res_dict = {stn: {'tot': '-', 'day': '-'} for stn in TARGET_STATIONS}
    try:
        # 웹 서버 환경은 보안망 제약이 없으므로 verify=True가 기본입니다.
        rt = requests.get(url_tot, timeout=5).text
        rd = requests.get(url_day, timeout=5).text
        for line in rt.split('\n'):
            if not line.startswith('#') and len(line.split(',')) > 2:
                parts = line.split(',')
                if parts[1].strip() in TARGET_STATIONS: res_dict[parts[1].strip()]['tot'] = parts[-2].strip()
        for line in rd.split('\n'):
            if not line.startswith('#') and len(line.split(',')) > 2:
                parts = line.split(',')
                if parts[1].strip() in TARGET_STATIONS: res_dict[parts[1].strip()]['day'] = parts[-2].strip()
    except: pass
    return tm[8:10], res_dict

@app.route('/')
def index():
    today = datetime.now().strftime("%Y%m%d")
    target_date = request.args.get('date', today)
    
    end_hour = datetime.now().hour if target_date == today else 23
    hours = [f"{target_date}{h:02d}00" for h in range(end_hour + 1)]
    
    with ThreadPoolExecutor(max_workers=5) as exec:
        data = list(exec.map(fetch_single_data, hours))
    
    data.sort(key=lambda x: x[0])
    
    final_results = []
    for stn in TARGET_STATIONS:
        name = "군산" if stn == '140' else "군산산단"
        for hour, res in data:
            final_results.append({'hour': hour, 'name': name, 'tot': res[stn]['tot'], 'day': res[stn]['day']})
            
    return render_template_string(HTML_TEMPLATE, results=final_results, today=today)

if __name__ == '__main__':
    app.run(debug=True)
