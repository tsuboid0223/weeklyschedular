import streamlit as st
import json
import base64
from datetime import datetime, timedelta
from PIL import Image
import io
import uuid

# 追加: オプション依存（なくても動く）
# ドラッグ＆ドロップ: streamlit-sortables
try:
    from streamlit_sortables import sort_items
    SORTABLE_AVAILABLE = True
except Exception:
    SORTABLE_AVAILABLE = False

# サムネイル画像のクリック対応: streamlit-extras
try:
    from streamlit_extras.clickable_images import clickable_images
    CLICKABLE_AVAILABLE = True
except Exception:
    CLICKABLE_AVAILABLE = False


# ページ設定
st.set_page_config(
    page_title="週間タスクスケジューラー",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f2937;
        margin-bottom: 2rem;
    }
    .week-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
    .day-column {
        background: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem;
        min-height: 400px;
        border: 2px solid #e2e8f0;
    }
    .task-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #3b82f6;
    }
    .task-card.high { border-left-color: #ef4444; }
    .task-card.medium { border-left-color: #f59e0b; }
    .task-card.low { border-left-color: #10b981; }

    .priority-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: bold;
        margin-right: 0.5rem;
    }
    .priority-high { background-color: #fecaca; color: #dc2626; }
    .priority-medium { background-color: #fed7aa; color: #ea580c; }
    .priority-low { background-color: #bbf7d0; color: #059669; }

    .label-tag {
        display: inline-block;
        background: #e0e7ff;
        color: #3730a3;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.75rem;
        margin: 0.1rem;
    }
</style>
""", unsafe_allow_html=True)


# データクラス
class Task:
    def __init__(self, id=None, title="", description="", date="", priority="medium", labels=None, attachments=None):
        self.id = id or str(uuid.uuid4())
        self.title = title
        self.description = description
        self.date = date  # "YYYY-MM-DD"
        self.priority = priority  # low/medium/high
        self.labels = labels or []
        self.attachments = attachments or []  # base64データURI
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'date': self.date,
            'priority': self.priority,
            'labels': self.labels,
            'attachments': self.attachments,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            date=data['date'],
            priority=data['priority'],
            labels=data.get('labels', []),
            attachments=data.get('attachments', [])
        )
        if 'created_at' in data:
            task.created_at = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            task.updated_at = datetime.fromisoformat(data['updated_at'])
        return task


# セッション状態の初期化
if 'tasks' not in st.session_state:
    st.session_state.tasks = []
if 'current_week' not in st.session_state:
    st.session_state.current_week = datetime.now().date()
if 'image_modal_open' not in st.session_state:
    st.session_state.image_modal_open = False
if 'image_modal' not in st.session_state:
    st.session_state.image_modal = None


# ユーティリティ関数
def get_week_dates(start_date):
    """指定した日付を含む週の7日（月曜起点）"""
    days_since_monday = start_date.weekday()
    monday = start_date - timedelta(days=days_since_monday)
    return [monday + timedelta(days=i) for i in range(7)]


def format_date_jp(date):
    """日本語形式で日付をフォーマット"""
    weekdays = ['月', '火', '水', '木', '金', '土', '日']
    return f"{date.month}/{date.day}({weekdays[date.weekday()]})"


def get_tasks_for_date(date_str):
    """指定した日付のタスクを取得"""
    return [task for task in st.session_state.tasks if task.date == date_str]


def save_task(task):
    """タスクを保存（新規/更新）"""
    existing_index = None
    for i, existing_task in enumerate(st.session_state.tasks):
        if existing_task.id == task.id:
            existing_index = i
            break
    task.updated_at = datetime.now()
    if existing_index is not None:
        st.session_state.tasks[existing_index] = task
    else:
        st.session_state.tasks.append(task)


def delete_task(task_id):
    """タスクを削除"""
    st.session_state.tasks = [task for task in st.session_state.tasks if task.id != task_id]


def process_uploaded_image(uploaded_file):
    """アップロードされた画像をbase64エンコードして保持"""
    if uploaded_file is not None:
        image_data = uploaded_file.read()
        base64_data = base64.b64encode(image_data).decode()
        return {
            'id': str(uuid.uuid4()),
            'name': uploaded_file.name,
            'type': uploaded_file.type,
            'size': len(image_data),
            'data': f"data:{uploaded_file.type};base64,{base64_data}"
        }
    return None


# 週次HTMLを生成（単一HTML、画像は埋め込み）
def generate_week_html(week_dates):
    weekdays_jp = ['月曜日','火曜日','水曜日','木曜日','金曜日','土曜日','日曜日']
    css = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", Arial, "Noto Sans", sans-serif; background:#f3f4f6; margin:0; padding:1rem;}
        .container{max-width:1200px;margin:0 auto;}
        .week-header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:1rem;border-radius:10px;text-align:center;margin-bottom:1rem;}
        .grid{display:grid;grid-template-columns:repeat(7,1fr);gap:10px;}
        .day{background:#f8fafc;border-radius:8px;padding:10px;border:2px solid #e2e8f0;min-height:200px;}
        .title{font-size:14px;font-weight:700;margin-bottom:6px;}
        .date{font-size:12px;color:#6b7280;margin-bottom:8px;}
        .task-card{background:#fff;border-radius:8px;padding:8px;margin:6px 0;border-left:4px solid #3b82f6;box-shadow:0 2px 4px rgba(0,0,0,0.06);}
        .task-card.high{border-left-color:#ef4444;}
        .task-card.medium{border-left-color:#f59e0b;}
        .task-card.low{border-left-color:#10b981;}
        .priority-badge{display:inline-block;padding:2px 6px;border-radius:9999px;font-size:10px;font-weight:700;margin-right:6px;}
        .priority-high{background:#fecaca;color:#dc2626;}
        .priority-medium{background:#fed7aa;color:#ea580c;}
        .priority-low{background:#bbf7d0;color:#059669;}
        .label{display:inline-block;background:#e0e7ff;color:#3730a3;padding:2px 6px;border-radius:12px;font-size:10px;margin:2px;}
        img.thumb{max-width:100%;border-radius:6px;border:1px solid #e5e7eb;margin-top:6px;}
        .desc{font-size:12px;color:#374151;margin-top:4px;white-space:pre-wrap;}
    </style>
    """
    week_start_str = week_dates[0].strftime("%Y/%m/%d")
    week_end_str = week_dates[6].strftime("%Y/%m/%d")

    html = [css, '<div class="container">']
    html.append(f'<div class="week-header"><h2>📅 {week_start_str} - {week_end_str}</h2></div>')
    html.append('<div class="grid">')

    for i, date in enumerate(week_dates):
        ds = date.strftime("%Y-%m-%d")
        tasks = get_tasks_for_date(ds)
        html.append('<div class="day">')
        html.append(f'<div class="title">{weekdays_jp[i]}</div>')
        html.append(f'<div class="date">{format_date_jp(date)}</div>')
        if not tasks:
            html.append('<div style="font-size:12px;color:#6b7280;">タスクなし</div>')
        else:
            for t in tasks:
                pclass = t.priority
                ptext = {'high':'高','medium':'中','low':'低'}[t.priority]
                html.append(f'<div class="task-card {pclass}">')
                html.append(f'<div><strong>{t.title}</strong> <span class="priority-badge priority-{pclass}">{ptext}</span></div>')
                if t.description:
                    html.append(f'<div class="desc">{t.description}</div>')
                if t.labels:
                    labels_html = ''.join([f'<span class="label">{label}</span>' for label in t.labels])
                    html.append(f'<div style="margin-top:4px;">{labels_html}</div>')
                if t.attachments:
                    for att in t.attachments:
                        if att['type'].startswith('image/'):
                            html.append(f'<img class="thumb" src="{att["data"]}" alt="{att["name"]}"/>')
                html.append('</div>')
        html.append('</div>')
    html.append('</div></div>')
    return ''.join(html)


# D&Dボードの描画（streamlit-sortables使用）
def render_dnd_board(week_dates):
    if not SORTABLE_AVAILABLE:
        st.info("ドラッグ＆ドロップを使うには requirements.txt に 'streamlit-sortables' を追加してください。")
        return

    st.markdown("#### 🧲 ドラッグ＆ドロップでタスクを曜日移動")

    # 7日分のアイテムを準備（key: 日付文字列, value: アイテム配列）
    date_keys = [d.strftime("%Y-%m-%d") for d in week_dates]
    containers = {}
    for ds in date_keys:
        tasks = get_tasks_for_date(ds)
        containers[ds] = [{"id": t.id, "content": t.title} for t in tasks]

    # 並び替えUI（横方向で7コンテナを並べる）
    new_containers = sort_items(
        containers,
        multi_containers=True,
        direction="horizontal",
        styles={
            "container": {
                "minHeight": "220px",
                "backgroundColor": "#f8fafc",
                "border": "2px dashed #e2e8f0",
                "borderRadius": "8px",
                "padding": "8px",
                "margin": "6px",
            },
            "item": {
                "padding": "6px 10px",
                "margin": "4px 0",
                "backgroundColor": "white",
                "border": "1px solid #e2e8f0",
                "borderRadius": "8px",
                "cursor": "grab",
            },
        },
        key="dnd_board",
    )

    # 変更反映（タスクID -> 新しい日付）
    id_to_new_date = {}
    for ds, items in new_containers.items():
        for item in items:
            if isinstance(item, dict) and "id" in item:
                tid = item["id"]
            else:
                tid = str(item)
            id_to_new_date[tid] = ds

    changed = False
    for task in st.session_state.tasks:
        new_date = id_to_new_date.get(task.id)
        if new_date and new_date != task.date:
            task.date = new_date
            task.updated_at = datetime.now()
            changed = True

    if changed:
        st.success("タスクの日付を更新しました。")
        st.rerun()


# モーダル制御（画像拡大）
def open_image_modal(attachment):
    st.session_state.image_modal = attachment
    st.session_state.image_modal_open = True


def close_image_modal():
    st.session_state.image_modal = None
    st.session_state.image_modal_open = False


# メインアプリケーション
def main():
    # ヘッダー
    st.markdown('<h1 class="main-header">📅 週間タスクスケジューラー</h1>', unsafe_allow_html=True)

    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")

        # 週選択
        week_start = st.date_input(
            "週を選択",
            value=st.session_state.current_week,
            key="week_selector"
        )
        st.session_state.current_week = week_start

        # タスク統計（全体）
        st.subheader("📊 タスク統計（全体）")
        total_tasks = len(st.session_state.tasks)
        high_priority = len([t for t in st.session_state.tasks if t.priority == 'high'])
        st.metric("総タスク数", total_tasks)
        st.metric("高優先度", high_priority)

        # データ管理（JSONエクスポート）
        st.subheader("💾 データ管理")
        if st.session_state.tasks:
            tasks_data = [task.to_dict() for task in st.session_state.tasks]
            json_data = json.dumps(tasks_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 JSONダウンロード",
                data=json_data,
                file_name=f"tasks_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )

        # HTMLダッシュボード出力
        st.subheader("🖼️ HTMLダッシュボード")
        week_dates = get_week_dates(st.session_state.current_week)
        html_data = generate_week_html(week_dates)
        st.download_button(
            label="📤 HTMLダウンロード",
            data=html_data,
            file_name=f"tasks_dashboard_{week_dates[0].strftime('%Y%m%d')}_{week_dates[6].strftime('%Y%m%d')}.html",
            mime="text/html"
        )

        # データクリア
        st.subheader("危険な操作")
        if st.button("🗑️ 全データクリア", type="secondary"):
            if st.checkbox("本当に削除しますか？"):
                st.session_state.tasks = []
                st.rerun()

    # 週表示
    week_dates = get_week_dates(st.session_state.current_week)
    week_start_str = week_dates[0].strftime("%Y/%m/%d")
    week_end_str = week_dates[6].strftime("%Y/%m/%d")
    st.markdown(f'<div class="week-header"><h2>📅 {week_start_str} - {week_end_str}</h2></div>', unsafe_allow_html=True)

    # D&Dモード（オプション）
    with st.expander("🧲 ドラッグ＆ドロップで曜日を移動（週内タスク）", expanded=False):
        if SORTABLE_AVAILABLE:
            render_dnd_board(week_dates)
            st.caption("タイトルのみの簡易カードで移動できます。移動後、自動で再描画されます。")
        else:
            st.info("この機能を使うには requirements.txt に 'streamlit-sortables' を追加してください。")

    # 新しいタスク作成
    with st.expander("➕ 新しいタスクを作成", expanded=False):
        with st.form("new_task_form"):
            col1, col2 = st.columns([2, 1])

            with col1:
                title = st.text_input("タスクタイトル *", placeholder="例: 会議準備")
                description = st.text_area("説明", placeholder="詳細な説明を入力...")

            with col2:
                task_date = st.date_input("日付", value=datetime.now().date())
                priority = st.selectbox("優先度", ["low", "medium", "high"], index=1)
                labels_input = st.text_input("ラベル (カンマ区切り)", placeholder="会議,重要")

            uploaded_file = st.file_uploader("画像を添付", type=['png', 'jpg', 'jpeg', 'gif'])
            submitted = st.form_submit_button("💾 タスクを保存")

            if submitted and title:
                labels = [label.strip() for label in labels_input.split(',') if label.strip()]
                attachments = []
                if uploaded_file:
                    attachment = process_uploaded_image(uploaded_file)
                    if attachment:
                        attachments.append(attachment)
                new_task = Task(
                    title=title,
                    description=description,
                    date=task_date.strftime("%Y-%m-%d"),
                    priority=priority,
                    labels=labels,
                    attachments=attachments
                )
                save_task(new_task)
                st.success(f"✅ タスク「{title}」を作成しました！")
                st.rerun()

    # 週間ビュー
    cols = st.columns(7)
    weekdays = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']

    for i, (date, col, weekday) in enumerate(zip(week_dates, cols, weekdays)):
        with col:
            date_str = date.strftime("%Y-%m-%d")
            date_display = format_date_jp(date)

            st.markdown(f"### {weekday}")
            st.markdown(f"**{date_display}**")

            day_tasks = get_tasks_for_date(date_str)

            if not day_tasks:
                st.markdown('<div class="day-column">タスクなし</div>', unsafe_allow_html=True)
            else:
                for task in day_tasks:
                    priority_class = f"task-card {task.priority}"
                    priority_badge_class = f"priority-badge priority-{task.priority}"

                    with st.container():
                        st.markdown(f'<div class="{priority_class}">', unsafe_allow_html=True)

                        col_title, col_actions = st.columns([3, 1])
                        with col_title:
                            st.markdown(f"**{task.title}**")
                            if task.priority != 'medium':
                                priority_text = {'high': '高', 'medium': '中', 'low': '低'}[task.priority]
                                st.markdown(f'<span class="{priority_badge_class}">{priority_text}</span>', unsafe_allow_html=True)

                        with col_actions:
                            if st.button("🗑️", key=f"delete_{task.id}", help="削除"):
                                delete_task(task.id)
                                st.rerun()

                        if task.description:
                            st.markdown(f"<small>{task.description}</small>", unsafe_allow_html=True)

                        if task.labels:
                            labels_html = ''.join([f'<span class="label-tag">{label}</span>' for label in task.labels])
                            st.markdown(labels_html, unsafe_allow_html=True)

                        # 画像（クリックで拡大表示）
                        if task.attachments:
                            st.markdown("**📎 添付ファイル:**")
                            for attachment in task.attachments:
                                if attachment['type'].startswith('image/'):
                                    if CLICKABLE_AVAILABLE:
                                        clicked = clickable_images(
                                            [attachment['data']],
                                            titles=[attachment['name']],
                                            div_style={
                                                "display": "inline-block",
                                                "padding": "2px",
                                                "border-radius": "8px"
                                            },
                                            img_style={
                                                "margin": "4px",
                                                "height": "120px",
                                                "border-radius": "6px",
                                                "border": "1px solid #e2e8f0",
                                                "box-shadow": "0 1px 2px rgba(0,0,0,0.05)"
                                            },
                                            key=f"thumb_{task.id}_{attachment['id']}"
                                        )
                                        if clicked == 0:
                                            open_image_modal(attachment)
                                            st.rerun()
                                    else:
                                        # フォールバック: サムネイル + 拡大ボタン
                                        try:
                                            image_data = attachment['data'].split(',')[1]
                                            image_bytes = base64.b64decode(image_data)
                                            image = Image.open(io.BytesIO(image_bytes))
                                            st.image(image, caption=attachment['name'], width=150)
                                        except Exception as e:
                                            st.error(f"画像の表示エラー: {str(e)}")
                                        if st.button("🔍 拡大表示", key=f"view_{task.id}_{attachment['id']}"):
                                            open_image_modal(attachment)
                                            st.rerun()

                        st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown("---")

    # モーダル（拡大画像）
    if st.session_state.image_modal_open and st.session_state.image_modal:
        with st.modal("画像プレビュー", key="image_modal"):
            att = st.session_state.image_modal
            st.image(att['data'], caption=att.get('name', ''), use_column_width=True)
            st.caption("Esc または下のボタンで閉じられます。")
            if st.button("閉じる", key="close_image_modal_btn"):
                close_image_modal()
                st.rerun()


if __name__ == "__main__":
    main()
