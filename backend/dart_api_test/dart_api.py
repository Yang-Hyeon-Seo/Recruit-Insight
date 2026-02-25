"""
dart api에서 여러 회사의 재무제표를 호출
해당 회사의 재무제표를 재무제표 종류별로 구분
BS와 IS(또는 CIS)의 주요 재무제표 데이터 분석
"""
import os, io, json, time
from dotenv import load_dotenv
import pandas as pd
import random
import xmltodict
import zipfile
import requests
from pprint import pprint


# ------------------ 함수 정의 -----------------------------
# 회사 데이터 가져오기 & 100개 회사 이름 및 회사 코드 `[(회사 이름, 회사 코드)]`` 형태로 반환
def get_company_data(DART_API_KEY):

    get_url = "https://opendart.fss.or.kr/api/corpCode.xml"

    params = {
        "crtfc_key": DART_API_KEY,
    }

    print("파일 다운로드 중")
    response = requests.get(get_url, params=params)  # API 호출

    if response.status_code != 200:
        return Response({"message": "저장실패"}, status.HTTP_502_BAD_GATEWAY)

    # 파일로 저장하지 않고, 메모리 상에서 바로 ZIP으로 인식
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        # io.BytesIO(response.content) : response.content 파일을 실제 있는 파일인 것처럼 만들어줌
        # 압축 파일 내 파일 목록 확인
        file_list = zip_ref.namelist()

        first_file_name = file_list[0] # 첫번째 파일 선택
        with zip_ref.open(first_file_name) as f:
            # 데이터 읽기
            xml_string = f.read().decode("utf-8")
            # print(xml_string)

    corp_dict = xmltodict.parse(xml_string)  # xml파일을 json 형태로 반환(타입은 딕셔너리)

    # API 결과에서 회사 리스트를 추출
    company_list = corp_dict.get("result").get("list")

    # 객체들을 리스트에 저장
    obj_list = []
    for item in company_list:  # 반복문 돌면서 객체 저장
        code = item.get("corp_code")
        name = item.get("corp_name")

        if code and name:  # 회사 코드와 회사 이름이 모두 존재한다면 리스트에 추가
            obj_list.append(
                (name, code)
            )

    return obj_list


def read_company_json():
    with open('../corp_sj_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 100개만 뽑아서 저장
    companies = [(item['fields']['corp_code'], item['fields']['corp_name']) for item in random.sample(data, 100)]

    return companies


def save_to_csv(data_list, filename):
    if data_list:
        df = pd.DataFrame(data_list)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f'{filename} 저장 완료')
    else:
        print(f'{filename}에 저장할 데이터 없음')

# ------------------ 실행 코드 -----------------------------

# DART API KEY 가져오기
load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")

ofs_cantcount = 0 # 재무제표가 없는 경우
cfs_cantcount = 0

# 0. 회사 데이터 가져오기
# companies = get_company_data(DART_API_KEY)
# select_100_companies = random.sample(companies, 100)
# pprint(select_100_companies)

# 1. 회사 표에서 100개의 회사를 중복 없이 랜덤으로 뽑기
companies = read_company_json()
pprint(companies)
save_to_csv(companies, 'companies_2024.csv') # 조회한 회사 저장

# 2. 각 회사의 재무제표 중 BS와 IS, CIS를 구분하여 저장

get_url = 'https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json'

BS = []
IS = []
CIS = []
CF = []

for i in range(100):
    # 회사 하나씩 dart에서 api 호출
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code" : companies[i][0],
        "bsns_year" : '2024',
        "reprt_code" : '11011',
        "fs_div" : "CFS", # "OFS"
    }

    response = requests.get(get_url, params=params)  # API 호출
    
    # 예외처리
    if response.status_code != 200:
        print("호출 오류", response.status_code)
        cfs_cantcount += 1 # 데이터를 찾을 수 없음
    else:
        data = response.json()

        if data["status"] != "000":
            print("재무제표 존재X", data)
            cfs_cantcount += 1 # 재무제표가 없음
            continue

        # 정상 호출
        for item in data['list']:
            item['corp_code'] = companies[i][0]
            item['corp_name'] = companies[i][1]

            sj_div = item.get('sj_div')
            if sj_div == 'BS':
                BS.append(item)
            elif sj_div == 'IS':
                IS.append(item)
            elif sj_div == 'CIS':
                CIS.append(item)
            elif sj_div == 'CF':
                CF.append(item)

        time.sleep(0.1)  # 혹시 API 막힐까봐 잠깐 휴식시키기 

        #pprint(data)
        # break


# -------------------OFS 시도 --------------------------
for i in range(100):
    # 회사 하나씩 dart에서 api 호출
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code" : companies[i][0],
        "bsns_year" : '2024',
        "reprt_code" : '11011',
        "fs_div" : "CFS", # "OFS"
    }

    response = requests.get(get_url, params=params)  # API 호출
    
    # 예외처리
    if response.status_code != 200:
        print("호출 오류", response.status_code)
        ofs_cantcount += 1 # 데이터를 찾을 수 없음
    else:
        data = response.json()

        if data["status"] != "000":
            print("재무제표 존재X", data)
            ofs_cantcount += 1 # 재무제표가 없음
            continue

        # 정상 호출
        for item in data['list']:
            item['corp_code'] = companies[i][0]
            item['corp_name'] = companies[i][1]

            sj_div = item.get('sj_div')
            if sj_div == 'BS':
                BS.append(item)
            elif sj_div == 'IS':
                IS.append(item)
            elif sj_div == 'CIS':
                CIS.append(item)
            elif sj_div == 'CF':
                CF.append(item)

        time.sleep(0.1)  # 혹시 API 막힐까봐 잠깐 휴식시키기 

        #pprint(data)
        # break

# -------------------------------------------------------


# 3. BS, IS, CIS 각각에 저장된 데이터들 확인 및 분석
# csv 파일로 반환
save_to_csv(BS, 'BS_2024.csv')
save_to_csv(IS, 'IS_2024.csv')
save_to_csv(CIS, 'CIS_2024.csv')
save_to_csv(CF, 'CF_2024.csv')
# 재무제표 없는 경우 몇개인지 출력
# print(cantcount)
print('CFS', cfs_cantcount)
print('OFS', ofs_cantcount)