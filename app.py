import streamlit as st
import json
import base64
from datetime import datetime, timedelta
from PIL import Image
import io
import uuid
import inspect
import re
import hashlib
from pathlib import Path
import threading
from contextlib import contextmanager

# 依存（未インストールでも動作継続）
# ドラッグ＆ドロップ: streamlit-sortables
try:
    from streamlit_sortables import sort_items
    SORTABLE_AVAILABLE = True
except Exception:
    SORTABLE_AVAILABLE = False

# 画像サムネイルのクリック: streamlit-extras
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
    initial_sidebar_state="expanded",
)

# CSS（曜日カードのデザイン含む）
st.markdown(
    """
<style>
:root { --fg:#1f2937; --muted:#6b7280; --border:#e5e7eb; --bg:#f8fafc; }
.main-header { text-align:center; color:var(--fg); margin: 0 0 1.0rem 0; }
.week-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white; padding: 0.9rem 1.2rem; border-radius: 14px; text-align:center; margin-bottom: 0.5rem;
}
.week-header h2 { margin:0; font-size: 1.1rem; font-weight:700; letter-spacing: 0.3px; }

/* 曜日カード */
.day-card { border:1px solid var(--border); border-radius: 12px; overflow:hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin-bottom: .75rem; }
.dc-head { display:flex; justify-content:space-between; align-items:center; padding:.55rem .8rem; color:#fff; font-weight:700; }
.dc-name { font-size:.98rem; letter-spacing:.3px; }
.dc-date { font-size:.9rem; opacity:.9; }
.dc-body { background:#ffffff; min-height: 360px; padding: .6rem .8rem; }

/* 曜日ごとのカラー */
.day-0 .dc-head { background: linear-gradient(135deg,#60a5fa,#3b82f6); } /* 月 */
.day-1 .dc-head { background: linear-gradient(135deg,#34d399,#10b981); } /* 火 */
.day-2 .dc-head { background: linear-gradient(135deg,#fbbf24,#f59e0b); } /* 水 */
.day-3 .dc-head { background: linear-gradient(135deg,#f472b6,#ec4899); } /* 木 */
.day-4 .dc-head { background: linear-gradient(135deg,#a78bfa,#8b5cf6); } /* 金 */
.day-5 .dc-head { background: linear-gradient(135deg,#fca5a5,#ef4444); } /* 土 */
.day-6 .dc-head { background: linear-gradient(135deg,#5eead4,#14b8a6); } /* 日 */

/* タスクカード */
.task-card {
  background: #fff; border-radius: 10px; padding: 0.75rem 0.9rem; margin: 0.6rem 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-left: 4px solid #3b82f6;
}
.task-card.high { border-left-color: #ef4444; }
.task-card.medium { border-left-color: #f59e0b; }
.task-card.low { border-left-color: #10b981; }
.task-title { font-weight: 700; font-size: 0.98rem; margin: 0 0 0.1rem 0; color:var(--fg); }
.priority-badge { display:inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; margin-left: 6px; }
.priority-high { background-color: #fecaca; color: #dc2626; }
.priority-medium { background-color: #fed7aa; color: #ea580c; }
.priority-low { background-color: #bbf7d0; color: #059669; }
.desc { font-size: 0.88rem; color:#374151; line-height: 1.45; margin-top: 0.2rem; }
.label-tag { display:inline-block; background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 9999px; font-size: 0.72rem; margin: 2px 4px 0 0; }
</style>
""",
    unsafe_allow_html=True,
)

# 永続化（同一デプロイ中のリロードでも保持）
DATA_FILE = Path("tasks_store.json")
_PERSIST_LOCK = threading.Lock()


def load_tasks_from_disk():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def persist_tasks_to_disk(task_dicts):
    try:
        with _PERSIST_LOCK:
            DATA_FILE.write_text(
                json.dumps(task_dicts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        pass


class Task:
    def __init__(
        self,
        id=None,
        title="",
        description="",
        date="",
        priority="medium",
        labels=None,
        attachments=None,
    ):
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
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "date": self.date,
            "priority": self.priority,
            "labels": self.labels,
            "attachments": self.attachments,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            date=data["date"],
            priority=data["priority"],
            labels=data.get("labels", []),
            attachments=data.get("attachments", []),
        )
        try:
            if data.get("created_at"):
                task.created_at = datetime.fromisoformat(data["created_at"])
        except Exception:
            task.created_at = datetime.now()
        try:
            if data.get("updated_at"):
                task.updated_at = datetime.fromisoformat(data["updated_at"])
        except Exception:
            task.updated_at = datetime.now()
        return task


# セッション初期化（起動時は常に現在週を表示）
if "initialized" not in st.session_state:
    st.session_state.tasks = [Task.from_dict(d) for d in load_tasks_from_disk()]
    st.session_state.current_week = datetime.now().date()
    st.session_state.image_modal_open = False
    st.session_state.image_modal = None
    st.session_state.edit_task_id = None
    st.session_state.new_task_date = None
    st.session_state.initialized = True


# ユーティリティ
def get_week_dates(start_date):
    monday = start_date - timedelta(days=start_date.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def format_date_jp(date):
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    return f"{date.month}/{date.day}({weekdays[date.weekday()]})"


def get_tasks_for_date(date_str):
    return [task for task in st.session_state.tasks if task.date == date_str]


def save_task(task):
    idx = next((i for i, t in enumerate(st.session_state.tasks) if t.id == task.id), None)
    task.updated_at = datetime.now()
    if idx is not None:
        st.session_state.tasks[idx] = task
    else:
        st.session_state.tasks.append(task)
    persist_tasks_to_disk([t.to_dict() for t in st.session_state.tasks])


def delete_task(task_id):
    st.session_state.tasks = [t for t in st.session_state.tasks if t.id != task_id]
    persist_tasks_to_disk([t.to_dict() for t in st.session_state.tasks])


def process_uploaded_image(uploaded_file):
    if uploaded_file is not None:
        data = uploaded_file.read()
        b64 = base64.b64encode(data).decode()
        return {
            "id": str(uuid.uuid4()),
            "name": uploaded_file.name,
            "type": uploaded_file.type,
            "size": len(data),
            "data": f"data:{uploaded_file.type};base64,{b64}",
        }
    return None


# HTMLダッシュボード
def generate_week_html(week_dates):
    weekdays_jp = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
    css = """
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans JP", "Yu Gothic", Arial, sans-serif; background:#f3f4f6; margin:0; padding:1rem;}
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
    ws, we = week_dates[0].strftime("%Y/%m/%d"), week_dates[6].strftime("%Y/%m/%d")
    html = [
        css,
        '<div class="container">',
        f'<div class="week-header"><h2>📅 {ws} - {we}</h2></div>',
        '<div class="grid">',
    ]
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
                ptext = {"high": "高", "medium": "中", "low": "低"}[t.priority]
                html.append(f'<div class="task-card {pclass}">')
                html.append(
                    f'<div><strong>{t.title}</strong> <span class="priority-badge priority-{pclass}">{ptext}</span></div>'
                )
                if t.description:
                    html.append(f'<div class="desc">{t.description}</div>')
                if t.labels:
                    labels = "".join([f'<span class="label">{lb}</span>' for lb in t.labels])
                    html.append(f'<div style="margin-top:4px;">{labels}</div>')
                if t.attachments:
                    for att in t.attachments:
                        if att["type"].startswith("image/"):
                            html.append(f'<img class="thumb" src="{att["data"]}" alt="{att["name"]}"/>')
                html.append("</div>")
        html.append("</div>")
    html.append("</div></div>")
    return "".join(html)


# D&Dユーティリティ
def build_short_ids(tasks):
    used, mapping = set(), {}
    for t in tasks:
        base = t.id.replace("-", "")
        length = 6
        sid = base[:length]
        while sid in used and length < len(base):
            length += 1
            sid = base[:length]
        used.add(sid)
        mapping[t.id] = sid
    return mapping


def week_signature(week_dates):
    keys = {d.strftime("%Y-%m-%d") for d in week_dates}
    items = [(t.id, t.date, t.updated_at.isoformat()) for t in st.session_state.tasks if t.date in keys]
    items.sort()
    return hashlib.md5(json.dumps(items, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]


# st.modal のフォールバック
@contextmanager
def modal_or_expander(title: str, key: str):
    if hasattr(st, "modal"):
        with st.modal(title, key=key):
            yield
    else:
        with st.expander(title, expanded=True):
            yield


# D&Dボード
def render_dnd_board(week_dates):
    if not SORTABLE_AVAILABLE:
        st.info("ドラッグ＆ドロップを使うには requirements.txt に 'streamlit-sortables' を追加してください。")
        return

    st.markdown("#### 🧲 ドラッグ＆ドロップでタスクを曜日移動")

    date_keys = [d.strftime("%Y-%m-%d") for d in week_dates]
    all_week_tasks = [t for ds in date_keys for t in get_tasks_for_date(ds)]
    short_ids = build_short_ids(all_week_tasks)
    short_to_full = {v: k for k, v in short_ids.items()}

    containers_payload = []
    for ds, d in zip(date_keys, week_dates):
        items = [f"{t.title} [id:{short_ids[t.id]}]" for t in get_tasks_for_date(ds)]
        containers_payload.append({"header": f"{format_date_jp(d)}（{len(items)}）", "items": items})

    kwargs = {"multi_containers": True, "direction": "horizontal"}
    try:
        params = inspect.signature(sort_items).parameters
        if "styles" in params:
            kwargs["styles"] = {
                "container": {
                    "minHeight": "220px",
                    "backgroundColor": "#f8fafc",
                    "border": "2px dashed #e2e8f0",
                    "borderRadius": "10px",
                    "padding": "8px",
                    "margin": "6px",
                },
                "item": {
                    "padding": "6px 10px",
                    "margin": "4px 0",
                    "backgroundColor": "#fff",
                    "border": "1px solid #e5e7eb",
                    "borderRadius": "8px",
                    "cursor": "grab",
                },
            }
        elif "container_style" in params and "item_style" in params:
            kwargs["container_style"] = {
                "minHeight": "220px",
                "backgroundColor": "#f8fafc",
                "border": "2px dashed #e2e8f0",
                "borderRadius": "10px",
                "padding": "8px",
                "margin": "6px",
            }
            kwargs["item_style"] = {
                "padding": "6px 10px",
                "margin": "4px 0",
                "backgroundColor": "#fff",
                "border": "1px solid #e5e7eb",
                "borderRadius": "8px",
                "cursor": "grab",
            }
    except Exception:
        pass

    new_containers = sort_items(containers_payload, **kwargs)

    id_to_new_date, pattern = {}, re.compile(r"\[id:([0-9a-fA-F]+)\]\s*$")
    for idx, cont in enumerate(new_containers):
        ds = date_keys[idx] if idx < len(date_keys) else None
        if ds is None:
            continue
        items_list = cont.get("items") if isinstance(cont, dict) else (cont if isinstance(cont, list) else [])
        for label in items_list:
            s = label.get("content") if isinstance(label, dict) else str(label)
            m = pattern.search(s)
            if not m:
                continue
            short = m.group(1)
            full = short_to_full.get(short)
            if full:
                id_to_new_date[full] = ds

    changed = False
    for task in st.session_state.tasks:
        new_date = id_to_new_date.get(task.id)
        if new_date and new_date != task.date:
            task.date = new_date
            task.updated_at = datetime.now()
            changed = True

    if changed:
        persist_tasks_to_disk([t.to_dict() for t in st.session_state.tasks])
        st.success("タスクの日付を更新しました。")
        st.rerun()


# 画像プレビュー
def open_image_modal(attachment):
    st.session_state.image_modal = attachment
    st.session_state.image_modal_open = True


def close_image_modal():
    st.session_state.image_modal = None
    st.session_state.image_modal_open = False


# 編集モーダル
def open_edit_modal(task_id: str):
    st.session_state.edit_task_id = task_id


def close_edit_modal():
    st.session_state.edit_task_id = None


def render_edit_modal():
    tid = st.session_state.edit_task_id
    if not tid:
        return
    task = next((t for t in st.session_state.tasks if t.id == tid), None)
    if not task:
        close_edit_modal()
        return

    with modal_or_expander("タスクを編集", key=f"edit_modal_{tid}"):
        with st.form(f"edit_form_{tid}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                new_title = st.text_input("タスクタイトル *", value=task.title)
                new_desc = st.text_area("説明", value=task.description)
            with col2:
                base_date = datetime.now().date()
                try:
                    if task.date:
                        base_date = datetime.strptime(task.date, "%Y-%m-%d").date()
                except Exception:
                    pass
                new_date = st.date_input("日付", value=base_date, key=f"edit_date_{tid}")
                new_pri = st.selectbox(
                    "優先度",
                    ["low", "medium", "high"],
                    index=["low", "medium", "high"].index(
                        task.priority if task.priority in ["low", "medium", "high"] else "medium"
                    ),
                    key=f"edit_pri_{tid}",
                )
                new_labels_str = st.text_input("ラベル (カンマ区切り)", value=",".join(task.labels), key=f"edit_labels_{tid}")
                clear_attachments = st.checkbox("既存の添付を全削除", value=False, key=f"edit_clear_{tid}")
            st.markdown("新しい画像を追加（任意）")
            new_upload = st.file_uploader(
                "画像を追加", type=["png", "jpg", "jpeg", "gif"], key=f"edit_upload_{tid}"
            )
            submitted = st.form_submit_button("保存")

        cancel = st.button("キャンセル", key=f"cancel_edit_{tid}")

        if cancel:
            close_edit_modal()
            st.rerun()

        if submitted:
            task.title = (new_title or task.title).strip()
            task.description = new_desc
            task.date = new_date.strftime("%Y-%m-%d")
            task.priority = new_pri
            task.labels = [s.strip() for s in new_labels_str.split(",") if s.strip()]
            if clear_attachments:
                task.attachments = []
            if new_upload:
                att = process_uploaded_image(new_upload)
                if att:
                    task.attachments.append(att)
            save_task(task)
            close_edit_modal()
            st.success("タスクを更新しました。")
            st.rerun()


# 週移動
def goto_prev_week():
    st.session_state.current_week = st.session_state.current_week - timedelta(days=7)
    st.rerun()


def goto_next_week():
    st.session_state.current_week = st.session_state.current_week + timedelta(days=7)
    st.rerun()


def goto_this_week():
    st.session_state.current_week = datetime.now().date()
    st.rerun()


# 新規作成（曜日ごとの＋から開く）
def open_new_task_modal(date_str):
    st.session_state.new_task_date = date_str


def close_new_task_modal():
    st.session_state.new_task_date = None


def render_new_task_modal():
    ds = st.session_state.new_task_date
    if not ds:
        return
    dt = datetime.strptime(ds, "%Y-%m-%d").date()
    with modal_or_expander(f"タスクを追加（{format_date_jp(dt)}）", key=f"new_task_{ds}"):
        with st.form(f"form_new_{ds}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                title = st.text_input("タスクタイトル *", key=f"title_{ds}")
                description = st.text_area("説明", key=f"desc_{ds}")
            with col2:
                st.text_input("日付（固定）", value=ds, disabled=True, key=f"date_{ds}")
                priority = st.selectbox("優先度", ["low", "medium", "high"], index=1, key=f"pri_{ds}")
                labels_input = st.text_input("ラベル (カンマ区切り)", key=f"labels_{ds}")
            uploaded_file = st.file_uploader(
                "画像を添付", type=["png", "jpg", "jpeg", "gif"], key=f"upload_{ds}"
            )
            submitted = st.form_submit_button("💾 タスクを保存")

        cancel = st.button("キャンセル", key=f"cancel_new_{ds}")

        if cancel:
            close_new_task_modal()
            st.rerun()

        if submitted and title.strip():
            labels = [s.strip() for s in labels_input.split(",") if s.strip()]
            attachments = []
            if uploaded_file:
                att = process_uploaded_image(uploaded_file)
                if att:
                    attachments.append(att)
            new_task = Task(
                title=title.strip(),
                description=description,
                date=ds,
                priority=priority,
                labels=labels,
                attachments=attachments,
            )
            save_task(new_task)
            close_new_task_modal()
            st.success(f"✅ タスク「{title}」を作成しました！")
            st.rerun()


# メイン
def main():
    st.markdown('<h1 class="main-header">📅 週間タスクスケジューラー</h1>', unsafe_allow_html=True)

    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        week_start = st.date_input("週を選択", value=st.session_state.current_week, key="week_selector")
        st.session_state.current_week = week_start

        st.subheader("📊 タスク統計（全体）")
        total_tasks = len(st.session_state.tasks)
        high_priority = len([t for t in st.session_state.tasks if t.priority == "high"])
        st.metric("総タスク数", total_tasks)
        st.metric("高優先度", high_priority)

        st.subheader("💾 データ管理")
        if st.session_state.tasks:
            data = json.dumps([t.to_dict() for t in st.session_state.tasks], ensure_ascii=False, indent=2)
            st.download_button(
                "📥 JSONダウンロード",
                data=data,
                file_name=f"tasks_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
            )

        st.subheader("🖼️ HTMLダッシュボード")
        week_dates_sb = get_week_dates(st.session_state.current_week)
        html_data = generate_week_html(week_dates_sb)
        st.download_button(
            "📤 HTMLダウンロード",
            data=html_data,
            file_name=f"tasks_dashboard_{week_dates_sb[0].strftime('%Y%m%d')}_{week_dates_sb[6].strftime('%Y%m%d')}.html",
            mime="text/html",
        )

        st.subheader("危険な操作")
        if st.button("🗑️ 全データクリア", type="secondary"):
            if st.checkbox("本当に削除しますか？"):
                st.session_state.tasks = []
                persist_tasks_to_disk([])
                st.rerun()

    # 週表示
    week_dates = get_week_dates(st.session_state.current_week)
    ws, we = week_dates[0].strftime("%Y/%m/%d"), week_dates[6].strftime("%Y/%m/%d")
    st.markdown(f'<div class="week-header"><h2>📅 {ws} - {we}</h2></div>', unsafe_allow_html=True)

    # 週移動
    nav_prev, nav_today, nav_next = st.columns([1, 1, 1])
    with nav_prev:
        if st.button("⬅ 前の週"):
            goto_prev_week()
    with nav_today:
        if st.button("🏠 今週へ"):
            goto_this_week()
    with nav_next:
        if st.button("次の週 ➡"):
            goto_next_week()

    # D&Dモード
    with st.expander("🧲 ドラッグ＆ドロップでタスクを曜日移動（週内タスク）", expanded=False):
        if SORTABLE_AVAILABLE:
            render_dnd_board(week_dates)
        else:
            st.info("この機能を使うには requirements.txt に 'streamlit-sortables' を追加してください。")

    # 週間ビュー
    cols = st.columns(7)
    weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

    for i, (date, col, weekday) in enumerate(zip(week_dates, cols, weekdays)):
        ds = date.strftime("%Y-%m-%d")
        with col:
            st.markdown(
                f'<div class="day-card day-{i}">'
                f'  <div class="dc-head"><div class="dc-name">{weekday}</div>'
                f'  <div class="dc-date">{format_date_jp(date)}</div></div>'
                f'  <div class="dc-body">',
                unsafe_allow_html=True,
            )

            # 追加ボタン（上部）
            add_left, add_center, add_right = st.columns([1, 1, 1])
            with add_right:
                if st.button("＋ タスク追加", key=f"add_{ds}"):
                    open_new_task_modal(ds)
                    st.rerun()

            # 当日タスク（作成日時の降順＝新しいものが上）
            day_tasks = sorted(get_tasks_for_date(ds), key=lambda t: t.created_at, reverse=True)
            if not day_tasks:
                st.caption("タスクなし")
            else:
                for task in day_tasks:
                    pcls = f"{task.priority}"
                    badge_cls = f"priority-badge priority-{task.priority}"
                    st.markdown(f'<div class="task-card {pcls}">', unsafe_allow_html=True)

                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(f'<div class="task-title">{task.title}</div>', unsafe_allow_html=True)
                        if task.priority != "medium":
                            ptxt = {"high": "高", "medium": "中", "low": "低"}[task.priority]
                            st.markdown(f'<span class="{badge_cls}">{ptxt}</span>', unsafe_allow_html=True)
                    with c2:
                        ec, dc = st.columns(2)
                        with ec:
                            if st.button("✏️", key=f"edit_{task.id}", help="編集"):
                                open_edit_modal(task.id)
                                st.rerun()
                        with dc:
                            if st.button("🗑️", key=f"delete_{task.id}", help="削除"):
                                delete_task(task.id)
                                st.rerun()

                    if task.description:
                        st.markdown(f'<div class="desc">{task.description}</div>', unsafe_allow_html=True)

                    if task.labels:
                        st.markdown(
                            "".join([f'<span class="label-tag">{lb}</span>' for lb in task.labels]),
                            unsafe_allow_html=True,
                        )

                    if task.attachments:
                        st.markdown("**📎 添付ファイル:**")
                        for att in task.attachments:
                            if att["type"].startswith("image/"):
                                if CLICKABLE_AVAILABLE:
                                    clicked = clickable_images(
                                        [att["data"]],
                                        titles=[att["name"]],
                                        div_style={"display": "inline-block", "padding": "2px"},
                                        img_style={
                                            "margin": "4px",
                                            "height": "110px",
                                            "border": "1px solid #e5e7eb",
                                            "border-radius": "6px",
                                        },
                                        key=f"thumb_{task.id}_{att['id']}",
                                    )
                                    if clicked == 0:
                                        open_image_modal(att)
                                        st.rerun()
                                else:
                                    try:
                                        b = base64.b64decode(att["data"].split(",")[1])
                                        img = Image.open(io.BytesIO(b))
                                        st.image(img, caption=att["name"], width=140)
                                    except Exception as e:
                                        st.error(f"画像の表示エラー: {str(e)}")
                                    if st.button("🔍", key=f"view_{task.id}_{att['id']}", help="拡大表示"):
                                        open_image_modal(att)
                                        st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)  # .task-card

            st.markdown("  </div></div>", unsafe_allow_html=True)  # .dc-body / .day-card

    # 編集モーダル
    render_edit_modal()

    # 新規作成モーダル
    render_new_task_modal()

    # 画像プレビューモーダル
    if st.session_state.image_modal_open and st.session_state.image_modal:
        with modal_or_expander("画像プレビュー", key="image_modal"):
            att = st.session_state.image_modal
            st.image(att["data"], caption=att.get("name", ""), use_column_width=True)
            if st.button("閉じる", key="close_image_modal_btn"):
                close_image_modal()
                st.rerun()


if __name__ == "__main__":
    main()
