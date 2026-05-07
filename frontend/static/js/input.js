// =========================================================
// input.js
// 역할:
// 1. 입력 화면의 폼 데이터를 수집
// 2. /api/analyze로 사용자 입력 전송
// 3. 응답 결과를 sessionStorage에 저장
// 4. 데이터 탐색 화면(/explore)으로 이동
// =========================================================

document.addEventListener("DOMContentLoaded", function () {
    const inputForm = document.getElementById("inputForm");

    const topicInput = document.getElementById("topic");
    const purposeSelect = document.getElementById("purpose");
    const contentTextarea = document.getElementById("content");
    const regionInput = document.getElementById("region");

    const errorMessage = document.getElementById("errorMessage");
    const loadingMessage = document.getElementById("loadingMessage");
    const submitButton = document.getElementById("submitButton");

    if (!inputForm) {
        console.error("inputForm을 찾을 수 없습니다.");
        return;
    }

    inputForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        hideError();

        const userInput = collectFormData();

        const validationMessage = validateInput(userInput);
        if (validationMessage) {
            showError(validationMessage);
            return;
        }

        setLoading(true);

        try {
            const response = await fetch("/api/analyze", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(userInput)
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.message || "데이터 후보 탐색 중 오류가 발생했습니다.");
            }

            saveAnalyzeResult(result);

            window.location.href = "/explore";

        } catch (error) {
            console.error("입력 분석 오류:", error);
            showError(error.message || "서버와 통신하는 중 오류가 발생했습니다.");
        } finally {
            setLoading(false);
        }
    });


    // =====================================================
    // 폼 데이터 수집
    // =====================================================

    function collectFormData() {
        const checkedDataTypes = Array.from(
            document.querySelectorAll('input[name="dataTypes"]:checked')
        ).map(function (checkbox) {
            return checkbox.value;
        });

        return {
            topic: topicInput.value.trim(),
            purpose: purposeSelect.value.trim(),
            content: contentTextarea.value.trim(),
            region: regionInput.value.trim(),
            dataTypes: checkedDataTypes
        };
    }


    // =====================================================
    // 입력값 검증
    // =====================================================

    function validateInput(userInput) {
        if (!userInput.topic) {
            return "활용 주제를 입력하세요.";
        }

        if (!userInput.purpose) {
            return "활용 목적을 선택하세요.";
        }

        if (!userInput.content) {
            return "활용 내용을 입력하세요.";
        }

        if (userInput.topic.length < 2) {
            return "활용 주제는 2자 이상 입력하세요.";
        }

        if (userInput.content.length < 5) {
            return "활용 내용은 5자 이상 입력하세요.";
        }

        return "";
    }


    // =====================================================
    // 분석 결과 저장
    // =====================================================

    function saveAnalyzeResult(result) {
        /*
            explore.html에서 사용할 데이터:
            - user_input
            - keywords
            - datasets
            - candidate_count
            - is_mock_data
        */

        sessionStorage.setItem("userInput", JSON.stringify(result.user_input || {}));
        sessionStorage.setItem("keywords", JSON.stringify(result.keywords || []));
        sessionStorage.setItem("datasets", JSON.stringify(result.datasets || []));
        sessionStorage.setItem("candidateCount", String(result.candidate_count || 0));
        sessionStorage.setItem("isMockData", String(result.is_mock_data || false));

        // 이전 추천 결과가 남아 있으면 삭제
        sessionStorage.removeItem("recommendations");
        sessionStorage.removeItem("recommendationCount");
    }


    // =====================================================
    // 로딩 상태 처리
    // =====================================================

    function setLoading(isLoading) {
        if (isLoading) {
            loadingMessage.style.display = "block";
            submitButton.disabled = true;
            submitButton.textContent = "탐색 중...";
        } else {
            loadingMessage.style.display = "none";
            submitButton.disabled = false;
            submitButton.textContent = "데이터 후보 탐색하기";
        }
    }


    // =====================================================
    // 오류 메시지 처리
    // =====================================================

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = "block";
        errorMessage.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });
    }

    function hideError() {
        errorMessage.textContent = "";
        errorMessage.style.display = "none";
    }
});