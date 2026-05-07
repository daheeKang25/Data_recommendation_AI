// =========================================================
// explore.js
// 역할:
// 1. sessionStorage에 저장된 사용자 입력, 키워드, 데이터 후보를 불러오기
// 2. 데이터 탐색 화면에 입력 요약, 키워드, 후보 데이터 표 출력
// 3. 검색어 / 제공형태 / 정렬 필터 적용
// 4. /api/recommend 호출 후 추천 결과를 sessionStorage에 저장
// 5. AI 추천 결과 화면(/result)으로 이동
// =========================================================

document.addEventListener("DOMContentLoaded", function () {
    // -----------------------------------------------------
    // 1. HTML 요소 가져오기
    // -----------------------------------------------------

    const summaryTopic = document.getElementById("summaryTopic");
    const summaryPurpose = document.getElementById("summaryPurpose");
    const summaryRegion = document.getElementById("summaryRegion");
    const candidateCount = document.getElementById("candidateCount");
    const keywordList = document.getElementById("keywordList");

    const searchInput = document.getElementById("searchInput");
    const typeFilter = document.getElementById("typeFilter");
    const sortSelect = document.getElementById("sortSelect");

    const datasetTableBody = document.getElementById("datasetTableBody");

    const errorMessage = document.getElementById("errorMessage");
    const loadingMessage = document.getElementById("loadingMessage");
    const emptyMessage = document.getElementById("emptyMessage");

    const refreshButton = document.getElementById("refreshButton");
    const recommendButton = document.getElementById("recommendButton");

    // -----------------------------------------------------
    // 2. sessionStorage 데이터 불러오기
    // -----------------------------------------------------

    const userInput = getStorageData("userInput", {});
    const keywords = getStorageData("keywords", []);
    const datasets = getStorageData("datasets", []);
    const storedCandidateCount = Number(sessionStorage.getItem("candidateCount") || datasets.length || 0);

    let currentDatasets = Array.isArray(datasets) ? [...datasets] : [];

    // -----------------------------------------------------
    // 3. 초기 화면 렌더링
    // -----------------------------------------------------

    renderSummary(userInput, keywords, storedCandidateCount);
    renderDatasetTable(currentDatasets);

    if (!currentDatasets.length) {
        showEmptyMessage(true);
    } else {
        showEmptyMessage(false);
    }

    // -----------------------------------------------------
    // 4. 이벤트 연결
    // -----------------------------------------------------

    if (searchInput) {
        searchInput.addEventListener("input", applyFilters);
    }

    if (typeFilter) {
        typeFilter.addEventListener("change", applyFilters);
    }

    if (sortSelect) {
        sortSelect.addEventListener("change", applyFilters);
    }

    if (refreshButton) {
        refreshButton.addEventListener("click", function () {
            searchInput.value = "";
            typeFilter.value = "";
            sortSelect.value = "default";

            currentDatasets = Array.isArray(datasets) ? [...datasets] : [];
            renderDatasetTable(currentDatasets);
            hideError();
        });
    }

    if (recommendButton) {
        recommendButton.addEventListener("click", createRecommendation);
    }


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
    // 입력 요약 렌더링
    // =====================================================

    function renderSummary(userInput, keywords, count) {
        summaryTopic.textContent = userInput.topic || "-";
        summaryPurpose.textContent = userInput.purpose || "-";
        summaryRegion.textContent = userInput.region || "전체 지역";
        candidateCount.textContent = `${count}개`;

        renderKeywords(keywords);
    }


    // =====================================================
    // 키워드 렌더링
    // =====================================================

    function renderKeywords(keywords) {
        keywordList.innerHTML = "";

        if (!Array.isArray(keywords) || keywords.length === 0) {
            keywordList.innerHTML = `<span class="keyword-chip">키워드 없음</span>`;
            return;
        }

        keywords.forEach(function (keyword) {
            const chip = document.createElement("span");
            chip.className = "keyword-chip";
            chip.textContent = keyword;
            keywordList.appendChild(chip);
        });
    }


    // =====================================================
    // 데이터 테이블 렌더링
    // =====================================================

    function renderDatasetTable(datasetList) {
        datasetTableBody.innerHTML = "";

        if (!Array.isArray(datasetList) || datasetList.length === 0) {
            showEmptyMessage(true);
            candidateCount.textContent = "0개";
            return;
        }

        showEmptyMessage(false);
        candidateCount.textContent = `${datasetList.length}개`;

        datasetList.forEach(function (dataset, index) {
            const row = document.createElement("tr");

            const title = dataset.title || "데이터명 없음";
            const organization = dataset.organization || "제공기관 정보 없음";
            const type = dataset.type || "유형 정보 없음";
            const modifiedDate = dataset.modified_date || "-";
            const description = dataset.description || "설명 없음";
            const url = dataset.url || "";

            row.innerHTML = `
                <td>${index + 1}</td>
                <td class="dataset-title">${escapeHtml(title)}</td>
                <td>${escapeHtml(organization)}</td>
                <td>${escapeHtml(type)}</td>
                <td>${escapeHtml(modifiedDate)}</td>
                <td>${escapeHtml(shortenText(description, 90))}</td>
                <td>
                    ${
                        url
                            ? `<a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer" class="table-link">바로가기</a>`
                            : `<span class="muted-text">없음</span>`
                    }
                </td>
            `;

            datasetTableBody.appendChild(row);
        });
    }


    // =====================================================
    // 검색 / 필터 / 정렬 적용
    // =====================================================

    function applyFilters() {
        hideError();

        const searchValue = searchInput.value.trim().toLowerCase();
        const selectedType = typeFilter.value.trim().toLowerCase();
        const sortValue = sortSelect.value;

        let filteredDatasets = Array.isArray(datasets) ? [...datasets] : [];

        // 검색어 필터
        if (searchValue) {
            filteredDatasets = filteredDatasets.filter(function (dataset) {
                const targetText = [
                    dataset.title,
                    dataset.organization,
                    dataset.type,
                    dataset.modified_date,
                    dataset.description,
                    dataset.category,
                    dataset.keywords,
                    dataset.matched_keyword
                ].join(" ").toLowerCase();

                return targetText.includes(searchValue);
            });
        }

        // 제공형태 필터
        if (selectedType) {
            filteredDatasets = filteredDatasets.filter(function (dataset) {
                const datasetType = String(dataset.type || "").toLowerCase();

                if (selectedType === "xlsx") {
                    return datasetType.includes("xlsx") || datasetType.includes("xls") || datasetType.includes("excel");
                }

                if (selectedType === "open api") {
                    return datasetType.includes("api") || datasetType.includes("open");
                }

                return datasetType.includes(selectedType);
            });
        }

        // 정렬
        filteredDatasets = sortDatasets(filteredDatasets, sortValue);

        currentDatasets = filteredDatasets;
        renderDatasetTable(currentDatasets);
    }


    // =====================================================
    // 정렬 함수
    // =====================================================

    function sortDatasets(datasetList, sortValue) {
        const sorted = [...datasetList];

        if (sortValue === "title") {
            sorted.sort(function (a, b) {
                return String(a.title || "").localeCompare(String(b.title || ""), "ko");
            });
        }

        if (sortValue === "organization") {
            sorted.sort(function (a, b) {
                return String(a.organization || "").localeCompare(String(b.organization || ""), "ko");
            });
        }

        if (sortValue === "updated") {
            sorted.sort(function (a, b) {
                const dateA = normalizeDateValue(a.modified_date);
                const dateB = normalizeDateValue(b.modified_date);

                return dateB - dateA;
            });
        }

        return sorted;
    }


    // =====================================================
    // 날짜 정렬용 값 변환
    // =====================================================

    function normalizeDateValue(value) {
        if (!value) {
            return 0;
        }

        const cleaned = String(value).replace(/[.]/g, "-");
        const timestamp = new Date(cleaned).getTime();

        if (Number.isNaN(timestamp)) {
            return 0;
        }

        return timestamp;
    }


    // =====================================================
    // AI 추천 결과 생성
    // =====================================================

    async function createRecommendation() {
        hideError();

        if (!Array.isArray(datasets) || datasets.length === 0) {
            showError("추천에 사용할 데이터 후보가 없습니다. 입력 화면에서 다시 탐색하세요.");
            return;
        }

        setLoading(true, "AI가 데이터 후보를 평가하고 추천 결과를 생성하는 중입니다.");

        try {
            const recommendTargetDatasets = datasets.slice(0, 10);
            const response = await fetch("/api/recommend", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    user_input: userInput,
                    datasets: recommendTargetDatasets
                })
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.message || "AI 추천 결과 생성 중 오류가 발생했습니다.");
            }

            saveRecommendationResult(result);

            window.location.href = "/result";

        } catch (error) {
            console.error("AI 추천 오류:", error);
            showError(error.message || "서버와 통신하는 중 오류가 발생했습니다.");
        } finally {
            setLoading(false);
        }
    }


    // =====================================================
    // 추천 결과 저장
    // =====================================================

    function saveRecommendationResult(result) {
        sessionStorage.setItem("recommendations", JSON.stringify(result.recommendations || []));
        sessionStorage.setItem("recommendationCount", String(result.recommendation_count || 0));
    }


    // =====================================================
    // 로딩 상태 처리
    // =====================================================

    function setLoading(isLoading, message) {
        if (!loadingMessage || !recommendButton) {
            return;
        }

        if (isLoading) {
            loadingMessage.textContent = message || "공공데이터 후보 목록을 불러오는 중입니다.";
            loadingMessage.style.display = "block";
            recommendButton.disabled = true;
            recommendButton.textContent = "추천 생성 중...";
        } else {
            loadingMessage.style.display = "none";
            recommendButton.disabled = false;
            recommendButton.textContent = "AI 추천 결과 생성하기";
        }
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
    // 빈 데이터 메시지 처리
    // =====================================================

    function showEmptyMessage(isShow) {
        if (!emptyMessage) {
            return;
        }

        emptyMessage.style.display = isShow ? "block" : "none";
    }


    // =====================================================
    // 텍스트 처리 유틸
    // =====================================================

    function shortenText(text, maxLength) {
        const value = String(text || "");

        if (value.length <= maxLength) {
            return value;
        }

        return value.slice(0, maxLength) + "...";
    }

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
