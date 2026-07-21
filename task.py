import json
import os
import urllib.error
import urllib.request

import streamlit as st


# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="환경오염 창의적 글쓰기 AI 코치",
    page_icon="🌏",
    layout="wide",
)

TASK = "환경오염을 해결할 수 있는 방법은 무엇일까?"
OPENAI_API_URL = "https://api.openai.com/v1/responses"

SYSTEM_INSTRUCTIONS = """
당신은 한국어 창의적 글쓰기 코치입니다.

학습자가 스스로 생각하고 글을 발전시키도록 도와주세요.
글쓰기 주제는 다음과 같습니다.

'환경오염을 해결할 수 있는 방법은 무엇일까?'

다음 원칙을 지켜주세요.

1. 사용자의 기존 생각과 글을 존중합니다.
2. 막연한 칭찬보다 구체적인 아이디어와 수정 방법을 제공합니다.
3. 확인되지 않은 통계, 연구, 출처를 만들어내지 않습니다.
4. 개인, 지역사회, 기업, 정부의 역할을 균형 있게 생각합니다.
5. 창의적인 표현과 논리적인 설득력을 함께 높입니다.
6. 읽기 쉬운 자연스러운 한국어를 사용합니다.
7. 사용자가 요청하지 않는 한 무조건 완성 글을 대신 쓰기보다
   사용자가 직접 선택하고 수정할 수 있도록 돕습니다.
""".strip()


# =========================================================
# API 및 상태 관리 함수
# =========================================================
def get_setting(name, default=""):
    """
    Streamlit Secrets에서 설정을 먼저 찾고,
    없으면 환경변수에서 읽습니다.
    """
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""

    return str(value or os.getenv(name, default)).strip()


def extract_output_text(response_data):
    """
    OpenAI Responses API 결과에서 출력 텍스트를 추출합니다.
    """
    direct_text = response_data.get("output_text")

    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    text_parts = []

    for output_item in response_data.get("output", []):
        if not isinstance(output_item, dict):
            continue

        if output_item.get("type") != "message":
            continue

        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue

            if content_item.get("type") == "output_text":
                text = content_item.get("text", "")

                if text:
                    text_parts.append(str(text))

    result = "\n".join(text_parts).strip()

    if not result:
        raise RuntimeError("AI 응답에서 텍스트를 찾지 못했습니다.")

    return result


def call_openai(prompt, max_output_tokens=1200):
    """
    OpenAI SDK나 requests 없이 urllib로 Responses API를 호출합니다.
    """
    api_key = get_setting("OPENAI_API_KEY")
    model = get_setting("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            "Streamlit Cloud의 App settings → Secrets에서 API 키를 등록하세요."
        )

    request_data = {
        "model": model,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
    }

    encoded_data = json.dumps(
        request_data,
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        OPENAI_API_URL,
        data=encoded_data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_text = response.read().decode("utf-8")
            response_data = json.loads(response_text)

        return extract_output_text(response_data)

    except urllib.error.HTTPError as error:
        error_message = ""

        try:
            error_body = error.read().decode("utf-8")
            error_data = json.loads(error_body)
            error_message = error_data.get("error", {}).get("message", "")
        except Exception:
            pass

        if error.code == 401:
            message = "API 키가 올바르지 않거나 API 사용 권한이 없습니다."
        elif error.code == 429:
            message = (
                "API 사용 한도 또는 호출 빈도를 초과했습니다. "
                "잠시 후 다시 시도하세요."
            )
        elif error.code == 404:
            message = (
                "설정한 AI 모델을 사용할 수 없습니다. "
                "Secrets의 OPENAI_MODEL 값을 확인하세요."
            )
        else:
            message = error_message or "OpenAI API 요청에 실패했습니다."

        raise RuntimeError(
            f"OpenAI API 오류 {error.code}: {message}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            "네트워크 연결에 실패했습니다."
        ) from error

    except TimeoutError as error:
        raise RuntimeError(
            "AI 응답 대기 시간이 초과되었습니다."
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "AI 서버의 응답을 해석하지 못했습니다."
        ) from error


def initialize_session_state():
    """
    앱에서 사용할 기본 상태를 생성합니다.
    """
    default_values = {
        "initial_thoughts": "",
        "ideas_text": "",
        "outline_text": "",
        "draft_text": "",
        "feedback_text": "",
        "revision_request": (
            "피드백을 반영하되 내 글의 핵심 생각과 말투는 유지해 주세요."
        ),
        "chat_messages": [],
    }

    for key, value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # 이미 화면에 표시된 위젯 값을 같은 실행에서 변경하면
    # Streamlit 오류가 발생할 수 있으므로 다음 실행에서 반영합니다.
    pending_updates = st.session_state.pop(
        "_pending_updates",
        {},
    )

    for key, value in pending_updates.items():
        st.session_state[key] = value


def schedule_update(**updates):
    """
    다음 Streamlit 실행에서 상태값을 변경합니다.
    """
    st.session_state["_pending_updates"] = updates
    st.rerun()


def run_generation(
    prompt,
    target_key,
    max_output_tokens=1200,
):
    """
    AI 생성 결과를 특정 session_state 값에 저장합니다.
    """
    try:
        with st.spinner("AI가 내용을 만들고 있습니다..."):
            result = call_openai(
                prompt,
                max_output_tokens=max_output_tokens,
            )

        schedule_update(**{target_key: result})

    except RuntimeError as error:
        st.error(str(error))


def get_writing_context():
    """
    사용자가 선택한 글쓰기 설정을 프롬프트 문자열로 만듭니다.
    """
    audience = st.session_state.get(
        "audience",
        "중학생",
    )

    genre = st.session_state.get(
        "genre",
        "창의적 설득문",
    )

    tone = st.session_state.get(
        "tone",
        "희망적이고 설득력 있게",
    )

    target_length = st.session_state.get(
        "target_length",
        "약 800자",
    )

    focus = st.session_state.get(
        "focus",
        "",
    )

    initial_thoughts = st.session_state.get(
        "initial_thoughts",
        "",
    )

    return f"""
[글쓰기 과제]
{TASK}

[예상 독자]
{audience}

[글의 형식]
{genre}

[글의 분위기]
{tone}

[목표 분량]
{target_length}

[집중하고 싶은 환경 문제]
{focus or "아직 정하지 않음"}

[사용자가 먼저 적은 생각]
{initial_thoughts or "아직 작성하지 않음"}
""".strip()


def count_characters_without_spaces(text):
    """
    공백과 줄바꿈을 제외한 글자 수를 계산합니다.
    """
    return len(
        text.replace(" ", "").replace("\n", "")
    )


def count_paragraphs(text):
    """
    빈 문단을 제외한 문단 수를 계산합니다.
    """
    if not text.strip():
        return 0

    return len(
        [
            paragraph
            for paragraph in text.split("\n\n")
            if paragraph.strip()
        ]
    )


def count_sentences(text):
    """
    마침표, 물음표, 느낌표를 기준으로
    대략적인 문장 수를 계산합니다.
    """
    if not text.strip():
        return 0

    return sum(
        text.count(mark)
        for mark in [".", "!", "?"]
    )


initialize_session_state()

API_KEY_READY = bool(
    get_setting("OPENAI_API_KEY")
)

CURRENT_MODEL = get_setting(
    "OPENAI_MODEL",
    "gpt-4.1-mini",
)


# =========================================================
# 화면 스타일
# =========================================================
st.markdown(
    """
    <style>
        .main-title {
            font-size: 2.15rem;
            font-weight: 800;
            margin-bottom: 0.15rem;
        }

        .sub-title {
            color: #616b78;
            margin-bottom: 1.1rem;
        }

        .task-card {
            padding: 1rem 1.15rem;
            border: 1px solid rgba(128, 128, 128, 0.28);
            border-radius: 14px;
            margin-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 사이드바
# =========================================================
with st.sidebar:
    st.header("⚙️ 앱 설정")

    if API_KEY_READY:
        st.success("OpenAI API 연결 준비 완료")
        st.caption(f"사용 모델: `{CURRENT_MODEL}`")

    else:
        st.warning("OpenAI API 키가 필요합니다.")

        st.code(
            'OPENAI_API_KEY = "여기에_API_키"\n'
            'OPENAI_MODEL = "gpt-4.1-mini"',
            language="toml",
        )

        st.caption(
            "Streamlit Cloud의 App settings → Secrets에 "
            "위 내용을 등록하세요."
        )

    st.divider()

    st.markdown("### AI 활용 원칙")

    st.caption(
        "AI가 만든 내용을 그대로 제출하기보다 필요한 부분을 선택하고, "
        "자신의 경험과 표현을 추가해 글을 완성하세요."
    )

    if st.button(
        "🗑️ 모든 작업 내용 초기화",
        use_container_width=True,
    ):
        for state_key in list(st.session_state.keys()):
            del st.session_state[state_key]

        st.rerun()


# =========================================================
# 앱 제목
# =========================================================
st.markdown(
    '<div class="main-title">'
    "🌏 환경오염 창의적 글쓰기 AI 코치"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="sub-title">'
    "아이디어를 얻고, 개요를 세우고, 직접 쓴 글을 "
    "피드백받아 발전시키는 웹앱입니다."
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="task-card">
        <b>오늘의 글쓰기 과제</b><br>
        {TASK}
    </div>
    """,
    unsafe_allow_html=True,
)


plan_tab, draft_tab, feedback_tab, chat_tab = st.tabs(
    [
        "1️⃣ 아이디어·개요",
        "2️⃣ 초안 쓰기",
        "3️⃣ 피드백·수정",
        "4️⃣ AI 코치 대화",
    ]
)


# =========================================================
# 1. 아이디어와 개요
# =========================================================
with plan_tab:
    st.subheader("글의 방향 정하기")

    first_column, second_column = st.columns(2)

    with first_column:
        st.selectbox(
            "예상 독자",
            [
                "초등학교 고학년",
                "중학생",
                "고등학생",
                "일반 시민",
                "정책 결정자",
            ],
            index=1,
            key="audience",
        )

        st.selectbox(
            "글의 형식",
            [
                "창의적 설득문",
                "미래에서 온 편지",
                "환경 영웅 이야기",
                "신문 칼럼",
                "연설문",
            ],
            key="genre",
        )

        st.selectbox(
            "목표 분량",
            [
                "약 500자",
                "약 800자",
                "약 1,200자",
                "약 1,500자",
            ],
            index=1,
            key="target_length",
        )

    with second_column:
        st.selectbox(
            "글의 분위기",
            [
                "희망적이고 설득력 있게",
                "진지하고 경고하는 느낌",
                "따뜻하고 감성적으로",
                "재치 있고 상상력 있게",
                "논리적이고 차분하게",
            ],
            key="tone",
        )

        st.text_input(
            "집중하고 싶은 환경 문제",
            placeholder=(
                "예: 플라스틱, 미세먼지, 음식물 쓰레기, "
                "수질오염, 시민 참여"
            ),
            key="focus",
        )

    st.text_area(
        "AI를 사용하기 전에 내가 먼저 떠올린 생각",
        height=130,
        placeholder=(
            "환경오염의 원인, 해결 방법, 나의 경험, "
            "궁금한 점을 자유롭게 적어보세요."
        ),
        key="initial_thoughts",
    )

    idea_prompt = f"""
{get_writing_context()}

사용자가 글의 소재를 선택할 수 있도록
서로 겹치지 않는 창의적인 아이디어 6개를 제안해 주세요.

각 아이디어는 다음 형식으로 작성하세요.

### 아이디어 번호. 제목

- 핵심 주장:
- 독특한 장면 또는 비유:
- 구체적인 환경오염 해결 행동:
- 이 아이디어가 흥미로운 이유:

다음 조건을 지켜주세요.

- 개인의 행동만 제시하지 말고 지역사회, 기업,
  정부의 역할도 다양하게 포함합니다.
- 확인되지 않은 통계나 출처를 사용하지 않습니다.
- 완성된 글을 대신 작성하지 않습니다.
- 사용자가 선택하고 확장할 수 있는 글쓰기 재료를 제공합니다.
""".strip()

    if st.button(
        "✨ AI에게 다양한 아이디어 받기",
        disabled=not API_KEY_READY,
        use_container_width=True,
        key="generate_ideas",
    ):
        run_generation(
            idea_prompt,
            "ideas_text",
            max_output_tokens=1200,
        )

    st.text_area(
        "아이디어 노트",
        height=330,
        help=(
            "마음에 드는 아이디어만 남기거나 "
            "자신의 생각을 추가해 수정하세요."
        ),
        key="ideas_text",
    )

    outline_prompt = f"""
{get_writing_context()}

[사용자가 선택하거나 수정한 아이디어]

{st.session_state.get("ideas_text", "") or "구체적인 아이디어가 아직 없습니다."}

위 정보를 바탕으로 글쓰기 개요를 만들어 주세요.

다음 항목을 포함하세요.

1. 임시 제목 3개
2. 한 문장 핵심 주장
3. 도입
   - 독자의 관심을 끌 장면, 질문 또는 짧은 이야기
4. 본론 1
   - 환경오염 문제의 원인
5. 본론 2
   - 구체적인 해결 방법
6. 본론 3
   - 해결 방법을 실행했을 때 예상되는 변화
7. 개인, 지역사회, 기업, 정부 중 관련 주체의 역할
8. 예상되는 반대 의견이나 현실적인 어려움
9. 그 어려움에 대한 답변
10. 결론에서 독자에게 제안할 행동
11. 글에 사용할 수 있는 비유나 상징 3개

사용자가 직접 초안을 쓸 수 있을 정도로 구체적으로 작성하되,
각 문단 전체를 완성된 글로 대신 작성하지 마세요.
""".strip()

    if st.button(
        "🧭 선택한 아이디어로 개요 만들기",
        disabled=not API_KEY_READY,
        use_container_width=True,
        key="generate_outline",
    ):
        run_generation(
            outline_prompt,
            "outline_text",
            max_output_tokens=1500,
        )

    st.text_area(
        "글쓰기 개요",
        height=410,
        help=(
            "AI가 만든 개요의 순서와 내용을 "
            "자신의 생각에 맞게 수정하세요."
        ),
        key="outline_text",
    )


# =========================================================
# 2. 초안 작성
# =========================================================
with draft_tab:
    st.subheader("개요를 바탕으로 초안 쓰기")

    st.info(
        "먼저 직접 글을 작성해 보세요. 막히는 경우에만 "
        "AI 참고 초안을 사용하고, 생성된 문장은 반드시 "
        "자신의 표현으로 수정하는 것을 권장합니다."
    )

    st.text_area(
        "AI 참고 초안에 추가로 반영할 요청",
        height=90,
        placeholder=(
            "예: 첫 문단은 2050년의 오염된 바다를 "
            "상상하는 장면으로 시작해 주세요."
        ),
        key="draft_request",
    )

    draft_prompt = f"""
{get_writing_context()}

[사용자가 확정한 개요]

{st.session_state.get("outline_text", "") or
"개요가 없습니다. 현재 정보를 바탕으로 자연스러운 구성을 먼저 생각하세요."}

[추가 요청]

{st.session_state.get("draft_request", "") or "별도의 추가 요청 없음"}

사용자가 직접 수정하기 위한 참고 초안을 작성해 주세요.

다음 조건을 지켜주세요.

1. 사용자가 선택한 글의 형식과 분위기를 지킵니다.
2. 환경오염 문제와 해결 방법을 구체적으로 연결합니다.
3. 개인의 실천만 강조하지 않습니다.
4. 필요한 경우 지역사회, 기업, 정부의 역할도 포함합니다.
5. 확인되지 않은 통계나 가짜 출처는 사용하지 않습니다.
6. 도입, 전개, 결론이 분명하게 드러나야 합니다.
7. 문장은 자연스럽고 창의적으로 작성합니다.
8. 과도하게 상투적이거나 추상적인 표현은 줄입니다.
9. 사용자가 선택한 목표 분량에 가깝게 작성합니다.
10. 글의 마지막에는 다음 제목으로 점검 질문 3개를 작성합니다.

[내가 직접 바꿔볼 부분]
""".strip()

    generate_column, clear_column = st.columns(2)

    with generate_column:
        if st.button(
            "📝 AI 참고 초안 만들기",
            disabled=not API_KEY_READY,
            use_container_width=True,
            key="generate_draft",
        ):
            run_generation(
                draft_prompt,
                "draft_text",
                max_output_tokens=2200,
            )

    with clear_column:
        if st.button(
            "현재 초안 지우기",
            use_container_width=True,
            key="clear_draft",
        ):
            schedule_update(
                draft_text="",
                feedback_text="",
            )

    st.text_area(
        "내 초안",
        height=570,
        placeholder=(
            "여기에 직접 글을 작성하세요. "
            "AI가 만든 참고 초안도 자유롭게 수정할 수 있습니다."
        ),
        key="draft_text",
    )

    current_draft = st.session_state.get(
        "draft_text",
        "",
    )

    metric_column1, metric_column2, metric_column3 = st.columns(3)

    metric_column1.metric(
        "공백 제외 글자 수",
        count_characters_without_spaces(current_draft),
    )

    metric_column2.metric(
        "문단 수",
        count_paragraphs(current_draft),
    )

    metric_column3.metric(
        "문장 수",
        count_sentences(current_draft),
    )

    st.download_button(
        "⬇️ 현재 글을 TXT 파일로 저장",
        data=current_draft,
        file_name="환경오염_창의적글쓰기.txt",
        mime="text/plain",
        disabled=not bool(current_draft.strip()),
        use_container_width=True,
    )


# =========================================================
# 3. 피드백과 수정
# =========================================================
with feedback_tab:
    st.subheader("내 글을 점검하고 발전시키기")

    feedback_categories = st.multiselect(
        "집중해서 받고 싶은 피드백",
        [
            "핵심 주장과 논리",
            "환경 해결책의 구체성",
            "창의적인 표현",
            "문단 사이의 연결",
            "독자 설득력",
            "문법과 어색한 문장",
        ],
        default=[
            "핵심 주장과 논리",
            "환경 해결책의 구체성",
            "창의적인 표현",
        ],
        key="feedback_categories",
    )

    feedback_prompt = f"""
[글쓰기 과제]

{TASK}

[사용자의 초안]

{st.session_state.get("draft_text", "") or "초안이 입력되지 않았습니다."}

[집중해서 확인할 항목]

{", ".join(feedback_categories) if feedback_categories else "글의 전체적인 완성도"}

위 글을 창의적 글쓰기 코치의 관점에서 평가해 주세요.

다음 형식을 지켜주세요.

## 잘된 점

초안의 구체적인 문장이나 부분을 근거로
잘된 점 3가지를 설명합니다.

## 우선 고칠 점

가장 중요한 개선점 3가지를
이유와 함께 설명합니다.

## 문장 단위 수정 제안

문제가 있거나 더 좋아질 수 있는 원문 표현을 짧게 제시하고,
대체 표현과 수정 이유를 알려주세요.

## 내용 보강 질문

사용자가 스스로 글의 내용을 깊게 만들 수 있는
질문 4개를 제시합니다.

## 최종 점검표

다음 항목을 각각 5점 척도로 평가하고
한 줄로 근거를 설명합니다.

- 핵심 주장
- 해결 방법의 구체성
- 창의성
- 글의 구성
- 문장 표현

글 전체를 새로 작성하지 말고,
사용자가 직접 수정할 수 있도록 방향을 알려주세요.
""".strip()

    draft_exists = bool(
        st.session_state.get(
            "draft_text",
            "",
        ).strip()
    )

    if st.button(
        "🔍 AI 피드백 받기",
        disabled=not API_KEY_READY or not draft_exists,
        use_container_width=True,
        key="generate_feedback",
    ):
        run_generation(
            feedback_prompt,
            "feedback_text",
            max_output_tokens=1800,
        )

    st.text_area(
        "AI 피드백",
        height=440,
        key="feedback_text",
    )

    st.text_area(
        "수정 요청",
        height=110,
        help=(
            "피드백 중 어떤 부분을 반영할지 "
            "사용자가 직접 결정하세요."
        ),
        key="revision_request",
    )

    revision_prompt = f"""
[글쓰기 과제]

{TASK}

[현재 초안]

{st.session_state.get("draft_text", "")}

[AI가 제공한 피드백]

{st.session_state.get("feedback_text", "") or "별도의 피드백 없음"}

[사용자의 수정 요청]

{st.session_state.get("revision_request", "")}

현재 초안을 수정해 주세요.

다음 조건을 지켜주세요.

1. 사용자의 핵심 생각과 글의 개성을 최대한 유지합니다.
2. 글을 불필요하게 전부 새로 작성하지 않습니다.
3. 사용자 요청과 피드백에 해당하는 부분을 중심으로 수정합니다.
4. 확인되지 않은 통계나 출처를 새로 만들지 않습니다.
5. 환경오염 해결 방법을 가능한 한 구체적으로 표현합니다.
6. 수정된 글을 먼저 제시합니다.
7. 글 뒤에 '수정한 핵심'이라는 제목으로
   주요 수정 사항을 4개 이하로 정리합니다.
""".strip()

    if st.button(
        "🛠️ 피드백을 반영한 수정본 만들기",
        disabled=not API_KEY_READY or not draft_exists,
        use_container_width=True,
        key="revise_draft",
    ):
        run_generation(
            revision_prompt,
            "draft_text",
            max_output_tokens=2300,
        )


# =========================================================
# 4. AI 코치와 자유 대화
# =========================================================
with chat_tab:
    st.subheader("AI 글쓰기 코치에게 질문하기")

    st.caption(
        "질문 예시: "
        "‘도입을 더 흥미롭게 만드는 질문 3개를 알려줘’, "
        "‘기업의 역할을 더 구체화해 줘’, "
        "‘내가 사용한 비유가 자연스러운지 확인해 줘’"
    )

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_message = st.chat_input(
        "글쓰기에 관해 질문하세요",
        disabled=not API_KEY_READY,
        key="coach_chat_input",
    )

    if user_message:
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        recent_messages = st.session_state.chat_messages[-8:]

        conversation_text = "\n\n".join(
            (
                "사용자: " + message["content"]
                if message["role"] == "user"
                else "AI 코치: " + message["content"]
            )
            for message in recent_messages
        )

        chat_prompt = f"""
[글쓰기 과제]

{TASK}

[현재 개요]

{st.session_state.get("outline_text", "") or "아직 개요 없음"}

[현재 초안]

{st.session_state.get("draft_text", "") or "아직 초안 없음"}

[최근 대화]

{conversation_text}

최근 대화의 마지막 사용자 질문에 답해 주세요.

다음 원칙을 지켜주세요.

- 사용자의 현재 글과 연결해서 구체적으로 답합니다.
- 가능한 경우 선택지나 짧은 예시를 제공합니다.
- 확인되지 않은 사실이나 통계를 만들지 않습니다.
- 사용자가 생각할 여지를 남기되 질문에는 직접 답합니다.
- 전체 글을 대신 작성하기보다 사용자의 글쓰기를 돕습니다.
""".strip()

        try:
            with st.spinner(
                "AI 코치가 답변을 준비하고 있습니다..."
            ):
                assistant_message = call_openai(
                    chat_prompt,
                    max_output_tokens=1200,
                )

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message,
                }
            )

            st.rerun()

        except RuntimeError as error:
            st.error(str(error))


# =========================================================
# 하단 안내
# =========================================================
st.divider()

st.caption(
    "이 앱은 OpenAI API를 사용합니다. "
    "API 사용량에 따라 비용이 발생할 수 있습니다. "
    "AI가 생성한 내용은 사용자가 사실성과 적절성을 확인해야 합니다."
)
