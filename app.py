from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import os
import re
import json
import requests
from datetime import datetime


# =========================================================
# 1. 기본 설정
# =========================================================

load_dotenv()

app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="frontend/static"
)

CORS(app)


# =========================================================
# 2. 환경변수 설정
# =========================================================

# 한양여대 API Gateway 설정
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://factchat-cloud.mindlogic.ai/v1/gateway"
)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5-mini")

# 공공데이터포털 목록조회 API 설정
PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY")
PUBLIC_DATA_API_URL = os.getenv(
    "PUBLIC_DATA_API_URL",
    "https://api.odcloud.kr/api/15077093/v1/dataset"
)

# Swagger 기준 dataset API 검색 조건
PUBLIC_DATA_SEARCH_PARAMS = [
    "cond[title::LIKE]",
    "cond[desc::LIKE]",
    "cond[keywords::LIKE]"
]

# Swagger 기준 page, perPage, returnType 사용
PUBLIC_DATA_PAGE_PARAM = os.getenv("PUBLIC_DATA_PAGE_PARAM", "page")
PUBLIC_DATA_SIZE_PARAM = os.getenv("PUBLIC_DATA_SIZE_PARAM", "perPage")
PUBLIC_DATA_TYPE_PARAM = os.getenv("PUBLIC_DATA_TYPE_PARAM", "returnType")
PUBLIC_DATA_TYPE_VALUE = os.getenv("PUBLIC_DATA_TYPE_VALUE", "JSON")

DEFAULT_NUM_ROWS = int(os.getenv("PUBLIC_DATA_NUM_ROWS", "20"))


# =========================================================
# 3. HTML 페이지 라우팅
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/input")
def input_page():
    return render_template("input.html")


@app.route("/explore")
def explore_page():
    return render_template("explore.html")


@app.route("/result")
def result_page():
    return render_template("result.html")


# =========================================================
# 4. 공통 유틸 함수
# =========================================================

def join_url(base_url, path):
    """
    base_url과 path를 안전하게 합치는 함수
    """
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def clean_text(value):
    """
    None, 숫자, 리스트 등이 들어와도 문자열로 안전하게 변환
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value).strip()


def parse_json_from_text(text):
    """
    LLM 응답에서 JSON만 추출하는 함수.
    LLM이 코드블록(```json)을 붙여도 처리 가능.
    """
    if not text:
        raise ValueError("LLM 응답이 비어 있습니다.")

    text = text.strip()

    # ```json ... ``` 제거
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    # 바로 JSON 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 본문 중 첫 JSON 객체 또는 배열 추출
    json_match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
    if not json_match:
        raise ValueError("LLM 응답에서 JSON을 찾지 못했습니다.")

    return json.loads(json_match.group(1))


def extract_choice_content(response_json):
    """
    OpenAI 호환 Chat Completions 응답에서 content 추출
    """
    # # 디버깅용: 응답 구조 확인
    # print("[LLM RAW RESPONSE]", json.dumps(response_json, ensure_ascii=False, indent=2)[:2000])
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("LLM 응답 형식이 예상과 다릅니다.")

    if isinstance(content, str):
        return content

    # 일부 모델은 content를 리스트 형태로 줄 수 있음
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)

    return str(content)


def error_response(message, status_code=400, detail=None):
    """
    API 오류 응답 통일
    """
    payload = {
        "success": False,
        "message": message
    }

    if detail:
        payload["detail"] = detail

    return jsonify(payload), status_code


# =========================================================
# 5. LLM API 호출 함수
# =========================================================

def call_llm(messages, temperature=0.2, max_tokens=1200):
    """
    한양여대 API Gateway의 OpenAI 호환 Chat Completions API 호출
    """
    if not LLM_API_KEY:
        raise ValueError(".env 파일에 LLM_API_KEY가 설정되어 있지 않습니다.")

    if not LLM_BASE_URL:
        raise ValueError(".env 파일에 LLM_BASE_URL이 설정되어 있지 않습니다.")

    if not LLM_MODEL:
        raise ValueError(".env 파일에 LLM_MODEL이 설정되어 있지 않습니다.")

    endpoint = join_url(LLM_BASE_URL, "chat/completions")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": messages
    }

    if LLM_MODEL.startswith("gpt-5"):
        payload["max_completion_tokens"] = max_tokens
        payload["reasoning_effort"] = "minimal"
        payload["verbosity"] = "low"
    else:
        payload["temperature"] = temperature
        payload["max_tokens"] = max_tokens

    response = requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"LLM API 호출 실패: {response.status_code} / {response.text}"
        )

    response_json = response.json()
    return extract_choice_content(response_json)


# =========================================================
# 6. 키워드 추출 함수
# =========================================================

def fallback_extract_keywords(user_input):
    """
    LLM API 실패 시 사용할 간단한 키워드 추출 함수
    """
    combined_text = " ".join([
        clean_text(user_input.get("topic")),
        clean_text(user_input.get("purpose")),
        clean_text(user_input.get("content")),
        clean_text(user_input.get("region"))
    ])

    words = re.findall(r"[가-힣A-Za-z0-9]+", combined_text)

    stopwords = {
        "분석", "활용", "목적", "내용", "데이터", "서비스", "추천",
        "하고", "싶습니다", "위한", "통해", "관련", "사용", "제작",
        "공모전", "과제", "보고서", "현황", "이용현황", "통계",
        "시각화", "공공데이터", "조회", "탐색", "후보", "정보",
        "서울시", "서울특별시", "경기도", "부산광역시", "인천광역시"
    }

    keywords = []
    for word in words:
        if len(word) < 2:
            continue
        if word in stopwords:
            continue
        if word not in keywords:
            keywords.append(word)

    # region = clean_text(user_input.get("region"))
    # if region and region not in keywords:
    #     keywords.insert(0, region)

    return keywords[:8]


def extract_keywords(user_input):
    """
    사용자 입력을 바탕으로 공공데이터 검색용 키워드 추출
    """
    prompt = f"""
    공공데이터포털 검색용 키워드를 JSON으로만 출력하세요.

    규칙:
    - 핵심 대상명, 서비스명, 정책명, 시설명을 우선하세요.
    - 지역명만 단독으로 넣지 마세요.
    - "분석", "현황", "이용현황", "데이터", "통계", "공모전"은 제외하세요.
    - 3~6개만 출력하세요.
    - 설명 없이 JSON만 출력하세요.

    예시:
    입력: 서울시 따릉이 이용현황 분석
    출력:
    {{
    "keywords": ["따릉이", "서울시 따릉이", "서울특별시 공공자전거", "공공자전거 대여이력", "공공자전거 대여소"],
    "search_intent": "서울시 따릉이 대여 이력 및 대여소 데이터 탐색"
    }}

    사용자 입력:
    - 활용 주제: {clean_text(user_input.get("topic"))}
    - 활용 목적: {clean_text(user_input.get("purpose"))}
    - 활용 내용: {clean_text(user_input.get("content"))}
    - 관심 지역: {clean_text(user_input.get("region"))}
    - 원하는 데이터 형태: {clean_text(user_input.get("data_types"))}

    출력 형식:
    {{
    "keywords": ["키워드1", "키워드2", "키워드3"],
    "search_intent": "탐색 의도 요약"
    }}
    """

    try:
        llm_text = call_llm(
            messages=[
                {
                    "role": "system",
                    "content": "당신은 공공데이터 검색 키워드 추출 전문가입니다. 반드시 JSON만 출력합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=2000
        )

        parsed = parse_json_from_text(llm_text)
        keywords = parsed.get("keywords", [])

        if not isinstance(keywords, list) or len(keywords) == 0:
            return fallback_extract_keywords(user_input)

        cleaned_keywords = []
        for keyword in keywords:
            keyword = clean_text(keyword)
            if keyword and keyword not in cleaned_keywords:
                cleaned_keywords.append(keyword)

        return cleaned_keywords[:10]

    except Exception as e:
        print("[키워드 추출 오류]", e)
        return fallback_extract_keywords(user_input)


# =========================================================
# 7. 공공데이터포털 후보 데이터 조회 함수
# =========================================================

def find_list_of_dicts(obj):
    """
    공공데이터포털 API 응답 구조가 API마다 다를 수 있으므로,
    JSON 내부에서 dict 리스트를 자동 탐색
    """
    candidates = []

    if isinstance(obj, list):
        if all(isinstance(item, dict) for item in obj):
            candidates.append(obj)

        for item in obj:
            candidates.extend(find_list_of_dicts(item))

    elif isinstance(obj, dict):
        for value in obj.values():
            candidates.extend(find_list_of_dicts(value))

    return candidates


def get_first_value(data, keys):
    """
    여러 후보 키 중 처음 존재하는 값을 반환
    """
    for key in keys:
        if key in data and data[key] not in [None, ""]:
            return data[key]
    return ""


def normalize_dataset_item(item, idx, keyword):
    """
    공공데이터포털 dataset API 응답 필드명을
    프론트엔드에서 사용하기 쉬운 형태로 통일
    """
    title = get_first_value(item, [
        "title", "list_title", "name", "datasetName", "dataName", "dataNm",
        "publicDataName", "publicDataSj", "infNm", "데이터명", "공공데이터명"
    ])

    organization = get_first_value(item, [
        "org_nm", "organization", "orgNm", "insttNm", "provideOrgNm",
        "provider", "제공기관", "기관명"
    ])

    data_type = get_first_value(item, [
        "ext", "data_type", "type", "dataType", "publicDataTy",
        "srvceType", "format", "dataFormat", "제공형태", "데이터유형"
    ])

    modified_date = get_first_value(item, [
        "updated_at", "modified_date", "modifiedDate", "updtDt",
        "modDate", "updatedAt", "mofcnDt", "수정일", "갱신일"
    ])

    description = get_first_value(item, [
        "desc", "description", "dataDesc", "publicDataDesc",
        "content", "설명", "공공데이터설명"
    ])

    url = get_first_value(item, [
        "page_url", "url", "link", "detailUrl", "dataUrl",
        "landingPage", "참조URL"
    ])

    category = get_first_value(item, [
        "category_nm", "new_category_nm"
    ])

    keywords_value = get_first_value(item, [
        "keywords"
    ])

    if not title:
        title = f"{keyword} 관련 공공데이터 {idx + 1}"

    if not organization:
        organization = "제공기관 정보 없음"

    if not data_type:
        data_type = "유형 정보 없음"

    if not url:
        url = f"https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword={keyword}"

    return {
        "id": f"data_{idx + 1:03d}",
        "title": clean_text(title),
        "organization": clean_text(organization),
        "type": clean_text(data_type),
        "modified_date": clean_text(modified_date),
        "description": clean_text(description),
        "url": clean_text(url),
        "category": clean_text(category),
        "keywords": clean_text(keywords_value),
        "matched_keyword": clean_text(keyword)
    }

def remove_duplicate_datasets(datasets):
    """
    데이터명 + 제공기관 기준 중복 제거
    """
    seen = set()
    unique = []

    for dataset in datasets:
        key = (
            dataset.get("title", "").strip(),
            dataset.get("organization", "").strip()
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(dataset)

    # id 재정렬
    for idx, dataset in enumerate(unique):
        dataset["id"] = f"data_{idx + 1:03d}"

    return unique


def get_mock_datasets(keywords):
    """
    공공데이터 API URL 또는 인증키가 없을 때 화면 테스트용으로 사용하는 예시 데이터.
    실제 추천용 데이터가 아니므로 source를 MOCK으로 표시.
    """
    keyword_text = " ".join(keywords) if keywords else "공공데이터"

    return [
        {
            "id": "data_001",
            "title": f"{keyword_text} 관련 공공데이터 후보 예시 1",
            "organization": "개발용 예시",
            "type": "CSV",
            "modified_date": "",
            "description": "공공데이터 API 연결 전 화면 테스트를 위한 예시 데이터입니다.",
            "url": "https://www.data.go.kr/",
            "matched_keyword": keywords[0] if keywords else "",
            "source": "MOCK"
        },
        {
            "id": "data_002",
            "title": f"{keyword_text} 관련 공공데이터 후보 예시 2",
            "organization": "개발용 예시",
            "type": "Open API",
            "modified_date": "",
            "description": "실제 공공데이터포털 API를 연결하면 이 위치에 조회 결과가 표시됩니다.",
            "url": "https://www.data.go.kr/",
            "matched_keyword": keywords[0] if keywords else "",
            "source": "MOCK"
        }
    ]


def search_public_data(keywords, data_types=None):
    """
    키워드를 이용해 공공데이터포털 목록조회 API에서 후보 데이터를 조회
    """
    if not keywords:
        return []

    # 아직 공공데이터 API URL 또는 키가 없으면 개발용 예시 데이터 반환
    if not PUBLIC_DATA_API_URL or not PUBLIC_DATA_API_KEY:
        print("[공공데이터 API 안내] PUBLIC_DATA_API_URL 또는 PUBLIC_DATA_API_KEY가 없어 MOCK 데이터를 반환합니다.")
        return get_mock_datasets(keywords)

    all_datasets = []

    for keyword in keywords:
        for search_param in PUBLIC_DATA_SEARCH_PARAMS:
            params = {
                "serviceKey": PUBLIC_DATA_API_KEY,
                PUBLIC_DATA_PAGE_PARAM: 1,
                PUBLIC_DATA_SIZE_PARAM: DEFAULT_NUM_ROWS,
                PUBLIC_DATA_TYPE_PARAM: PUBLIC_DATA_TYPE_VALUE,
                search_param: keyword
            }

            try:
                response = requests.get(
                    PUBLIC_DATA_API_URL,
                    params=params,
                    timeout=30
                )

                if response.status_code >= 400:
                    print(
                        f"[공공데이터 API 오류] "
                        f"keyword={keyword}, search_param={search_param}, "
                        f"status={response.status_code}, body={response.text[:300]}"
                    )
                    continue

                try:
                    raw_data = response.json()
                except json.JSONDecodeError:
                    print(
                        f"[공공데이터 API 오류] JSON 응답이 아닙니다. "
                        f"keyword={keyword}, search_param={search_param}"
                    )
                    continue

                # dataset API는 보통 raw_data["data"]에 목록이 들어 있음
                items = raw_data.get("data", [])

                if not isinstance(items, list):
                    list_candidates = find_list_of_dicts(raw_data)
                    if not list_candidates:
                        print(
                            f"[공공데이터 API 안내] 데이터 목록을 찾지 못했습니다. "
                            f"keyword={keyword}, search_param={search_param}"
                        )
                        continue

                    items = max(list_candidates, key=len)

                if not items:
                    continue

                for item in items:
                    normalized = normalize_dataset_item(
                        item=item,
                        idx=len(all_datasets),
                        keyword=keyword
                    )
                    normalized["source"] = "PUBLIC_DATA_API"
                    normalized["search_param"] = search_param
                    all_datasets.append(normalized)

            except Exception as e:
                print(
                    f"[공공데이터 API 호출 오류] "
                    f"keyword={keyword}, search_param={search_param}, error={e}"
                )
                continue

    unique_datasets = remove_duplicate_datasets(all_datasets)

    # 원하는 데이터 형태 필터링
    if data_types:
        selected_types = [str(x).lower() for x in data_types]

        filtered = []
        for dataset in unique_datasets:
            dtype = dataset.get("type", "").lower()

            if any(selected_type in dtype for selected_type in selected_types):
                filtered.append(dataset)

        # 필터 결과가 있을 때만 필터 적용
        if filtered:
            unique_datasets = filtered

    return unique_datasets[:50]


# =========================================================
# 8. AI 추천 함수
# =========================================================

def simple_overlap_score(user_input, dataset):
    """
    LLM 추천 실패 시 사용할 간단한 관련도 점수
    """
    user_text = " ".join([
        clean_text(user_input.get("topic")),
        clean_text(user_input.get("purpose")),
        clean_text(user_input.get("content")),
        clean_text(user_input.get("region"))
    ]).lower()

    dataset_text = " ".join([
        clean_text(dataset.get("title")),
        clean_text(dataset.get("organization")),
        clean_text(dataset.get("description")),
        clean_text(dataset.get("matched_keyword"))
    ]).lower()

    words = set(re.findall(r"[가-힣A-Za-z0-9]+", user_text))
    words = {w for w in words if len(w) >= 2}

    if not words:
        return 50

    matched = sum(1 for word in words if word in dataset_text)
    score = int((matched / len(words)) * 100)

    return max(50, min(score, 95))


def fallback_recommend_datasets(user_input, datasets, top_n=5):
    """
    LLM API 실패 시 규칙 기반 추천 결과 생성
    """
    scored = []

    for dataset in datasets:
        score = simple_overlap_score(user_input, dataset)
        scored.append((score, dataset))

    scored.sort(key=lambda x: x[0], reverse=True)

    recommendations = []

    for rank, (score, dataset) in enumerate(scored[:top_n], start=1):
        recommendations.append({
            "rank": rank,
            "dataset_id": dataset.get("id"),
            "title": dataset.get("title"),
            "organization": dataset.get("organization"),
            "type": dataset.get("type"),
            "modified_date": dataset.get("modified_date"),
            "url": dataset.get("url"),
            "score": score,
            "reason": "사용자 입력 키워드와 데이터명 또는 설명의 관련성이 높아 추천되었습니다.",
            "usage": "데이터의 지역, 대상, 지표 항목을 확인한 뒤 분석 목적에 맞게 전처리하여 활용할 수 있습니다.",
            "analysis_idea": "지역별 비교, 시계열 변화, 수요-공급 불균형 분석 등에 활용할 수 있습니다.",
            "visualization": "막대그래프, 지도 시각화, 산점도, 순위표",
            "combined_data": []
        })

    return recommendations


def recommend_datasets(user_input, datasets, top_n=5):
    """
    조회된 후보 데이터 목록 안에서만 AI 추천 생성
    """
    if not datasets:
        return []

    # LLM에 너무 많은 데이터를 보내지 않도록 제한
    candidate_datasets = datasets[:10]

    compact_candidates = []

    for dataset in candidate_datasets:
        compact_candidates.append({
            "id": dataset.get("id"),
            "title": dataset.get("title"),
            "organization": dataset.get("organization"),
            "type": dataset.get("type"),
            "modified_date": dataset.get("modified_date"),
            "description": clean_text(dataset.get("description"))[:300],
            "keywords": dataset.get("keywords"),
            "url": dataset.get("url")
        })

    candidate_text = json.dumps(
        compact_candidates,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
당신은 공공데이터 기반 데이터 분석 기획 전문가입니다.

아래 사용자 입력과 공공데이터포털에서 실제 조회된 후보 데이터 목록을 보고,
사용자 목적에 가장 적합한 공공데이터를 최대 5개 추천하세요.

중요 제한:
1. 반드시 제공된 후보 데이터 목록 안에서만 추천하세요.
2. 후보 목록에 없는 데이터명, 제공기관, URL을 절대 새로 만들지 마세요.
3. 추천 결과의 dataset_id는 반드시 후보 목록의 id 값 중 하나여야 합니다.
4. 관련성이 낮은 데이터는 억지로 추천하지 마세요.
5. 결과는 반드시 JSON으로만 출력하세요.
6. 설명 문장, 마크다운, 코드블록은 출력하지 마세요.

사용자 입력:
- 활용 주제: {clean_text(user_input.get("topic"))}
- 활용 목적: {clean_text(user_input.get("purpose"))}
- 활용 내용: {clean_text(user_input.get("content"))}
- 관심 지역: {clean_text(user_input.get("region"))}
- 원하는 데이터 형태: {clean_text(user_input.get("data_types"))}

후보 데이터 목록:
{candidate_text}

출력 형식:
{{
  "recommendations": [
    {{
      "rank": 1,
      "dataset_id": "data_001",
      "score": 92,
      "reason": "추천 이유",
      "usage": "활용 방향",
      "analysis_idea": "분석 아이디어",
      "visualization": "시각화 방향",
      "combined_data": ["결합하면 좋은 데이터 키워드 1", "결합하면 좋은 데이터 키워드 2"]
    }}
  ]
}}
"""

    try:
        llm_text = call_llm(
            messages=[
                {
                    "role": "system",
                    "content": "당신은 공공데이터 추천 전문가입니다. 반드시 후보 목록 안에서만 추천하고 JSON만 출력합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_tokens=4000
        )

        parsed = parse_json_from_text(llm_text)
        recommendations = parsed.get("recommendations", [])

        if not isinstance(recommendations, list):
            return fallback_recommend_datasets(user_input, datasets, top_n)

        dataset_map = {
            dataset["id"]: dataset
            for dataset in datasets
            if "id" in dataset
        }

        validated = []

        for rec in recommendations:
            dataset_id = rec.get("dataset_id")

            # 후보 목록에 없는 id는 제거
            if dataset_id not in dataset_map:
                continue

            source_dataset = dataset_map[dataset_id]

            validated.append({
                "rank": len(validated) + 1,
                "dataset_id": dataset_id,
                "title": source_dataset.get("title"),
                "organization": source_dataset.get("organization"),
                "type": source_dataset.get("type"),
                "modified_date": source_dataset.get("modified_date"),
                "url": source_dataset.get("url"),
                "score": rec.get("score", 0),
                "reason": clean_text(rec.get("reason")),
                "usage": clean_text(rec.get("usage")),
                "analysis_idea": clean_text(rec.get("analysis_idea")),
                "visualization": clean_text(rec.get("visualization")),
                "combined_data": rec.get("combined_data", [])
            })

            if len(validated) >= top_n:
                break

        if not validated:
            return fallback_recommend_datasets(user_input, datasets, top_n)

        return validated

    except Exception as e:
        print("[AI 추천 오류]", e)
        return fallback_recommend_datasets(user_input, datasets, top_n)


# =========================================================
# 9. API 라우팅
# =========================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    """
    서버 상태 확인용 API
    """
    return jsonify({
        "success": True,
        "message": "서버가 정상 실행 중입니다.",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    입력 화면에서 호출하는 API.
    사용자 입력 → 키워드 추출 → 공공데이터 후보 조회
    """
    try:
        data = request.get_json()

        if not data:
            return error_response("요청 데이터가 비어 있습니다.", 400)

        user_input = {
            "topic": clean_text(data.get("topic")),
            "purpose": clean_text(data.get("purpose")),
            "content": clean_text(data.get("content")),
            "region": clean_text(data.get("region")),
            "data_types": data.get("dataTypes") or data.get("data_types") or []
        }

        if not user_input["topic"]:
            return error_response("활용 주제를 입력해야 합니다.", 400)

        if not user_input["content"]:
            return error_response("활용 내용을 입력해야 합니다.", 400)

        keywords = extract_keywords(user_input)

        datasets = search_public_data(
            keywords=keywords,
            data_types=user_input["data_types"]
        )

        return jsonify({
            "success": True,
            "user_input": user_input,
            "keywords": keywords,
            "datasets": datasets,
            "candidate_count": len(datasets),
            "is_mock_data": any(dataset.get("source") == "MOCK" for dataset in datasets)
        })

    except Exception as e:
        print("[/api/analyze 오류]", e)
        return error_response(
            "사용자 입력 분석 중 오류가 발생했습니다.",
            500,
            detail=str(e)
        )


@app.route("/api/recommend", methods=["POST"])
def recommend():
    """
    데이터 탐색 화면에서 호출하는 API.
    공공데이터 후보 목록 → AI 추천 결과 생성
    """
    try:
        data = request.get_json()

        if not data:
            return error_response("요청 데이터가 비어 있습니다.", 400)

        user_input = data.get("user_input") or data.get("userInput")
        datasets = data.get("datasets")

        if not user_input:
            return error_response("user_input 값이 없습니다.", 400)

        if not datasets or not isinstance(datasets, list):
            return error_response("추천에 사용할 데이터 후보 목록이 없습니다.", 400)

        recommendations = recommend_datasets(
            user_input=user_input,
            datasets=datasets,
            top_n=5
        )

        return jsonify({
            "success": True,
            "recommendations": recommendations,
            "recommendation_count": len(recommendations)
        })

    except Exception as e:
        print("[/api/recommend 오류]", e)
        return error_response(
            "AI 추천 결과 생성 중 오류가 발생했습니다.",
            500,
            detail=str(e)
        )


# =========================================================
# 10. 오류 페이지 처리
# =========================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "message": "요청한 페이지 또는 API를 찾을 수 없습니다."
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "서버 내부 오류가 발생했습니다."
    }), 500

@app.route("/keep-alive")
def keep_alive():
    return "I am alive!"
# =========================================================
# 11. 서버 실행
# =========================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
