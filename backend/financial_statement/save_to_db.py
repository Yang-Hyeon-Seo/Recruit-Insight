import os
import time

from dotenv import load_dotenv

from . import models
from .amount_clean import amount_clean
from .services.financial_services import call_dart_fnltt_singl_acnt_all


# env 파일의 DART API키 저장
load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")


def get_data(corp, bsns_year, reprt_code):
    # def get_data(request):
    """
    특정 기업 재무제표 데이터를 호출하는 함수

    변수 설명
    - corp_code : 기업 코드
    - bsns_year : 비즈니스 연도
    - reprt_code : 보고서 코드(1분기/반기/3분기/사업 보고서)
    fs_div라는 변수도 있는데, 우선 개별재무제표만 대상으로 하기 위해 OFS 값으로 할당

    1. DART API에서 데이터 호출
    2. pandas 이용하여 데이터 정제
    3. 재무 비율 계산 (재무비율도 모두 계산해서 DB에 한 번에 저장)
    4. DB 저장
    """
    start = time.time()
    # 1. DART API 데이터 호출 =====================================
    # get 호출이 아니라면 바로 return
    # if request.method != "GET":
    #     print("잘못된 호출입니다.")
    # return redirect("financial_statement:index")
    # get 호출인 경우

    # DART API 호출
    # 예외처리를 하지 않으면, 오타 발생 시 오류 발생
    # try:
    #     # 회사 코드 찾기
    #     corp_name = request.GET.get("corp_name")  # 회사 이름
    #     corp = models.CorpCode.objects.get(corp_name=corp_name)  # 회사 객체
    #     corp_code = corp.corp_code  # 회사 번호

    # except models.CorpCode.DoesNotExist:
    #     print("오류:", corp_name, "을 찾을 수 없습니다.")
    #     return redirect("financial_statement:index")

    # bsns_year = request.GET.get("bsns_year")
    # reprt_code = request.GET.get("reprt_code", "11011")

    # API 호출하기
    crtfc_key = DART_API_KEY
    fs_div = "OFS"  # OFS : 개별 재무제표
    corp_code = corp.corp_code

    response = call_dart_fnltt_singl_acnt_all(crtfc_key, bsns_year, reprt_code, fs_div, corp_code)

    if response.status_code != 200:
        print("호출 오류:", response.status_code)
        # return Response({"message": "호출 오류 발생"}, status.HTTP_502_BAD_GATEWAY)
        # return redirect("financial_statement:index")
        return False

    data = response.json()

    if data["status"] != "000":
        print("재무제표 호출 실패:", data)
        # return Response({"message": "재무제표 호출 실패"}, status.HTTP_404_NOT_FOUND)
        # return redirect("financial_statment:index")
        return False

    # # 정상 호출
    # # api 결과 json 파일로 저장------------------------------------------
    # print("json파일 작성 시작")
    # api_data_dir = os.path.join(settings.BASE_DIR, "api_data")
    # os.makedirs(api_data_dir, exist_ok=True)

    # code = data["list"][0].get("corp_code")
    # year = data["list"][0].get("bsns_year")
    # reprt = data["list"][0].get("reprt_code")

    # file_name = f"{code}{year}{reprt}.json"

    # json_path = os.path.join(api_data_dir, file_name)

    # with open(json_path, "w", encoding="utf-8") as f:
    #     json.dump(data, f, indent=4, ensure_ascii=False)
    # print("json파일 저장 완료")
    # # ---------------------------------------------------------

    # 데이터 DB 저장
    print("DB저장====================================")
    obj_list = []

    # 외래키 저장을 위한 변수 및 딕셔너리 생성
    sj_dict = {
        "BS": models.SjDiv.objects.get(sj_div="BS"),
        "IS": models.SjDiv.objects.get(sj_div="IS"),
        "CIS": models.SjDiv.objects.get(sj_div="CIS"),
        "CF": models.SjDiv.objects.get(sj_div="CF"),
        "SCE": models.SjDiv.objects.get(sj_div="SCE"),
    }

    # 결과 리스트의 공통된 값 저장
    base_year = int(data["list"][0].get("bsns_year"))
    reprt_code = data["list"][0].get("reprt_code")

    # 재무 비율 계산 위한 딕셔너리
    # 3년을 리스트로 만들어서 한 번에 3년치 계산하기
    fin_dict = [
        {
            "bsns_year": base_year,
            "corp_code": corp,  # 객체
            "reprt_code": reprt_code,
            "thstrm_nm": data["list"][0].get("thstrm_nm"),
            # 위의 코드들은 모든 행이 동일하니까 제일 앞에 있는 데이터 이용
        },
        {
            "bsns_year": base_year - 1,
            "corp_code": corp,  # 객체
            "reprt_code": reprt_code,
            "thstrm_nm": data["list"][0].get("frmtrm_nm"),
        },
        {
            "bsns_year": base_year - 2,
            "corp_code": corp,  # 객체
            "reprt_code": reprt_code,
            "thstrm_nm": data["list"][0].get("bfefrmtrm_nm"),
        },
    ]

    for item in data["list"]:
        # corp_code = item.get('corp_code')
        account_id = item.get("account_id")

        account_id = account_id.replace("ifrs_", "ifrs-full_")
        # print(account_id)

        account_nm = item.get("account_nm")
        account_detail = item.get("account_detail")
        sj_div = sj_dict.get(item.get("sj_div"))  # 딕셔너리에서 같은 값으로 찾아서 객체 저장
        currency = item.get("currency")

        # 당기 데이터
        if "thstrm_amount" in item:
            bsns_year = base_year
            thstrm_nm = item.get("thstrm_nm")
            thstrm_amount = item.get("thstrm_amount")
            thstrm_amount = amount_clean(thstrm_amount)

            obj_list.append(
                models.FinancialData(
                    corp_code=corp,
                    bsns_year=bsns_year,
                    account_id=account_id,
                    account_nm=account_nm,
                    account_detail=account_detail,
                    sj_div=sj_div,
                    thstrm_nm=thstrm_nm,
                    thstrm_amount=thstrm_amount,
                    currency=currency,
                    reprt_code=reprt_code,
                )
            )

            fin_dict[0].setdefault(account_id, thstrm_amount)

        # 전기 데이터
        if "frmtrm_amount" in item:
            bsns_year = base_year - 1
            thstrm_nm = item.get("frmtrm_nm")
            thstrm_amount = item.get("frmtrm_amount")
            thstrm_amount = amount_clean(thstrm_amount)

            obj_list.append(
                models.FinancialData(
                    corp_code=corp,
                    bsns_year=bsns_year,
                    account_id=account_id,
                    account_nm=account_nm,
                    account_detail=account_detail,
                    sj_div=sj_div,
                    thstrm_nm=thstrm_nm,
                    thstrm_amount=thstrm_amount,
                    currency=currency,
                    reprt_code=reprt_code,
                )
            )

            fin_dict[1].setdefault(account_id, thstrm_amount)

        # 전전기 데이터
        if "bfefrmtrm_amount" in item:
            bsns_year = base_year - 2
            thstrm_nm = item.get("bfefrmtrm_nm")
            thstrm_amount = item.get("bfefrmtrm_amount")
            thstrm_amount = amount_clean(thstrm_amount)

            obj_list.append(
                models.FinancialData(
                    corp_code=corp,
                    bsns_year=bsns_year,
                    account_id=account_id,
                    account_nm=account_nm,
                    account_detail=account_detail,
                    sj_div=sj_div,
                    thstrm_nm=thstrm_nm,
                    thstrm_amount=thstrm_amount,
                    currency=currency,
                    reprt_code=reprt_code,
                )
            )
            fin_dict[2].setdefault(account_id, thstrm_amount)

    if obj_list:
        models.FinancialData.objects.bulk_create(
            obj_list,
            ignore_conflicts=True,
            # update_conflicts=True,
            # unique_fields=["corp_code", "bsns_year", "account_id", "account_detail"],
            # update_fields=["account_nm", "thstrm_amount", "currency"]
        )
        print("데이터 저장")

    # 재무비율 계산----------------------------------------------------------------------------------------
    ratio_list = []

    for i in range(3):
        # 변수 선언
        equity = fin_dict[0].get("ifrs-full_Equity")  # 자본
        assets = fin_dict[0].get("ifrs-full_Assets")  # 자산
        current_liabilities = fin_dict[0].get("ifrs-full_CurrentLiabilities")  # 유동부채
        operating_income_loss = fin_dict[0].get("dart_OperatingIncomeLoss")  # 영업 이익
        profitloss = fin_dict[0].get("ifrs-full_ProfitLoss")  # 당기순이익(순손실)
        revenue = fin_dict[0].get("ifrs-full_Revenue")  # 매출액
        current_trade_receivables = fin_dict[0].get("ifrs-full_CurrentTradeReceivables")  # 매출채권

        # print(equity)
        # print(assets)
        # print(current_liabilities)
        # print(operating_income_loss)
        # print(profitloss)
        # print(revenue)
        # print(current_trade_receivables)

        # 자본 구성(15) (CapitalStructure)
        # 자기자본 비율 (capital adequacy ratio)
        if equity is not None and assets is not None and assets != 0:
            """
                자기자본 / 총자산 
                기업의 재무 상태가 얼마나 안전하고 튼튼한지 나타냄
                회사 전체 재산 중 빚 제외한 남은 돈이 얼마나 되는지
            """
            capital_adequacy_ratio = equity / assets

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="capital_adequacy_ratio",
                    ratio_nm="자기자본비율",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="capital_structure",
                    thstrm_amount=capital_adequacy_ratio,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 유동성(15) (Liquidity)
        # 유동비율 (current ratio) - 15
        if current_liabilities is not None and equity is not None and equity != 0:
            """
                유동부채 / 자본
                일반적으로 100% 이하라면 단기지급능력 부족함
                이론적인 유동비율의 목표 비율은 200% 이상
                유동비율의 문제점은 재고자산의 현금화 속도 및 현금화 가능성이 기업마다 다르기 때문에
                일률적으로 적용하는 데 무리가 있다는 것임
            """
            current_ration = current_liabilities / equity

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="current_ration",
                    ratio_nm="유동비율",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Liquidity",
                    thstrm_amount=current_ration,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 수익성(10) (Profitability)
        # 총자본영업이익률(ROA, Return on Assets)
        if operating_income_loss is not None and assets is not None and assets != 0:
            """
                영업이익 / 총자산(평균잔액)
                총자본 = 주주자본(자본) + 타인자본(부채)
                return은 영업이익 / 당기순이익 둘 다 될 수 있으나
                별도의 정의가 되어 있지 않다면 영업이익으로 간주해도 됨
            """

            roa = operating_income_loss / assets
            # 당기순이익 버전
            # ROA = fin_dict['ifrs-full_ProfitLoss'] / fin_dict['ifrs-full_Assets']

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="ROA",
                    ratio_nm="총자본영업이익률",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Profitability",
                    thstrm_amount=roa,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 자기자본순이익률(ROE, Return On Equity)
        if profitloss is not None and equity is not None and equity != 0:
            """
                (당기)순이익 / 자기자본(평균잔액)
                자기자본순이익률 > 주주의 요구수익률 -> 기업가치 성장
                자기자본순이익률 < 주주의 요구수익률 -> 기업의 가치 감소
                => 기업이 조달한 자기자본의 가치를 유지하기 위해 필요한 수익률 의미
            """

            roe = profitloss / equity

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="ROE",
                    ratio_nm="자기자본순이익률",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Profitability",
                    thstrm_amount=roe,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 총자본수익률 (ROI, Return on Investment)
        if profitloss is not None and assets is not None and assets != 0:
            """
                당기순이익 / 총자본(평균잔액)
                주주와 채권자가 투자한 자본에 대해 벌어들이는 수익성
                듀폰 시스템에서 매출수익성과 총자본회전속도가 결합된 비율로, 재무통제수단으로 이용함
            """

            roi = profitloss / assets

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="ROI",
                    ratio_nm="총자본수익률",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Profitability",
                    thstrm_amount=roi,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 매출액영업이익률 (Sales operating profit margin)
        if operating_income_loss is not None and revenue is not None and revenue != 0:
            """
                영업이익 / 매출액
            """
            sales_operating_profit_margin = operating_income_loss / revenue

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="sales_operating_profit_margin",
                    ratio_nm="매출액영업이익률",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Profitability",
                    thstrm_amount=sales_operating_profit_margin,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 활동성(5) (Efficiency)
        # 총자산회전율 (Total Assets Turnover)
        if revenue is not None and assets is not None and assets != 0:
            """
                매출액 / 총자산
                총자산 = 총자본 (크기 동일)
                기업이 보유하고 있는 총자산들을 얼마나 효과적으로 활용하고 있는지 측정
                기업의 총자산이 1년에 몇 번 회전했는가 의미
            """

            total_assets_turnover = revenue / assets

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="total_assets_turnover",
                    ratio_nm="총자산회전율",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Efficiency",
                    thstrm_amount=total_assets_turnover,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="회",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 매출채권회전율 (Receivables Turnover)
        if revenue is not None and current_trade_receivables is not None and current_trade_receivables != 0:
            """
                매출액 / 매출채권
                매출채권회전율이 높다 -> 매출채권 관리가 잘 되고 있음
                매출채권회전율이 낮다 -> 매출채권 관리에 문제가 있음
                매출채권회전기간 : 매출채권이 매출액으로 바뀌는데 걸리는 기간
                매출채권 : (실무적으로) 한 달에도 몇 번씩 거래하는 기업에서는 거래할 때마다 돈이 이동하는 것이 아니고
                    채권(돈을 받을 권리)로 기록했다가, 서로 약속한 특정한 날에 돈이 이동함
            """
            receivables_turnover = revenue / current_trade_receivables

            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="receivables_turnover",
                    ratio_nm="매출채권회전율",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Efficiency",
                    thstrm_amount=receivables_turnover,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="회",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        if i == 2:
            continue
        # 성장성(5) (Growth)
        # 이 부분은 전년도 지표가 들어가야 하기 때문에 0, 1번 인덱스에서만 계산
        # 총자본증가율 (total capital growth rate)
        last_assets = fin_dict[i + 1].get("ifrs-full_Assets")
        if assets is not None and last_assets is not None and last_assets != 0:
            total_capital_growth_rate = (assets / last_assets) - 1
            """
                (당기말 총자산 / 전기말 총자산) - 1
            """
            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="total_capital_growth_rate",
                    ratio_nm="총자본증가율",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Growth",
                    thstrm_amount=total_capital_growth_rate,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

        # 매출액증가율 (sales growth rate)
        last_revenue = fin_dict[i + 1].get("ifrs-full_Revenue")
        if revenue is not None and last_revenue is not None and last_revenue != 0:
            sales_growth_rate = (revenue / last_revenue) - 1
            """
                (당기 매출액 / 전기 매출액) - 1 
            """
            ratio_list.append(
                models.FinancialRatio(
                    bsns_year=fin_dict[i].get("bsns_year"),
                    ratio_id="sales_growth_rate",
                    ratio_nm="매출액증가율",
                    reprt_code=fin_dict[i].get("reprt_code"),
                    category="Growth",
                    thstrm_amount=sales_growth_rate,
                    thstrm_nm=fin_dict[i].get("thstrm_nm"),
                    unit="%",
                    corp_code=fin_dict[i].get("corp_code"),
                )
            )

    models.FinancialRatio.objects.bulk_create(ratio_list, ignore_conflicts=True)
    # -----------------------------------------------------------------------------------------------------------

    end = time.time()
    print(end - start, "초")
    # pprint(ratio_list)
    return True
    # return redirect("financial_statement:index")
