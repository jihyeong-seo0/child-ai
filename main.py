# =========================================================
# 환경오염 해결 아이디어 + 생성형 AI 대화 앱 (Streamlit)
# - Solar API(모델: solar-open2)를 openai 라이브러리로 사용
# - 초보자를 위해 한국어 주석을 최대한 자세히 달았어요.
# =========================================================

# 1) 필요한 라이브러리 불러오기 ----------------------------
import json                       # 저장한 대화를 파일(JSON)로 내려받을 때 사용
import streamlit as st            # 화면(웹앱)을 만들어 주는 라이브러리
from openai import OpenAI         # Solar API를 호출할 때 쓰는 라이브러리


# 2) 페이지 기본 설정 --------------------------------------
# page_title: 브라우저 탭에 보이는 이름 / page_icon: 탭 아이콘
st.set_page_config(page_title="환경오염 해결 아이디어", page_icon="🌍")


# 3) 화면 맨 위 제목 ---------------------------------------
st.title("환경오염을 해결하기 위한 아이디어를 작성해주세요.")


# 4) AI에게 줄 '성격' (시스템 프롬프트) --------------------
# 이 문장이 AI의 말투와 역할을 정해 줍니다.
SYSTEM_PROMPT = "너는 따뜻하고 친절한 데이터 분석 선생님이야. 반드시 순수 한국어로만 답해"


# 5) Solar API 연결 클라이언트 만들기 ----------------------
# - api_key: 코드에 직접 쓰지 않고, 비밀 금고(secrets)에서 불러옵니다.
#   (Streamlit Cloud의 Settings > Secrets 에 SOLAR_API_KEY 를 넣어 두세요.)
# - base_url: Solar API 접속 주소
client = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1",
)


# 6) 사이드바(왼쪽 메뉴) - 이름과 학년 입력 ----------------
with st.sidebar:
    st.header("학생 정보")

    # 이름: 이 이름이 '하나의 코드(구분자)'가 되어
    #      아래에서 아이디어/프롬프트/결과물을 이 이름에 묶어 저장합니다.
    name = st.text_input("이름을 입력하세요")

    # 나이(학년): 초등학교 5학년 / 6학년 중에서 선택
    grade = st.radio("나이(학년)를 선택하세요", ["초등학교 5학년", "초등학교 6학년"])


# 7) 세션 상태 준비하기 ------------------------------------
# 세션 상태(session_state)는 새로고침해도 값이 유지되는 '기억 장치'예요.
# - messages: 지금 진행 중인 대화 내용(AI가 이전 대화를 기억하게 해줌)
# - records : 이름별로 저장한 아이디어/대화 기록 (이름이 '코드' 역할)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "records" not in st.session_state:
    st.session_state.records = {}


# 8) 이름별 저장 공간을 만들어 주는 도우미 함수 ------------
def 이름_저장공간_준비(학생이름):
    """해당 이름의 저장 공간이 없으면 새로 만들어 줍니다."""
    if 학생이름 not in st.session_state.records:
        st.session_state.records[학생이름] = {
            "학년": grade,       # 선택한 학년
            "아이디어": [],       # 학생이 직접 쓴 아이디어들
            "대화": [],          # (질문, 답변) 쌍으로 저장되는 AI 대화
        }
    # 학년은 바뀔 수 있으니 항상 최신 값으로 갱신
    st.session_state.records[학생이름]["학년"] = grade


# =========================================================
# 9) [첫 번째 칸] 아이디어 작성 칸
# =========================================================
st.header("✏️ 아이디어 작성 칸")
st.caption("환경오염을 해결할 나만의 아이디어를 자유롭게 적어 보세요.")

# 여러 줄을 쓸 수 있는 입력 상자
아이디어_내용 = st.text_area("나의 아이디어", height=150, placeholder="예) 학교에서 분리수거 게임을 만들어요!")

# 아이디어 저장 버튼
if st.button("아이디어 저장하기"):
    if not name:  # 이름이 비어 있으면 저장하지 않음
        st.warning("먼저 사이드바에서 이름을 입력해 주세요.")
    elif not 아이디어_내용.strip():  # 내용이 비어 있으면 저장하지 않음
        st.warning("아이디어 내용을 입력해 주세요.")
    else:
        이름_저장공간_준비(name)  # 이 이름의 저장 공간 준비
        st.session_state.records[name]["아이디어"].append(아이디어_내용)
        st.success(f"'{name}' 학생의 아이디어가 저장되었어요! 👍")

# 지금까지 이 이름으로 저장한 아이디어 보여주기
if name and name in st.session_state.records:
    저장된_아이디어들 = st.session_state.records[name]["아이디어"]
    if 저장된_아이디어들:
        with st.expander(f"📌 '{name}' 학생이 저장한 아이디어 보기 ({len(저장된_아이디어들)}개)"):
            for 번호, 글 in enumerate(저장된_아이디어들, start=1):
                st.write(f"{번호}. {글}")


# 두 칸을 시각적으로 구분하는 선
st.divider()


# =========================================================
# 10) [두 번째 칸] 생성형 AI 대화 칸
# =========================================================
st.header("🤖 생성형 AI 대화 칸")
st.caption("아이디어에 대해 AI 선생님과 이야기해 보세요.")

# (1) 지금까지의 대화를 말풍선으로 다시 그려 주기
#     - 새로고침되어도 이전 대화가 화면에 계속 보이게 합니다.
for 메시지 in st.session_state.messages:
    with st.chat_message(메시지["role"]):   # role: "user"(학생) 또는 "assistant"(AI)
        st.markdown(메시지["content"])


# (2) 스트리밍으로 받은 글자를 실시간으로 흘려보내 주는 도우미 함수
def 실시간_글자흐름(스트림):
    """AI가 보내주는 조각(chunk)에서 글자만 뽑아 하나씩 내보냅니다."""
    for 조각 in 스트림:
        내용 = 조각.choices[0].delta.content  # 이번 조각의 글자
        if 내용:                              # 빈 조각은 건너뜀
            yield 내용


# (3) 화면 아래쪽 채팅 입력창
질문 = st.chat_input("메시지를 입력하세요")

if 질문:  # 학생이 무언가 입력했다면
    # 이름을 안 적었으면, 결과를 이름에 묶어 저장할 수 없으니 먼저 안내
    if not name:
        st.warning("사이드바에서 이름을 먼저 입력해 주세요. 이름으로 대화가 저장됩니다.")
        st.stop()  # 여기서 실행을 멈춤

    # 3-1) 학생이 보낸 메시지를 기억에 추가하고 말풍선으로 표시
    st.session_state.messages.append({"role": "user", "content": 질문})
    with st.chat_message("user"):
        st.markdown(질문)

    # 3-2) AI의 답변을 말풍선으로 이어서 보여 주기
    with st.chat_message("assistant"):
        try:
            # Solar API에 대화 요청 보내기
            스트림 = client.chat.completions.create(
                model="solar-open2",  # 모델 이름은 반드시 이 글자 그대로!
                messages=(
                    # 맨 앞에 시스템 프롬프트(성격)를 넣고,
                    # 그 뒤에 지금까지의 전체 대화를 함께 보냅니다.
                    # -> 이렇게 하면 AI가 이전 대화를 기억하며 이어서 답합니다.
                    [{"role": "system", "content": SYSTEM_PROMPT}]
                    + st.session_state.messages
                ),
                stream=True,               # 스트리밍으로 받기 (글자가 실시간으로 흘러나옴)
                reasoning_effort="none",   # 추론(생각) 기능 끄기 -> 답이 더 빨리 나옴
            )

            # 흘러나오는 글자를 화면에 실시간으로 써 주고,
            # 완성된 전체 답변 문자열을 돌려받습니다.
            답변 = st.write_stream(실시간_글자흐름(스트림))

        except Exception:
            # 요청이 실패해도 무서운 에러 화면 대신 친절한 안내를 보여 줍니다.
            답변 = None
            st.error(
                "앗, 답변을 가져오는 데 문제가 생겼어요. 😢\n\n"
                "잠시 후 다시 시도해 주세요. 문제가 계속되면 인터넷 연결이나 "
                "API 키(SOLAR_API_KEY) 설정을 확인해 주세요."
            )

    # 3-3) AI 답변이 정상적으로 왔다면, 기억과 저장 기록에 남기기
    if 답변:
        # 대화 기억에 AI 답변 추가 (다음 질문 때 이 답변도 함께 참고됨)
        st.session_state.messages.append({"role": "assistant", "content": 답변})

        # 이름(코드)에 '질문(프롬프트)'과 '답변(결과물)'을 묶어서 저장
        이름_저장공간_준비(name)
        st.session_state.records[name]["대화"].append(
            {"프롬프트": 질문, "결과물": 답변}
        )


# =========================================================
# 11) 사이드바 아래쪽 - 이름으로 저장된 기록 내려받기
# =========================================================
with st.sidebar:
    st.divider()
    st.subheader("저장된 기록")

    if name and name in st.session_state.records:
        # 이름별 기록을 보기 좋은 JSON 글자로 바꿉니다.
        기록_텍스트 = json.dumps(
            {name: st.session_state.records[name]},
            ensure_ascii=False,  # 한글이 깨지지 않게
            indent=2,
        )
        # 다운로드 버튼: 파일 이름에도 학생 이름(코드)이 들어갑니다.
        st.download_button(
            label="내 기록 내려받기 (JSON)",
            data=기록_텍스트,
            file_name=f"{name}_기록.json",
            mime="application/json",
        )
    else:
        st.caption("이름을 입력하고 아이디어나 대화를 저장하면 여기에서 내려받을 수 있어요.")
