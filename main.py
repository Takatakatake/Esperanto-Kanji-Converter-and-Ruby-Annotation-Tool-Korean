# streamlit_app_expanded_fixed.py
# ------------------------------------
# メインの Streamlit アプリ (機能拡充版、設定変更しても入力テキストは消えない例)

import streamlit as st
import re
import io
import json
import pandas as pd  # 必要なら使う
from typing import List, Dict, Tuple, Optional
import multiprocessing
import streamlit.components.v1 as components


from esp_text_replacement_module import (
    x_to_circumflex,
    x_to_hat,
    hat_to_circumflex,
    circumflex_to_hat,

    replace_esperanto_chars,
    import_placeholders,

    orchestrate_comprehensive_esperanto_text_replacement,
    parallel_process,
    apply_ruby_html_header_and_footer
)

# ページ設定
st.set_page_config(page_title="Esperanto文の文字列(漢字)置換ツール", layout="wide")

# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ ここからユーザーに表示する日本語を韓国語に置換 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
st.title("에스페란토 문장을 한자 치환하거나, HTML 형식의 번역 루비를 추가하는 (확장판)")

st.write("---")

# 1) JSONファイル (置換ルール) をロードする (デフォルト or アップロード)
selected_option = st.radio(
    "JSON 파일을 어떻게 하시겠습니까? (치환용 JSON 파일 읽기)",
    ("기본값 사용하기", "업로드하기")
)

with st.expander("**샘플 JSON(치환용 JSON 파일)**"):
    # サンプルファイルのパス
    json_file_path = './Appの运行に使用する各类文件/最终的な替换用リスト(列表)(合并3个JSON文件).json'
    # JSONファイルを読み込んでダウンロードボタンを生成
    with open(json_file_path, "rb") as file_json:
        btn_json = st.download_button(
            label="샘플 JSON(치환용 JSON 파일) 다운로드",
            data=file_json,
            file_name="치환용 JSON 파일.json",
            mime="application/json"
        )

replacements_final_list: List[Tuple[str, str, str]] = []
replacements_list_for_localized_string: List[Tuple[str, str, str]] = []
replacements_list_for_2char: List[Tuple[str, str, str]] = []

if selected_option == "기본값 사용하기":
    default_json_path = "./Appの运行に使用する各类文件/最终的な替换用リスト(列表)(合并3个JSON文件).json"
    try:
        with open(default_json_path, 'r', encoding='utf-8') as f:
            combined_data = json.load(f)
            replacements_final_list = combined_data.get(
                "全域替换用のリスト(列表)型配列(replacements_final_list)", [])
            replacements_list_for_localized_string = combined_data.get(
                "局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", [])
            replacements_list_for_2char = combined_data.get(
                "二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", [])
        st.success("기본 JSON을 성공적으로 불러왔습니다.")
    except Exception as e:
        st.error(f"JSON 파일 로드에 실패했습니다: {e}")
        st.stop()
else:
    uploaded_file = st.file_uploader("JSON 파일 업로드(합병 3개 JSON 파일).json 형식", type="json")
    if uploaded_file is not None:
        try:
            combined_data = json.load(uploaded_file)
            replacements_final_list = combined_data.get(
                "全域替换用のリスト(列表)型配列(replacements_final_list)", [])
            replacements_list_for_localized_string = combined_data.get(
                "局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", [])
            replacements_list_for_2char = combined_data.get(
                "二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", [])
            st.success("업로드한 JSON을 성공적으로 불러왔습니다.")
        except Exception as e:
            st.error(f"업로드 JSON 파일 로드에 실패했습니다: {e}")
            st.stop()
    else:
        st.warning("JSON 파일이 업로드되지 않았습니다. 처리를 중단합니다.")
        st.stop()

# 2) placeholders (占位符) の読み込み
placeholders_for_skipping_replacements: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt'
)
placeholders_for_localized_replacement: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt'
)

# 3) 設定パラメータ (UI) - 高度な設定
st.write("---")

st.header("고급 설정 (병렬 처리)")
with st.expander("병렬 처리에 대한 설정 열기"):
    st.write("""
            여기에서는 문자열(한자) 치환 시 사용할 병렬 처리 프로세스 수를 결정합니다.  
            """)
    use_parallel = st.checkbox("병렬 처리를 사용하기", value=False)
    num_processes = st.number_input("동시 프로세스 수", min_value=2, max_value=6, value=4, step=1)

st.write("---")

# ユーザー向け選択肢（キー側を韓国語に変更 / 値側は機能維持のためそのまま）
options = {
    'HTML 형식＿루비 문자 크기 조정': 'HTML格式_Ruby文字_大小调整',
    'HTML 형식＿루비 문자 크기 조정（한자 치환）': 'HTML格式_Ruby文字_大小调整_汉字替换',
    'HTML 형식': 'HTML格式',
    'HTML 형식（한자 치환）': 'HTML格式_汉字替换',
    '괄호 형식': '括弧(号)格式',
    '괄호 형식(한자 치환)': '括弧(号)格式_汉字替换',
    '단순 치환': '替换后文字列のみ(仅)保留(简单替换)'
}

# 사용자에게 보여줄 옵션 목록 (라벨)은 위의 dict 키들을 사용
display_options = list(options.keys())
selected_display = st.selectbox('출력 형식을 선택하세요:', display_options)
format_type = options[selected_display]

processed_text = ""

# 4) 入力テキストのソースを選択 (アップロード or テキストエリア)
st.subheader("입력 텍스트 소스")
source_option = st.radio("입력 텍스트를 어떻게 하시겠습니까?", ("직접 입력", "파일 업로드"))

uploaded_text = ""
if source_option == "파일 업로드":
    text_file = st.file_uploader("텍스트 파일 업로드 (UTF-8)", type=["txt", "csv", "md"])
    if text_file is not None:
        uploaded_text = text_file.read().decode("utf-8", errors="replace")
        st.info("파일을 불러왔습니다.")
    else:
        st.warning("텍스트 파일이 업로드되지 않았습니다. 직접 입력으로 전환하거나 파일을 업로드하세요.")

if "text0_value" not in st.session_state:
    st.session_state["text0_value"] = ""

with st.form(key='text_input_form'):
    if source_option == "직접 입력":
        text0 = st.text_area(
            "에스페란토 문장을 입력하세요",
            height=150,
            value=st.session_state["text0_value"]
        )
    else:
        if not st.session_state["text0_value"] and uploaded_text:
            st.session_state["text0_value"] = uploaded_text
        text0 = st.text_area(
            "에스페란토 문장(파일에서 읽어옴)",
            value=st.session_state["text0_value"],
            height=150
        )

    st.markdown("""'%<50문자 이내의 문자열>%' 형태로 문장의 앞뒤를 '%'로 둘러싸면, 해당 부분은 문자열(한자) 치환 없이 원본 그대로 유지됩니다.""")
    st.markdown("""그리고 '@<18문자 이내의 문자열>@' 형태로 앞뒤를 '@'로 둘러싸면, 해당 부분만 국소적으로 문자열(한자) 치환됩니다.""")

    letter_type = st.radio('출력 문자 형식', ('위 첨자 형태', 'x 형식', '^ 형식'))

    submit_btn = st.form_submit_button('전송')
    cancel_btn = st.form_submit_button('취소')

    if submit_btn:
        st.session_state["text0_value"] = text0

        if use_parallel:
            processed_text = parallel_process(
                text=text0,
                num_processes=num_processes,
                placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
                replacements_list_for_localized_string=replacements_list_for_localized_string,
                placeholders_for_localized_replacement=placeholders_for_localized_replacement,
                replacements_final_list=replacements_final_list,
                replacements_list_for_2char=replacements_list_for_2char,
                format_type=format_type
            )
        else:
            processed_text = orchestrate_comprehensive_esperanto_text_replacement(
                text=text0,
                placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
                replacements_list_for_localized_string=replacements_list_for_localized_string,
                placeholders_for_localized_replacement=placeholders_for_localized_replacement,
                replacements_final_list=replacements_final_list,
                replacements_list_for_2char=replacements_list_for_2char,
                format_type=format_type
            )

        if letter_type == '위 첨자 형태':
            processed_text = replace_esperanto_chars(processed_text, x_to_circumflex)
            processed_text = replace_esperanto_chars(processed_text, hat_to_circumflex)
        elif letter_type == '^ 형식':
            processed_text = replace_esperanto_chars(processed_text, x_to_hat)
            processed_text = replace_esperanto_chars(processed_text, circumflex_to_hat)

        processed_text = apply_ruby_html_header_and_footer(processed_text, format_type)

# =========================================
# フォーム外の処理: 結果表示・ダウンロード
# =========================================
if processed_text:
    if "HTML" in format_type:
        tab1, tab2 = st.tabs(["HTML 미리보기", "치환 결과(HTML 소스 코드)"])
        with tab1:
            components.html(processed_text, height=500, scrolling=True)
        with tab2:
            st.text_area("", processed_text, height=300)
    else:
        tab3_list = st.tabs(["치환 결과 텍스트"])
        with tab3_list[0]:
            st.text_area("", processed_text, height=300)

    download_data = processed_text.encode('utf-8')
    st.download_button(
        label="치환 결과 다운로드",
        data=download_data,
        file_name="치환 결과.html",
        mime="text/html"
    )

st.write("---")
st.title("앱의 GitHub 리포지토리")
st.markdown("https://github.com/Takatakatake/Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-")
