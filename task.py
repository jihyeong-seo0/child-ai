"""
창의적 글쓰기 + 생성형 AI 프롬프트 사용 연구용 웹앱
Streamlit Cloud 배포용 단일 파일 코드
필요 라이브러리: streamlit 만 사용 (API 호출, CSV 저장 등은 파이썬 표준 라이브러리만 사용)
"""

import streamlit as st
import urllib.request
import json
import csv
import io
from datetime import datetime

# ----------------------------
# 기본 설정
# ----------------------------
st.set_page_config(page_title="창의적 글쓰기 with AI", page_icon="✍️", layout="wide")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL_NAME = "claude-sonnet-5"

# Streamlit Cloud > App settings > Secrets 에 아래처럼 등록해서 사용하세요.
# ANTHROPIC_API_KEY = "sk-ant-xxxxxxxx"
API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "").strip()


def validate_api_key(key: str):
    """API 키에 문제가 있으면 사용자에게 보여줄 메시지를 반환하고, 문제 없으면 None을 반환."""
    if not key:
        return "API 키가 설정되어 있지 않습니다. Secrets에 ANTHROPIC_API_KEY를 등록해 주세요."
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        return (
            "API 키에 일반 문자가 아닌 특수문자(예: 하이픈이 대시(–)로, "
            "따옴표가 스마트 따옴표로 자동 변환됨)가 섞여 있습니다. "
            "Secrets에서 키를 지우고 메모장 등 서식 없는 곳에 붙여넣은 뒤 다시 등록해 주세요."
        )
    return None


API_KEY_ERROR = validate_api_key(API_KEY)

# ----------------------------
# 세션 상태 초기화
# ----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{"role": "user"/"assistant", "content": str, "timestamp": str}]

if "participant_id" not in st.session_state:
    st.session_state.participant_id = ""

if "task_started_at" not in st.session_state:
    st.session_state.task_started_at = None


# ----------------------------
# Claude API 호출 함수 (표준 라이브러리 urllib 사용)
# ----------------------------
def call_claude_api(conversation_history, system_prompt, api_key):
    """
    conversation_history: [{"role": "user"/"assistant", "content": str}, ...]
    """
    payload = {
        "model": MODEL_NAME,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": conversation_history,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text_parts = [
                block["text"] for block in result.get("content", [])
                if block.get("type") == "text"
            ]
            return "\n".join(text_parts).strip()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return f"[API 오류: {e.code}] {err_body}"
    except UnicodeEncodeError:
        return (
            "[오류 발생] API 키에 특수문자가 섞여 있어 요청을 보낼 수 없습니다. "
            "Secrets에서 API 키를 다시 확인해 주세요."
        )
    except Exception as e:
        return f"[오류 발생] {e}"


# ----------------------------
# 로그를 CSV로 변환하는 함수
# ----------------------------
def export_logs_to_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["participant_id", "turn", "role", "content", "timestamp"])
    for i, msg in enumerate(st.session_state.messages, start=1):
        writer.writerow([
            st.session_state.participant_id,
            i,
            msg["role"],
            msg["content"],
            msg["timestamp"],
        ])
    return output.getvalue()


# ----------------------------
# 사이드바: 연구 설정 / 참가자 정보 / 로그 다운로드
# ----------------------------
with st.sidebar:
    st.header("연구 설정")
    st.session_state.participant_id = st.text_input(
        "참가자 ID", value=st.session_state.participant_id, placeholder="예: P01"
    )

    st.divider()
    st.subheader("글쓰기 과제 안내")
    task_prompt = st.text_area(
        "참가자에게 제시할 창의적 글쓰기 과제를 입력하세요.",
        value="AI의 도움을 받아, '예상치 못한 손님'을 소재로 한 짧은 이야기를 써 보세요.",
        height=100,
    )

    system_prompt = st.text_area(
        "AI에게 부여할 역할(system prompt)",
        value=(
            "당신은 창의적 글쓰기를 돕는 어시스턴트입니다. "
            "사용자가 요청하는 대로 아이디어 제안, 문장 수정, 이어쓰기 등을 도와주세요. "
            "사용자의 창작 의도를 존중하고, 직접 완성된 이야기를 대신 써주기보다는 "
            "사용자가 요청한 만큼만 도와주세요."
        ),
        height=100,
    )

    st.divider()
    if st.button("대화 기록 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.task_started_at = None
        st.rerun()

    st.divider()
    st.subheader("연구자용 데이터 내보내기")
    if st.session_state.messages:
        csv_data = export_logs_to_csv()
        st.download_button(
            label="대화 로그 CSV 다운로드",
            data=csv_data,
            file_name=f"prompt_log_{st.session_state.participant_id or 'unknown'}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        json_data = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
        st.download_button(
            label="대화 로그 JSON 다운로드",
            data=json_data,
            file_name=f"prompt_log_{st.session_state.participant_id or 'unknown'}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.caption("아직 기록된 대화가 없습니다.")

    if API_KEY_ERROR:
        st.warning(API_KEY_ERROR)


# ----------------------------
# 메인 화면
# ----------------------------
st.title("✍️ 창의적 글쓰기 with 생성형 AI")
st.info(f"**글쓰기 과제:** {task_prompt}")

if not st.session_state.participant_id:
    st.warning("왼쪽 사이드바에서 참가자 ID를 먼저 입력해 주세요.")

# 대화 내역 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        st.caption(msg["timestamp"])

# 사용자 입력
user_input = st.chat_input("AI에게 도움을 요청하거나, 이야기를 이어서 작성해 보세요.")

if user_input:
    if API_KEY_ERROR:
        st.error(API_KEY_ERROR)
    else:
        if st.session_state.task_started_at is None:
            st.session_state.task_started_at = datetime.now().isoformat()

        # 사용자 메시지 기록
        timestamp = datetime.now().isoformat()
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": timestamp,
        })
        with st.chat_message("user"):
            st.markdown(user_input)
            st.caption(timestamp)

        # API 호출을 위한 대화 이력 구성 (role/content만 추출)
        api_history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages
        ]

        with st.chat_message("assistant"):
            with st.spinner("AI가 응답을 작성하는 중..."):
                ai_response = call_claude_api(api_history, system_prompt, API_KEY)
            st.markdown(ai_response)
            response_timestamp = datetime.now().isoformat()
            st.caption(response_timestamp)

        st.session_state.messages.append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": response_timestamp,
        })

# 참가자가 최종 결과물을 별도로 제출할 수 있는 영역
st.divider()
st.subheader("최종 결과물 제출")
final_text = st.text_area("완성한 글을 최종적으로 여기에 붙여넣어 주세요.", height=200)
if st.button("최종 결과물 기록"):
    st.session_state.messages.append({
        "role": "final_submission",
        "content": final_text,
        "timestamp": datetime.now().isoformat(),
    })
    st.success("최종 결과물이 기록되었습니다. 사이드바에서 로그를 다운로드할 수 있습니다.")
