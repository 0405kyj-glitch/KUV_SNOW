from flask import Flask, render_template_string, request, jsonify
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# [기상청 API 설정]
AUTH_KEY = "6cM_QKR5T2KDP0CkeU9i-w"
STATION_MAP = {
    'gunsan': '140',
    'gunsansandan': '886'
}
STATION_NAME_MAP = {
    '140': '군산',
    '886': '군산산단'
}

# HTML/JavaScript 템플릿 (지점 선택 UI 추가)
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
        #controls { margin-top: 15px; display: flex; flex-direction: column; gap: 10px; align-items: stretch; }
        .control-row { display: flex; gap: 10px; align-items: center; }
        .radio-group { flex-grow: 1; display: flex; gap: 20px; align-items: center; }
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
            display: none;
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
                <div class="control-row">
                    조회 날짜: <input type="date" id="targetDate" max="{{ today }}" value="{{ today }}">
                </div>
                <div class="control-row">
                    지점 선택:
                    <div class="radio-group">
                        <label><input type="radio" name="stationSelect" value="gunsan" checked> 군산</label>
                        <label><input type="radio" name="stationSelect" value="gunsansandan"> 군산산단</label>
                    </div>
                </div>
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
            const stationKey = document.querySelector('input[name="stationSelect"]:checked').value;
            
            if (!dateInput) {
                alert('조회 날짜를 선택해 주세요.');
                return;
            }

            const yyyymmdd = dateInput.replace(/-/g, '');
            const resultsArea = document.getElementById('resultsArea');
            const spinner = document.getElementById('loadingSpinner');

            resultsArea.innerHTML = '';
            spinner.style.display = 'block';

            try {
                const response = await fetch(`/api/snow?date=${yyyymmdd}&station=${stationKey}`);
                const data = await response.json();

                spinner.style.display = 'none';

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
                
                // 단일 지점 데이터이므로 별도의 그룹화 로직이 필요 없습니다.
                for (let i = 0; i < data.length; i++) {
                    const row = data[i];
                    
                    tableHTML += `
                        <tr>
                            <td>${row.hour}:00</td><td>${row.name}</td><td>${row.tot}</td><td>${row.day}</td>
                        </tr>
                    `;
                }

                tableHTML += `
                        </tbody>
                    </table>
                `;
                resultsArea.innerHTML = tableHTML;

            } catch (error) {
                spinner.style.display = 'none';
                console.error('Fetch error:', error);
                resultsArea.innerHTML = `<div class="no-data">데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.</div>`;
            }
        }
    </script>
</body>
</html>
"""

# API 통신 함수: 단일 지점 ID를 인수로 받습니다.
def fetch_data_for_time(tm, sd, target_stn_id):
    url = f"https://apihub.kma.go.kr/api/typ01/url/kma_snow1.php?sd={sd}&tm={tm}&help=0&authKey={AUTH_KEY}"
    
    # API 응답 지연 문제를 해결하기 위해 타임아웃을 15초로 설정
    REQUEST_TIMEOUT = 15 
    
    try:
        # SSL 인증서 검증 활성화 (verify=False 제거됨)
        response = requests.get(url, timeout=REQUEST_TIMEOUT) 
        response.raise_for_status()
        
        data = response.text
        
        for line in data.split('\n'):
            if not line.startswith('#') and len(line.split(',')) > 2:
                parts = line.split(',')
                stn = parts[1].strip()
                # 요청한 단일 지점 ID만 확인
                if stn == target_stn_id: 
                    return parts[-2].strip() 
                    
    except requests.exceptions.RequestException:
        pass # 에러 발생 시 로그를 남기지 않고 패스
        
    return '-' # 실패 또는 데이터 미확인 시 기본값 반환


@app.route('/')
def home():
    """초기 접속 화면"""
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template_string(HTML_TEMPLATE, today=today)

@app.route('/api/snow')
def get_snow_data():
    """선택된 지점의 적설 데이터를 가져오는 API 엔드포인트"""
    target_date = request.args.get('date')
    station_key = request.args.get('station')
    
    if not target_date or not station_key:
        return jsonify({'error': '날짜 또는 지점 매개변수가 필요합니다.'}), 400

    if station_key not in STATION_MAP:
         return jsonify({'error': '유효하지 않은 지점 선택입니다.'}), 400

    target_stn_id = STATION_MAP[station_key]
    target_stn_name = STATION_NAME_MAP[target_stn_id]
    
    now = datetime.now()
    today_str = now.strftime("%Y%m%d")
    
    try:
        end_hour = now.hour if target_date == today_str else 23
        hours = [f"{target_date}{h:02d}00" for h in range(end_hour + 1)]
    except ValueError:
        return jsonify({'error': '유효하지 않은 날짜 형식입니다.'}), 400

    # 병렬 처리용 매개변수 목록 생성
    task_params = []
    for h in hours:
        task_params.append((h, 'tot', target_stn_id))
        task_params.append((h, 'day', target_stn_id))
    
    # ThreadPoolExecutor를 사용하여 병렬 처리 (워커 수 2개 유지)
    futures = {}
    with ThreadPoolExecutor(max_workers=2) as exec:
        for tm, sd, stn_id in task_params:
            future = exec.submit(fetch_data_for_time, tm, sd, stn_id)
            futures[(tm, sd)] = future

    # 결과를 시간(tm)과 유형(sd: tot/day)별로 정리
    combined_data = {}
    for (tm, sd), future in futures.items():
        val = future.result() 
        
        if tm not in combined_data:
            combined_data[tm] = {'tot': '-', 'day': '-'}
            
        combined_data[tm][sd] = val

    final_results = []
    sorted_times = sorted(combined_data.keys())
    
    # 단일 지점의 시간 순서대로 최종 결과 생성
    for tm in sorted_times:
        hour = tm[8:10]
        data_at_tm = combined_data[tm]
        
        final_results.append({
            'hour': hour,
            'name': target_stn_name,
            'tot': data_at_tm['tot'],
            'day': data_at_tm['day']
        })
    
    return jsonify(final_results)
