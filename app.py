from flask import Flask, render_template_string, request, jsonify
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import urllib3

# SSL 인증서 경고 무시 설정 유지
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# [기상청 API 설정]
AUTH_KEY = "6cM_QKR5T2KDP0CkeU9i-w"
# 두 지점을 순서대로 정의 (140: 군산, 886: 군산산단)
TARGET_STATIONS = ['140', '886'] 

# HTML/JavaScript 템플릿 (로딩바, 버튼 기반 조회 기능 포함)
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
        #controls { margin-top: 15px; display: flex; gap: 10px; align-items: center; }
        input[type="date"] { padding: 10px; border: 1px solid #ccc; border-radius: 4px; flex-grow: 1; }
        button { padding: 10px 15px; background-color: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; transition: background-color 0.3s; }
        button:hover { background-color: #218838; }
        .no-data { text-align: center; color: #dc3545; margin-top: 30px; font-size: 1.1em; font-weight: bold; }
        
        /* 로딩 스피너 디자인 */
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
            display: none; /* 초기에는 숨김 */
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>❄️ 군산 지역 적설 데이터 조회</h1>
            <p>제작자: 군산공항 김영진</p>
            <div id="controls">
                조회 날짜: <input type="date" id="targetDate" max="{{ today }}" value="{{ today }}">
                <button onclick="fetchData()">조회하기</button>
            </div>
        </div>
        
        <div id="loadingSpinner" class="spinner"></div>
        <div id="resultsArea">
            </div>

    </div>

    <script>
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('targetDate').value = today;

        async function fetchData() {
            const dateInput = document.getElementById('targetDate').value;
            if (!dateInput) {
                alert('조회 날짜를 선택해 주세요.');
                return;
            }

            const yyyymmdd = dateInput.replace(/-/g, '');
            const resultsArea = document.getElementById('resultsArea');
            const spinner = document.getElementById('loadingSpinner');

            resultsArea.innerHTML = '';
            spinner.style.display = 'block'; // 로딩바 표시

            try {
                // Flask API 엔드포인트 호출
                const response = await fetch(`/api/snow?date=${yyyymmdd}`);
                const data = await response.json();

                spinner.style.display = 'none'; // 로딩바 숨김

                if (data.error) {
                    resultsArea.innerHTML = `<div class="no-data">${data.error}</div>`;
                    return;
                }
                
                if (!data.length || data.every(row => row.tot === '-' && row.day === '-')) {
                    resultsArea.innerHTML = `<div class="no-data">해당 날짜의 데이터가 없습니다.</div>`;
                    return;
                }

                // 테이블 생성
                let tableHTML = `
                    <table>
                        <thead>
                            <tr>
                                <th>시간</th><th>지역</th><th>총 쌓인 눈 (cm)</th><th>새로 내린 눈 (cm)</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                // 데이터 그룹화 및 순서 조정 (140, 886 붙여서 출력)
                for (let i = 0; i < data.length; i += 2) {
                    const row140 = data[i]; // 군산 (140)
                    const row886 = data[i+1]; // 군산산단 (886)
                    
                    if (row140.hour === row886.hour) {
                        // 군산 140 출력
                        tableHTML += `
                            <tr>
                                <td>${row140.hour}:00</td><td>${row140.name}</td><td>${row140.tot}</td><td>${row140.day}</td>
                            </tr>
                        `;
                        // 군산산단 886 출력
                        tableHTML += `
                            <tr>
                                <td>${row886.hour}:00</td><td>${row886.name}</td><td>${row886.tot}</td><td>${row886.day}</td>
                            </tr>
                        `;
                    }
                }

                tableHTML += `
                        </tbody>
                    </table>
                `;
                resultsArea.innerHTML = tableHTML;

            } catch (error) {
                spinner.style.display = 'none'; // 로딩바 숨김
                console.error('Fetch error:', error);
                resultsArea.innerHTML = `<div class="no-data">데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.</div>`;
            }
        }
        
        // 페이지 로드 시 자동 조회 방지 (버튼 클릭 기반으로 전환)
        // window.onload = fetchData;
    </script>
</body>
</html>
"""

# [개선된] API 통신 함수: 두 지점의 데이터를 한 번의 API 요청으로 처리
def fetch_data_for_time(tm, sd):
    url = f"https://apihub.kma.go.kr/api/typ01/url/kma_snow1.php?sd={sd}&tm={tm}&help=0&authKey={AUTH_KEY}"
    res_data = {stn: '-' for stn in TARGET_STATIONS}
    
    REQUEST_TIMEOUT = 5 # 넉넉하게 5초로 설정
    
    try:
        # verify=False로 SSL 오류 방지
        response = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False)
        response.raise_for_status() # HTTP 오류 시 예외 발생
        
        data = response.text
        
        for line in data.split('\n'):
            if not line.startswith('#') and len(line.split(',')) > 2:
                parts = line.split(',')
                stn = parts[1].strip()
                if stn in TARGET_STATIONS: 
                    # 데이터는 끝에서 두 번째 필드
                    res_data[stn] = parts[-2].strip()
                    
    except requests.exceptions.RequestException as e:
        # 타임아웃, 연결 오류, HTTP 오류 등 발생 시 모든 값 '-' 처리
        print(f"API Request failed for {tm}, {sd}: {e}")
        pass
        
    return res_data


@app.route('/')
def home():
    """초기 접속 화면 (빈 화면 및 UI만 표시)"""
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template_string(HTML_TEMPLATE, today=today)

@app.route('/api/snow')
def get_snow_data():
    """JS 요청에 따라 데이터를 가져오는 API 엔드포인트"""
    target_date = request.args.get('date')
    
    if not target_date:
        return jsonify({'error': '날짜(date) 매개변수가 필요합니다.'}), 400

    now = datetime.now()
    today_str = now.strftime("%Y%m%d")
    
    try:
        # 요청된 날짜가 오늘 날짜인 경우, 현재 시간까지만 조회
        end_hour = now.hour if target_date == today_str else 23
        hours = [f"{target_date}{h:02d}00" for h in range(end_hour + 1)]
    except ValueError:
        return jsonify({'error': '유효하지 않은 날짜 형식입니다.'}), 400

    # 병렬 처리: 총적설(tot)과 신적설(day) 데이터를 한 번에 가져오기
    results = {}
    
    # 24시간 전체 요청 시간 목록을 [time, time, ... ] 형태에서 [(time, 'tot'), (time, 'day'), ...] 형태로 확장
    task_params = []
    for h in hours:
        task_params.append((h, 'tot'))
        task_params.append((h, 'day'))
    
    # [성능 개선] API 요청 횟수를 줄이는 방식이므로, 워커 수는 4개 (Render의 CPU 코어 수)로 유지
    with ThreadPoolExecutor(max_workers=4) as exec:
        # 각 시간에 대해 tot, day 데이터를 병렬 요청
        responses = list(exec.map(lambda p: (p[0], p[1], fetch_data_for_time(p[0], p[1])), task_params))
        
    # 결과를 시간(tm)과 지점(stn)별로 정리
    combined_data = {}
    for tm, sd, res_data in responses:
        if tm not in combined_data:
            combined_data[tm] = {'140': {'tot': '-', 'day': '-'}, '886': {'tot': '-', 'day': '-'}}
            
        for stn, val in res_data.items():
            combined_data[tm][stn][sd] = val

    final_results = []
    
    # 데이터 정렬: 시간 순서로, 같은 시간 내에서는 140, 886 순서로 정렬
    sorted_times = sorted(combined_data.keys())
    
    for tm in sorted_times:
        hour = tm[8:10]
        data_by_stn = combined_data[tm]
        
        # 140 (군산) 데이터 추가
        final_results.append({
            'hour': hour,
            'name': '군산',
            'tot': data_by_stn['140']['tot'],
            'day': data_by_stn['140']['day']
        })
        
        # 886 (군산산단) 데이터 추가
        final_results.append({
            'hour': hour,
            'name': '군산산단',
            'tot': data_by_stn['886']['tot'],
            'day': data_by_stn['886']['day']
        })
    
    return jsonify(final_results)

# if __name__ == '__main__':
#     app.run(debug=True)
