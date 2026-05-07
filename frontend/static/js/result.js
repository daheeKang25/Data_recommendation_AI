// =========================================================
// result.js
// 역할:
// 1. sessionStorage에 저장된 사용자 입력과 AI 추천 결과를 불러오기
// 2. 추천 결과 요약 표시
// 3. 추천 데이터 카드 목록 출력
// 4. 추천 결과가 없을 경우 안내 메시지 표시
// =========================================================

document.addEventListener("DOMContentLoaded", function () {
    // -----------------------------------------------------
    // 1. HTML 요소 가져오기
    // -----------------------------------------------------

    const resultTopic = document.getElementById("resultTopic");
    const resultPurpose = document.getElementById("resultPurpose");
    const resultRegion = document.getElementById("resultRegion");
    const recommendationCount = document.getElementById("recommendationCount");

    const recommendationList = document.getElementById("recommendationList");

    const errorMessage = document.getElementById("errorMessage");
    const loadingMessage = document.getElementById("loadingMessage");
    const emptyMessage = document.getElementById("emptyMessage");

    // -----------------------------------------------------
    // 2. sessionStorage 데이터 불러오기
    // -----------------------------------------------------

    const userInput = getStorageData("userInput", {});
    const recommendations = getStorageData("recommendations", []);
    const storedRecommendationCount = Number(
        sessionStorage.getItem("recommendationCount") || recommendations.length || 0
    );

    // -----------------------------------------------------
    // 3. 초기 화면 렌더링
    // -----------------------------------------------------

    hideError();
    setLoading(false);

    renderSummary(userInput, storedRecommendationCount);
    renderRecommendations(recommendations);


    // =====================================================
    // sessionStorage 읽기 함수
    // =====================================================

    function getStorageData(key, defaultValue) {
        try {
            const value = sessionStorage.getItem(key);

            if (!value) {
                return defaultValue;
            }

            return JSON.parse(value);
        } catch (error) {
            console.error(`${key} 데이터 파싱 오류:`, error);
            return defaultValue;
        }
    }


    // =====================================================
    // 추천 결과 요약 렌더링
    // =====================================================

    function renderSummary(userInput, count) {
        if (resultTopic) {
            resultTopic.textContent = userInput.topic || "-";
        }

        if (resultPurpose) {
            resultPurpose.textContent = userInput.purpose || "-";
        }

        if (resultRegion) {
            resultRegion.textContent = userInput.region || "전체 지역";
        }

        if (recommendationCount) {
            recommendationCount.textContent = `${count}개`;
        }
    }


    // =====================================================
    // 추천 카드 목록 렌더링
    // =====================================================

    function renderRecommendations(recommendationData) {
        if (!recommendationList) {
            showError("추천 결과를 표시할 영역을 찾을 수 없습니다.");
            return;
        }

        recommendationList.innerHTML = "";

        if (!Array.isArray(recommendationData) || recommendationData.length === 0) {
            showEmptyMessage(true);

            if (recommendationCount) {
                recommendationCount.textContent = "0개";
            }

            return;
        }

        showEmptyMessage(false);

        recommendationData.forEach(function (recommendation, index) {
            const card = createRecommendationCard(recommendation, index);
            recommendationList.appendChild(card);
        });

        if (recommendationCount) {
            recommendationCount.textContent = `${recommendationData.length}개`;
        }
    }


    // =====================================================
    // 추천 카드 생성
    // =====================================================

    function createRecommendationCard(recommendation, index) {
        const card = document.createElement("article");
        card.className = "recommendation-card";

        const rank = recommendation.rank || index + 1;
        const title = recommendation.title || "데이터명 없음";
        const organization = recommendation.organization || "제공기관 정보 없음";
        const type = recommendation.type || "유형 정보 없음";
        const modifiedDate = recommendation.modified_date || "-";
        const score = recommendation.score || 0;
        const reason = recommendation.reason || "추천 이유가 제공되지 않았습니다.";
        const usage = recommendation.usage || "활용 방향이 제공되지 않았습니다.";
        const analysisIdea = recommendation.analysis_idea || "분석 아이디어가 제공되지 않았습니다.";
        const visualization = recommendation.visualization || "시각화 방향이 제공되지 않았습니다.";
        const combinedData = Array.isArray(recommendation.combined_data)
            ? recommendation.combined_data
            : [];
        const url = recommendation.url || "";

        card.innerHTML = `
            <div class="recommendation-card-header">
                <div>
                    <span class="rank-badge">추천 ${escapeHtml(rank)}위</span>
                    <h4>${escapeHtml(title)}</h4>
                </div>

                <div class="score-box">
                    <strong>${escapeHtml(score)}</strong>
                    <span>점</span>
                </div>
            </div>

            <div class="dataset-meta">
                <span>제공기관: ${escapeHtml(organization)}</span>
                <span>제공형태: ${escapeHtml(type)}</span>
                <span>수정일: ${escapeHtml(modifiedDate)}</span>
            </div>

            <div class="recommendation-content">
                <div class="recommendation-block">
                    <h5>추천 이유</h5>
                    <p>${escapeHtml(reason)}</p>
                </div>

                <div class="recommendation-block">
                    <h5>활용 방향</h5>
                    <p>${escapeHtml(usage)}</p>
                </div>

                <div class="recommendation-block">
                    <h5>분석 아이디어</h5>
                    <p>${escapeHtml(analysisIdea)}</p>
                </div>

                <div class="recommendation-block">
                    <h5>시각화 방향</h5>
                    <p>${escapeHtml(visualization)}</p>
                </div>

                <div class="recommendation-block">
                    <h5>결합 추천 데이터</h5>
                    ${renderCombinedData(combinedData)}
                </div>
            </div>

            <div class="recommendation-actions">
                ${
                    url
                        ? `<a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer" class="primary-button">공공데이터포털에서 확인하기</a>`
                        : `<span class="muted-text">URL 정보 없음</span>`
                }
            </div>
        `;

        return card;
    }


    // =====================================================
    // 결합 추천 데이터 렌더링
    // =====================================================

    function renderCombinedData(combinedData) {
        if (!Array.isArray(combinedData) || combinedData.length === 0) {
            return `<p class="muted-text">결합 추천 데이터가 없습니다.</p>`;
        }

        const chips = combinedData.map(function (item) {
            return `<span class="keyword-chip">${escapeHtml(item)}</span>`;
        }).join("");

        return `<div class="keyword-list">${chips}</div>`;
    }


    // =====================================================
    // 로딩 상태 처리
    // =====================================================

    function setLoading(isLoading) {
        if (!loadingMessage) {
            return;
        }

        loadingMessage.style.display = isLoading ? "block" : "none";
    }


    // =====================================================
    // 오류 메시지 처리
    // =====================================================

    function showError(message) {
        if (!errorMessage) {
            alert(message);
            return;
        }

        errorMessage.textContent = message;
        errorMessage.style.display = "block";
        errorMessage.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });
    }

    function hideError() {
        if (!errorMessage) {
            return;
        }

        errorMessage.textContent = "";
        errorMessage.style.display = "none";
    }


    // =====================================================
    // 빈 결과 메시지 처리
    // =====================================================

    function showEmptyMessage(isShow) {
        if (!emptyMessage) {
            return;
        }

        emptyMessage.style.display = isShow ? "block" : "none";
    }


    // =====================================================
    // HTML 보안 처리 유틸
    // =====================================================

    function escapeHtml(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function escapeAttribute(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll('"', "&quot;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    }
});